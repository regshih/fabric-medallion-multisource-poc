#!/usr/bin/env python
"""Set catalog-facing descriptions and optionally assign the workspace domain.

The command is a dry run unless ``--apply`` is supplied.  Domain assignment
uses a deploy-time domain ID because listing/creating tenant domains requires
broader admin permissions than assignment to an existing domain.
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from infra.fabric.client import FabricClient
    from infra.governance.common import workspace_id
else:
    from infra.fabric.client import FabricClient
    from .common import workspace_id

ROOT = Path(__file__).resolve().parents[2]
log = logging.getLogger("fabric.governance.catalog_setup")

DESCRIPTIONS = {
    "databricks_bronze": "Source-aligned Azure Databricks Unity Catalog integration for synthetic transaction, risk-score, and merchant Delta data.",
    "cosmos_bronze": "Source-aligned Fabric mirror of synthetic Cosmos DB digital sessions, devices, and fraud alerts.",
    "silver_lh": "Conformed and quality-checked multisource Silver Delta tables, with nested Cosmos fields flattened and rejected records quarantined.",
    "gold_lh": "Gold star schema and cross-source customer fraud-risk aggregates for Direct Lake and governed SQL consumption.",
    "gold_wh": "Governed SQL serving layer over Gold, combining zero-copy views with local security-bearing copies for supported RLS and DDM.",
    "pl_multisource_medallion": "Orchestrates source validation, Silver and Gold builds, Warehouse publication, reconciliation, and run logging.",
    "nb_source_validation": "Validates Databricks and Cosmos source-aligned objects and records source-stage audit metrics.",
    "nb_silver_transform": "Standardizes, deduplicates, validates, and quarantines multisource records into Silver Delta tables.",
    "nb_gold_build": "Builds Gold dimensions, facts, and the cross-source AggCustomerRiskProfile analytical model.",
    "nb_warehouse_publish": "Publishes the ordered Warehouse refresh contract after the Gold Lakehouse build.",
    "nb_reconciliation": "Reconciles source, Silver, quarantine, Gold, cross-source, and incremental-change results.",
    "nb_gold_consumption_demo": "Demonstrates customer-risk and fraud investigations across Databricks and Cosmos-derived Gold data.",
    "nb_pipeline_log": "Writes idempotent success and failure stage records for the multisource pipeline run.",
}

assert all(len(value) <= 256 for value in DESCRIPTIONS.values())


def planned_updates(items: list[dict], force: bool = False) -> list[tuple[str, str]]:
    updates = []
    for item in items:
        description = DESCRIPTIONS.get(str(item.get("displayName", "")))
        if description and (force or item.get("description") != description):
            updates.append((str(item["id"]), description))
    return updates


def apply_descriptions(client: FabricClient, workspace: str, *, force: bool, apply: bool) -> int:
    items = client.items(workspace)
    updates = planned_updates(items, force)
    for item_id, description in updates:
        item = next(value for value in items if str(value["id"]) == item_id)
        if apply:
            client.request(
                "PATCH", f"workspaces/{workspace}/items/{item_id}", json={"description": description}
            )
        log.info("%s description: %s", "updated" if apply else "would update", item["displayName"])
    return len(updates)


def assign_domain(client: FabricClient, workspace: str, domain_id: str, *, apply: bool) -> None:
    if not domain_id or (domain_id.startswith("<") and domain_id.endswith(">")):
        raise RuntimeError("Set FABRIC_DOMAIN_ID or pass --domain-id")
    if apply:
        client.request("POST", f"workspaces/{workspace}/assignToDomain", json={"domainId": domain_id})
    log.info("%s workspace assignment to configured Retail Banking Analytics domain", "applied" if apply else "would apply")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform changes; otherwise print a dry-run plan")
    parser.add_argument("--force", action="store_true", help="rewrite descriptions even when already equal")
    parser.add_argument("--assign-domain", action="store_true", help="assign an existing domain")
    parser.add_argument("--domain-id", default="", help="existing domain ID; defaults to FABRIC_DOMAIN_ID")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    client = FabricClient()
    workspace = workspace_id(client)
    count = apply_descriptions(client, workspace, force=args.force, apply=args.apply)
    log.info("%d description change(s) %s", count, "applied" if args.apply else "planned")
    if args.assign_domain:
        assign_domain(client, workspace, args.domain_id or os.getenv("FABRIC_DOMAIN_ID", ""), apply=args.apply)


if __name__ == "__main__":
    main()

