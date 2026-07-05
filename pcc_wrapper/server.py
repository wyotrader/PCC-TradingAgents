import os
import json
import time
import asyncio
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# --- Configuration ---
LLM_CONFIGS = {
    "dev": {
        "llm_provider": "ollama",
        "deep_think_llm": "qwen2.5:7b",
        "quick_think_llm": "qwen2.5:7b",
    },
    "production_local": {
        "llm_provider": "ollama",
        "deep_think_llm": "llama3.2:3b",
        "quick_think_llm": "llama3.2:3b",
    },
    "cloud": {
        "llm_provider": "anthropic",
        "deep_think_llm": "claude-sonnet-4-20250514",
        "quick_think_llm": "claude-sonnet-4-20250514",
    },
}

MODE = os.getenv("PCC_LLM_MODE", "dev")
print(f"Starting with LLM mode: {MODE}")

# --- Models ---
class AnalyzeRequest(BaseModel):
    ticker: str
    date: Optional[str] = None
    mode: str = "swing"

class BatchAnalyzeRequest(BaseModel):
    tickers: list[str]
    date: Optional[str] = None
    mode: str = "swing"

class MarketSummaryRequest(BaseModel):
    market_data: dict

# --- App ---
app = FastAPI(title="PCC TradingAgents Sidecar", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Job tracking
jobs: dict = {}
executor = ThreadPoolExecutor(max_workers=1)

# Analysis cache (ticker -> result, with TTL)
analysis_cache: dict = {}
CACHE_TTL = 1800  # 30 minutes


def get_ta_config():
    """Build TradingAgents config from current mode."""
    config = DEFAULT_CONFIG.copy()
    llm_cfg = LLM_CONFIGS.get(MODE, LLM_CONFIGS["dev"])
    config.update(llm_cfg)
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    return config


def run_analysis(ticker: str, date: str, job_id: str):
    """Run full TradingAgents analysis (blocking, runs in thread pool)."""
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["started_at"] = datetime.utcnow().isoformat()

        start_time = time.time()
        config = get_ta_config()
        ta = TradingAgentsGraph(debug=False, config=config)
        final_state, decision = ta.propagate(ticker, date)
        elapsed = time.time() - start_time

        # Extract all reports from final state
        result = {
            "ticker": ticker,
            "date": date,
            "market_report": final_state.get("market_report", ""),
            "sentiment_report": final_state.get("sentiment_report", ""),
            "news_report": final_state.get("news_report", ""),
            "fundamentals_report": final_state.get("fundamentals_report", ""),
            "bull_case": final_state.get("investment_debate_state", {}).get("bull_history", ""),
            "bear_case": final_state.get("investment_debate_state", {}).get("bear_history", ""),
            "investment_plan": final_state.get("investment_plan", ""),
            "trader_decision": final_state.get("trader_investment_plan", ""),
            "risk_debate": {
                "aggressive": final_state.get("risk_debate_state", {}).get("aggressive_history", ""),
                "conservative": final_state.get("risk_debate_state", {}).get("conservative_history", ""),
                "neutral": final_state.get("risk_debate_state", {}).get("neutral_history", ""),
            },
            "final_decision": decision if isinstance(decision, str) else str(decision),
            "confidence": 0.0,
            "processing_time_seconds": round(elapsed, 1),
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        # Try to extract BUY/HOLD/SELL from decision text
        decision_text = result["final_decision"].upper()
        if "BUY" in decision_text:
            result["final_decision_signal"] = "BUY"
        elif "SELL" in decision_text:
            result["final_decision_signal"] = "SELL"
        else:
            result["final_decision_signal"] = "HOLD"

        jobs[job_id]["status"] = "complete"
        jobs[job_id]["result"] = result
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()

        # Cache the result
        analysis_cache[ticker] = {
            "result": result,
            "cached_at": time.time(),
        }

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        print(f"Analysis failed for {ticker}: {e}")


@app.get("/api/health")
def health():
    llm_cfg = LLM_CONFIGS.get(MODE, {})
    return {
        "status": "ok",
        "mode": MODE,
        "provider": llm_cfg.get("llm_provider", "unknown"),
        "quick_model": llm_cfg.get("quick_think_llm", "unknown"),
        "deep_model": llm_cfg.get("deep_think_llm", "unknown"),
        "active_jobs": sum(1 for j in jobs.values() if j["status"] == "running"),
        "cached_analyses": len(analysis_cache),
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Start a full TradingAgents analysis. Returns job ID for polling."""
    ticker = req.ticker.upper().strip()
    date = req.date or datetime.utcnow().strftime("%Y-%m-%d")

    # Check cache first
    if ticker in analysis_cache:
        cached = analysis_cache[ticker]
        if time.time() - cached["cached_at"] < CACHE_TTL:
            return {
                "job_id": None,
                "status": "complete",
                "cached": True,
                "result": cached["result"],
            }

    # Check if already running for this ticker
    for jid, job in jobs.items():
        if job.get("ticker") == ticker and job["status"] == "running":
            return {"job_id": jid, "status": "running", "cached": False}

    # Create new job
    job_id = f"{ticker}-{int(time.time())}"
    jobs[job_id] = {
        "ticker": ticker,
        "date": date,
        "status": "queued",
        "result": None,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Run in background thread
    executor.submit(run_analysis, ticker, date, job_id)

    return {"job_id": job_id, "status": "queued", "cached": False}


@app.get("/api/analyze/{job_id}")
def get_analysis_status(job_id: str):
    """Poll for analysis result."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    response = {
        "job_id": job_id,
        "ticker": job.get("ticker"),
        "status": job["status"],
        "created_at": job.get("created_at"),
    }

    if job["status"] == "complete":
        response["result"] = job["result"]
        response["completed_at"] = job.get("completed_at")
    elif job["status"] == "failed":
        response["error"] = job.get("error")
        response["completed_at"] = job.get("completed_at")

    return response


@app.post("/api/analyze-batch")
def analyze_batch(req: BatchAnalyzeRequest, background_tasks: BackgroundTasks):
    """Start analysis for multiple tickers."""
    results = []
    for ticker in req.tickers[:10]:  # Cap at 10 tickers
        single_req = AnalyzeRequest(ticker=ticker, date=req.date, mode=req.mode)
        result = analyze(single_req, background_tasks)
        results.append(result)
    return {"jobs": results}


@app.post("/api/market-summary")
def market_summary(req: MarketSummaryRequest):
    """Generate AI market narrative from scored data."""
    try:
        from langchain_core.messages import HumanMessage

        config = get_ta_config()

        if config["llm_provider"] == "ollama":
            from langchain_community.chat_models import ChatOllama
            llm = ChatOllama(model=config["deep_think_llm"])
        elif config["llm_provider"] == "anthropic":
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model=config["deep_think_llm"])
        else:
            raise ValueError(f"Unsupported provider: {config['llm_provider']}")

        market_json = json.dumps(req.market_data, indent=2, default=str)

        prompt = f"""You are a senior market strategist at a proprietary trading firm. Analyze the following market data and provide a concise trading floor briefing.

Market Data:
{market_json}

Provide your response in this exact JSON format (no markdown, no backticks, just raw JSON):
{{
    "summary": "2-3 sentence overall market assessment",
    "bull_thesis": "Key bullish factors in 1-2 sentences",
    "bear_thesis": "Key bearish factors in 1-2 sentences",
    "key_risks": ["risk 1", "risk 2", "risk 3"],
    "recommendation": "One sentence actionable recommendation for swing traders"
}}"""

        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # Try to parse as JSON
        try:
            # Strip markdown fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(content)
            parsed["generated_at"] = datetime.utcnow().isoformat()
            parsed["model"] = config["deep_think_llm"]
            return parsed
        except json.JSONDecodeError:
            # Fallback: return raw text as summary
            return {
                "summary": content[:500],
                "bull_thesis": "",
                "bear_thesis": "",
                "key_risks": [],
                "recommendation": "",
                "generated_at": datetime.utcnow().isoformat(),
                "model": config["deep_think_llm"],
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI summary failed: {str(e)}")


@app.get("/api/cache/{ticker}")
def get_cached_analysis(ticker: str):
    """Get cached analysis for a ticker."""
    ticker = ticker.upper().strip()
    if ticker in analysis_cache:
        cached = analysis_cache[ticker]
        if time.time() - cached["cached_at"] < CACHE_TTL:
            return {"cached": True, "result": cached["result"]}
    raise HTTPException(status_code=404, detail="No cached analysis found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100, workers=1)
