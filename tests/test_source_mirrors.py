import base64
import json

from infra.fabric.source_mirrors import cosmos_definition, definition_part, enabled


def test_cosmos_definition_is_deterministic_and_binds_only_connection_metadata():
    first = cosmos_definition("cosmos_bronze", "connection-id", "banking_poc")
    second = cosmos_definition("cosmos_bronze", "connection-id", "banking_poc")
    assert first == second
    parts = {part["path"]: part for part in first["parts"]}
    mirroring = json.loads(base64.b64decode(parts["mirroring.json"]["payload"]))
    assert mirroring["properties"]["source"]["typeProperties"] == {
        "connection": "connection-id",
        "database": "banking_poc",
    }
    assert "credential" not in json.dumps(first).lower()
    assert definition_part(first, "mirroring.json")["properties"]["source"]["typeProperties"] == {
        "connection": "connection-id",
        "database": "banking_poc",
    }


def test_destructive_recreate_flag_is_explicit(monkeypatch):
    monkeypatch.delenv("FABRIC_ALLOW_DATABRICKS_MIRROR_RECREATE", raising=False)
    assert not enabled("FABRIC_ALLOW_DATABRICKS_MIRROR_RECREATE")
    monkeypatch.setenv("FABRIC_ALLOW_DATABRICKS_MIRROR_RECREATE", "true")
    assert enabled("FABRIC_ALLOW_DATABRICKS_MIRROR_RECREATE")
