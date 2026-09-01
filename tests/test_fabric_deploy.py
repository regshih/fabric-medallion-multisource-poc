import base64
import json

from infra.fabric.deploy import NOTEBOOK_NAMES, deploy


class FakeClient:
    def __init__(self):
        self.definitions = {}
        self.created = []

    def capacities(self):
        return [{"id": "capacity-guid", "displayName": "shared-capacity"}]

    def workspaces(self):
        return []

    def ensure_workspace(self, name, capacity_id, description):
        assert capacity_id == "capacity-guid"
        return {"id": "workspace-guid", "displayName": name, "capacityId": capacity_id}

    def items(self, workspace_id):
        return [
            {"id": "databricks-guid", "displayName": "db-mirror", "type": "MirroredAzureDatabricksCatalog"},
            {"id": "cosmos-guid", "displayName": "cosmos-mirror", "type": "MirroredDatabase"},
        ]

    def ensure_item(self, workspace_id, display_name, item_type, definition=None, **kwargs):
        item_id = f"id-{display_name}"
        self.created.append((display_name, item_type))
        if definition:
            self.definitions[display_name] = definition
        return {"id": item_id, "displayName": display_name, "type": item_type}


def test_deploy_binds_all_environment_ids_at_deploy_time(tmp_path, monkeypatch):
    notebook_dir = tmp_path / "notebooks"
    pipeline_dir = tmp_path / "pipelines"
    notebook_dir.mkdir()
    pipeline_dir.mkdir()
    for name in NOTEBOOK_NAMES:
        (notebook_dir / f"{name}.py").write_text(f"# {name}\n", encoding="utf-8")
    source_pipeline = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "pipelines" / "pl_multisource_medallion.json"
    )
    (pipeline_dir / source_pipeline.name).write_text(source_pipeline.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setenv("FABRIC_WORKSPACE_NAME", "test-workspace")
    monkeypatch.setenv("FABRIC_CAPACITY_NAME", "shared-capacity")
    monkeypatch.setenv("FABRIC_DATABRICKS_MIRROR_NAME", "db-mirror")
    monkeypatch.setenv("FABRIC_COSMOS_MIRROR_NAME", "cosmos-mirror")
    monkeypatch.setenv("DATABRICKS_SCHEMA", "banking_source")
    monkeypatch.setenv("COSMOS_DATABASE_NAME", "banking_poc")
    api = FakeClient()
    result = deploy(api, root=tmp_path)

    assert result["workspaceId"] == "workspace-guid"
    pipeline_definition = api.definitions["pl_multisource_medallion"]
    part = next(p for p in pipeline_definition["parts"] if p["path"] == "pipeline-content.json")
    bound = base64.b64decode(part["payload"]).decode()
    assert "{{" not in bound
    assert "workspace-guid" in bound
    assert "databricks-guid" in bound
    assert "cosmos-guid" in bound
    assert "id-silver_lh" in bound
    assert "id-gold_lh" in bound
    assert '"warehouse_name":{"value":"gold_wh"' in bound
    assert ("pl_multisource_medallion", "DataPipeline") in api.created
