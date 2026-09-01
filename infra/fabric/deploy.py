#!/usr/bin/env python
"""Idempotently deploy the POC workspace, data items, notebooks, and pipeline.

This script authenticates with Azure CLI/Entra through DefaultAzureCredential.
It does not provision or resize an Azure capacity.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from infra.fabric.client import FabricApiError, FabricClient
    from infra.fabric.definitions import bind_pipeline, notebook_definition, pipeline_definition
else:
    from .client import FabricApiError, FabricClient
    from .definitions import bind_pipeline, notebook_definition, pipeline_definition

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_NAME = "pl_multisource_medallion"
NOTEBOOK_NAMES = (
    "nb_source_validation",
    "nb_silver_transform",
    "nb_gold_build",
    "nb_warehouse_publish",
    "nb_reconciliation",
    "nb_pipeline_log",
    "nb_gold_consumption_demo",
)

log = logging.getLogger("fabric.deploy")


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or (value.startswith("<") and value.endswith(">")):
        raise RuntimeError(f"Set {name} to a real identifier before deployment")
    return value


def resolve_capacity_id(client: FabricClient) -> str:
    configured_id = os.getenv("FABRIC_CAPACITY_ID", "").strip()
    configured_name = os.getenv("FABRIC_CAPACITY_NAME", "").strip()
    capacities = client.capacities()
    for capacity in capacities:
        if configured_id and capacity.get("id", "").lower() == configured_id.lower():
            return str(capacity["id"])
        if configured_name and capacity.get("displayName", "").lower() == configured_name.lower():
            return str(capacity["id"])
        if configured_id and configured_id.rstrip("/").split("/")[-1].lower() == str(
            capacity.get("displayName", "")
        ).lower():
            return str(capacity["id"])
    requested = configured_name or configured_id or "(none configured)"
    raise FabricApiError(f"Fabric capacity {requested!r} is not visible to the signed-in identity")


def load_notebooks(directory: Path = ROOT / "notebooks") -> dict[str, str]:
    missing = [name for name in NOTEBOOK_NAMES if not (directory / f"{name}.py").is_file()]
    if missing:
        raise FileNotFoundError(f"Required notebook sources are missing: {', '.join(missing)}")
    return {name: (directory / f"{name}.py").read_text(encoding="utf-8") for name in NOTEBOOK_NAMES}


def source_item_ids(client: FabricClient, workspace_id: str) -> dict[str, str]:
    """Resolve preconfigured mirrored source items by name, regardless of mirror subtype."""
    requested = {
        "databricks_source": (
            required_env("FABRIC_DATABRICKS_MIRROR_NAME"),
            "MirroredAzureDatabricksCatalog",
        ),
        "cosmos_source": (required_env("FABRIC_COSMOS_MIRROR_NAME"), "MirroredDatabase"),
    }
    visible = client.items(workspace_id)
    result: dict[str, str] = {}
    for key, (display_name, item_type) in requested.items():
        matches = [
            item
            for item in visible
            if item.get("displayName") == display_name and item.get("type") == item_type
        ]
        if len(matches) != 1:
            raise FabricApiError(
                f"Expected exactly one Fabric source item named {display_name!r}; found {len(matches)}"
            )
        result[key] = str(matches[0]["id"])
    return result


def deploy(client: FabricClient, *, root: Path = ROOT) -> dict[str, Any]:
    workspace_name = required_env("FABRIC_WORKSPACE_NAME")
    capacity_id = resolve_capacity_id(client)
    workspace = client.ensure_workspace(
        workspace_name,
        capacity_id,
        "Synthetic banking multisource medallion POC using Databricks and Cosmos DB.",
    )
    workspace_id = str(workspace.get("id", ""))
    if not workspace_id:
        raise FabricApiError("Workspace creation did not return an item ID")

    names = {
        "silver_lh": os.getenv("FABRIC_SILVER_LAKEHOUSE_NAME", "silver_lh"),
        "gold_lh": os.getenv("FABRIC_GOLD_LAKEHOUSE_NAME", "gold_lh"),
        "gold_wh": os.getenv("FABRIC_WAREHOUSE_NAME", "gold_wh"),
        "databricks_schema": required_env("DATABRICKS_SCHEMA"),
        "cosmos_schema": required_env("COSMOS_DATABASE_NAME"),
    }
    items: dict[str, str] = {}
    for key in ("silver_lh", "gold_lh"):
        item = client.ensure_item(
            workspace_id, names[key], "Lakehouse", description=f"{key.split('_')[0].title()} medallion layer"
        )
        items[key] = str(item["id"])
    warehouse = client.ensure_item(
        workspace_id, names["gold_wh"], "Warehouse", description="Governed Gold SQL serving layer"
    )
    items["gold_wh"] = str(warehouse["id"])
    items.update(source_item_ids(client, workspace_id))

    notebook_ids: dict[str, str] = {}
    for display_name, source in load_notebooks(root / "notebooks").items():
        item = client.ensure_item(
            workspace_id,
            display_name,
            "Notebook",
            notebook_definition(display_name, source),
            description=f"POC automation notebook: {display_name}",
        )
        notebook_ids[display_name] = str(item["id"])

    template_path = root / "pipelines" / f"{PIPELINE_NAME}.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    pipeline_item_ids = {
        **items,
        # Audit Delta tables live in Gold for this POC; no empty audit-only
        # Lakehouse is created merely for architectural symmetry.
        "audit_lh": items["gold_lh"],
    }
    bound = bind_pipeline(template, workspace_id, notebook_ids, pipeline_item_ids, names)
    pipeline = client.ensure_item(
        workspace_id,
        PIPELINE_NAME,
        "DataPipeline",
        pipeline_definition(PIPELINE_NAME, bound),
        description="Validates both sources and builds Silver, Gold, Warehouse, and reconciliation outputs",
    )
    items.update(notebook_ids)
    items[PIPELINE_NAME] = str(pipeline["id"])
    return {"workspaceId": workspace_id, "capacityId": capacity_id, "items": items}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Run the pipeline after deployment")
    parser.add_argument("--run-date", default="", help="Optional ISO run date (YYYY-MM-DD)")
    parser.add_argument("--job-timeout", type=float, default=43200)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = FabricClient(job_timeout=args.job_timeout)
    result = deploy(client)
    if args.run:
        payload = (
            {"executionData": {"parameters": {"run_date": args.run_date}}} if args.run_date else None
        )
        run = client.run_item(
            result["workspaceId"], result["items"][PIPELINE_NAME], "Pipeline", payload
        )
        result["run"] = run
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
