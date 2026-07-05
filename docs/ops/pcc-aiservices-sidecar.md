# PCC TradingAgents Sidecar — pcc-aiservices-01

## Runtime

TradingAgents runs as an advisory-only FastAPI sidecar on:

- Host: pcc-aiservices-01
- IP: 192.168.86.6
- Port: 8100
- Health: http://192.168.86.6:8100/api/health
- Systemd service: pcc-tradingagents-sidecar.service

## LLM provider

Local inference is provided by Ollama on pcc-aiservices-01:

- Ollama URL: http://192.168.86.6:11434
- Current installed/default model: llama3.2:3b

## Environment file

Runtime environment is stored outside git:

- /etc/pcc-tradingagents/sidecar.env

Current intended values:

PCC_LLM_MODE=production_local
OLLAMA_HOST=http://192.168.86.6:11434
QUICK_THINK_LLM=llama3.2:3b
DEEP_THINK_LLM=llama3.2:3b

## Security boundary

TradingAgents is advisory only.

It must not hold broker credentials, order execution authority, or ProtectedOrderOrchestrator authority. Production trading execution remains outside this sidecar.

## Network

MissionControl app host pcc-app-01 reaches the sidecar at:

- http://192.168.86.6:8100

Firewall should allow port 8100 only from approved internal application hosts.
