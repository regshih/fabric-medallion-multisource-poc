import base64
import json
import re
from pathlib import Path

import pytest

from infra.fabric.definitions import bind_pipeline, notebook_definition

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "pipelines" / "pl_multisource_medallion.json"


def load_pipeline():
    return json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))


def test_notebook_definition_is_deterministic_and_decodable():
    first = notebook_definition("nb_test", "print('synthetic')")
    second = notebook_definition("nb_test", "print('synthetic')")
    assert first == second
    parts = {part["path"]: part for part in first["parts"]}
    assert base64.b64decode(parts["notebook-content.py"]["payload"]).decode() == "print('synthetic')"
    platform = json.loads(base64.b64decode(parts[".platform"]["payload"]))
    assert platform["metadata"] == {"type": "Notebook", "displayName": "nb_test"}


def test_pipeline_template_has_no_embedded_guids_and_binding_is_non_mutating():
    template = load_pipeline()
    original = json.dumps(template)
    names = {
        "nb_source_validation",
        "nb_silver_transform",
        "nb_gold_build",
        "nb_warehouse_publish",
        "nb_reconciliation",
        "nb_pipeline_log",
        "nb_gold_consumption_demo",
    }
    ids = {name: f"bound-{index}" for index, name in enumerate(sorted(names))}
    item_ids = {
        "databricks_source": "db-source", "cosmos_source": "cosmos-source",
        "silver_lh": "silver", "gold_lh": "gold", "gold_wh": "warehouse", "audit_lh": "audit",
    }
    item_names = {
        "silver_lh": "silver_lh", "gold_lh": "gold_lh", "gold_wh": "gold_wh",
        "databricks_schema": "banking_source",
        "cosmos_schema": "banking_poc",
    }
    bound = bind_pipeline(template, "bound-workspace", ids, item_ids, item_names)
    encoded = json.dumps(bound)
    assert "{{" not in encoded
    assert "bound-workspace" in encoded
    assert json.dumps(template) == original
    assert re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", original, re.I) is None


def test_unknown_binding_fails_closed():
    with pytest.raises(KeyError, match="Unresolved"):
        bind_pipeline({"id": "{{NOTEBOOK_ID:missing}}"}, "ws", {})


def test_pipeline_dependencies_and_failure_logging_cover_every_stage():
    activities = {a["name"]: a for a in load_pipeline()["properties"]["activities"]}
    assert {d["activity"] for d in activities["SilverTransform"]["dependsOn"]} == {
        "ValidateDatabricks", "ValidateCosmos"
    }
    assert activities["GoldBuild"]["dependsOn"][0]["activity"] == "SilverTransform"
    assert activities["WarehousePublish"]["dependsOn"][0]["activity"] == "GoldBuild"
    assert activities["Reconciliation"]["dependsOn"][0]["activity"] == "WarehousePublish"
    assert activities["LogPipelineSuccess"]["dependsOn"][0] == {
        "activity": "Reconciliation", "dependencyConditions": ["Succeeded"]
    }
    for stage in (
        "ValidateDatabricks", "ValidateCosmos", "SilverTransform", "GoldBuild",
        "WarehousePublish", "Reconciliation",
    ):
        handlers = [
            item for item in activities.values()
            if item["name"].startswith("Log")
            and {"activity": stage, "dependencyConditions": ["Failed"]} in item.get("dependsOn", [])
        ]
        assert len(handlers) == 1
        assert handlers[0]["typeProperties"]["parameters"]["raise_after_log"]["value"] is True


def test_every_notebook_activity_receives_shared_run_identity():
    activities = load_pipeline()["properties"]["activities"]
    for activity in activities:
        parameters = activity["typeProperties"]["parameters"]
        assert parameters["pipeline_run_id"]["value"] == "@pipeline().RunId"
        assert "pipeline().parameters.run_date" in parameters["run_date"]["value"]
        if activity["name"].startswith("Log"):
            assert parameters["workspace_id"]["value"] == "{{WORKSPACE_ID}}"
            assert parameters["audit_lakehouse_id"]["value"] == "{{ITEM_ID:audit_lh}}"
