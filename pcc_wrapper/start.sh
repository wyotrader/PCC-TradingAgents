#!/bin/bash
cd ~/TradingAgents
source venv/bin/activate
export PCC_LLM_MODE="${1:-dev}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
echo "Starting PCC TradingAgents Sidecar in $PCC_LLM_MODE mode..."
python -m uvicorn pcc_wrapper.server:app --host 0.0.0.0 --port 8100 --workers 1
