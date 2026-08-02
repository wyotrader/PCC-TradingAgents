import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tetonops_manifest_is_database_free_and_pinned() -> None:
    manifest = json.loads(
        (ROOT / "operations/tetonops/project.json").read_text(encoding="utf-8")
    )
    assert manifest["contractVersion"] == "1.0"
    assert manifest["project"] == "trading-agents"
    assert manifest["database"] is None
    assert manifest["deployment"]["host"] == "pcc-aiservices-01"
    assert manifest["deployment"]["runtimeServices"] == [
        "pcc-tradingagents-sidecar.service"
    ]
    assert manifest["requiredTetonOps"] == {
        "minimumVersion": "1.0.0",
        "manifestContract": "1.0",
        "queryPackContract": "1.0",
        "migrationInventoryContract": "1.0",
        "outputContract": "1.0",
    }


def test_tetonops_inventory_contains_no_executable_hooks() -> None:
    manifest = json.loads(
        (ROOT / "operations/tetonops/project.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(manifest, sort_keys=True).lower()
    for prohibited in (
        "executablehook", "shell", "connectionstring", "sudoers", "sqlartifact"
    ):
        assert prohibited not in serialized
