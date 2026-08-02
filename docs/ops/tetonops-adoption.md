# TetonOps adoption

PCC TradingAgents is an active, database-free TetonOps consumer. Its canonical
identifier is `trading-agents`; the shared operational interface is:

```text
tetondeploy trading-agents capabilities
tetondeploy trading-agents status
tetondeploy trading-agents preflight
tetondeploy trading-agents activate FULL_COMMIT
tetondeploy trading-agents verify
tetondb trading-agents capabilities
tetondb trading-agents health
```

Database commands return `status=not-configured`. SQLite checkpoint files and
the decision log are application state, not a generic database authority lane.
The repository owns only its manifest, service/health declaration, migration
inventory, and application tests. Shared packaging, gates, authorization,
evidence, release switching, and operations behavior live in TetonOperations.

This branch registers the project but does not install or activate TetonOps,
change the sidecar service, or alter credentials. Those remain owner-gated.
