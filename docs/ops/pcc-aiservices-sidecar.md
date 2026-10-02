# PCC TradingAgents Sidecar — pcc-aiservices-01

## Reproducible sidecar installation

The sidecar has a declared optional dependency group. On Ubuntu 26, the
recovered stack was validated with Python 3.14.4, FastAPI 0.139.0,
Starlette 1.3.1, and Uvicorn 0.50.0. FastAPI and Uvicorn are pinned in
`sidecar`; Starlette is resolved through FastAPI's `starlette>=0.46.0`
dependency rather than independently pinned. This is a sidecar dependency
contract, not a lock of the framework's entire transitive dependency graph.

From a clean repository checkout, create a new environment without touching
the active service environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[sidecar]'
.venv/bin/python -m pip check
.venv/bin/python tests/sidecar_dependency_smoke.py
```

The smoke check imports the installed sidecar and exercises `/api/health`
in-process. It performs no analysis, inference, broker, or network calls.
The `pcc_wrapper` package is included in distribution discovery so imports
also work outside the repository directory. Service configuration changes
and activation of a replacement environment remain separate owner gates.

## Runtime endpoints

TradingAgents runs as an advisory-only FastAPI sidecar on:

- Host: pcc-aiservices-01
- IP: 10.86.1.12
- Port: 8100
- Health: http://10.86.1.12:8100/api/health
- Systemd service: pcc-tradingagents-sidecar.service

## LLM provider

Local inference is provided by Ollama on pcc-aiservices-01:

- Ollama URL: http://10.86.1.12:11434
- Current installed/default model: llama3.2:3b

## Environment file

Runtime environment is stored outside git:

- /etc/pcc-tradingagents/sidecar.env

Current intended values:

PCC_LLM_MODE=production_local
OLLAMA_HOST=http://10.86.1.12:11434
QUICK_THINK_LLM=llama3.2:3b
DEEP_THINK_LLM=llama3.2:3b

## Security boundary

TradingAgents is advisory only.

It must not hold broker credentials, order execution authority, or ProtectedOrderOrchestrator authority. Production trading execution remains outside this sidecar.

## Network

MissionControl app host pcc-app-01 reaches the sidecar at:

- http://10.86.1.12:8100

Firewall should allow port 8100 only from approved internal application hosts.
