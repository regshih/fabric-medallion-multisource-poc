#!/usr/bin/env python
"""Safely add a Gold device column constraint to a OneLake data access role.

The API is full-replace.  This helper GETs every role, preserves every role,
member, rule, row constraint, and unrelated column constraint, uses the GET
ETag for optimistic concurrency, and defaults to the service's dry-run mode.
``--apply`` first performs a server dry run, then submits the same replacement.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from infra.fabric.client import FabricApiError, FabricClient
    from infra.governance.common import item_by_name, workspace_id
else:
    from infra.fabric.client import FabricApiError, FabricClient
    from .common import item_by_name, workspace_id

ROOT = Path(__file__).resolve().parents[2]
log = logging.getLogger("fabric.governance.onelake_data_access")
ROLE_FIELDS = ("name", "kind", "decisionRules", "members")
TARGET_TABLE = "/Tables/DimDevice"
PERMITTED_DEVICE_COLUMNS = [
    "DeviceID", "CustomerID", "FirstSeen", "LastSeen", "Trusted", "OperatingSystem",
    "AppVersion", "RiskSignalsJSON", "GeoHistoryJSON", "DeviceSK", "pipeline_run_id",
    "run_date", "gold_loaded_at",
]


def _is_read_rule(rule: dict[str, Any]) -> bool:
    for scope in rule.get("permission", []):
        if scope.get("attributeName") == "Action" and "Read" in scope.get("attributeValueIncludedIn", []):
            return True
    return False


def build_replacement(roles: list[dict[str, Any]], role_name: str = "DefaultReader") -> dict[str, Any]:
    replacement = copy.deepcopy(roles)
    targets = [role for role in replacement if role.get("name") == role_name]
    if len(targets) != 1:
        raise FabricApiError(f"Expected exactly one data access role named {role_name!r}; found {len(targets)}")
    changed = 0
    for rule in targets[0].get("decisionRules", []):
        if not _is_read_rule(rule):
            continue
        constraints = rule.setdefault("constraints", {})
        columns = constraints.setdefault("columns", [])
        columns[:] = [entry for entry in columns if entry.get("tablePath") != TARGET_TABLE]
        columns.append({
            "tablePath": TARGET_TABLE,
            "columnNames": PERMITTED_DEVICE_COLUMNS,
            "columnEffect": "Permit",
            "columnAction": ["Read"],
        })
        changed += 1
    if changed == 0:
        raise FabricApiError(f"Role {role_name!r} has no Read decision rule")
    # Server-assigned IDs are not part of the create/update request.  All
    # writable role fields, including unknown nested members/rules, survive.
    return {"value": [{key: role[key] for key in ROLE_FIELDS if key in role} for role in replacement]}


def update(client: FabricClient, workspace: str, item_id: str, *, apply: bool, role_name: str) -> dict[str, Any]:
    path = f"workspaces/{workspace}/items/{item_id}/dataAccessRoles"
    current = client.request("GET", path)
    etag = current.headers.get("ETag") or current.headers.get("Etag")
    if not etag:
        raise FabricApiError("Data access role GET did not return an ETag; refusing a full replacement")
    payload = build_replacement(current.json().get("value", []), role_name)
    headers = {"If-Match": etag}
    client.request("PUT", f"{path}?dryRun=true", json=payload, headers=headers)
    log.info("server dry run succeeded; existing roles and unrelated constraints were preserved")
    if apply:
        response = client.request("PUT", path, json=payload, headers=headers)
        log.info("full replacement applied with If-Match concurrency protection")
        return {"applied": True, "etag": response.headers.get("ETag") or response.headers.get("Etag")}
    return {"applied": False, "etag": etag, "payload": payload}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply after the mandatory server dry run")
    parser.add_argument("--role-name", default="DefaultReader")
    parser.add_argument("--lakehouse-name", default="", help="defaults to FABRIC_GOLD_LAKEHOUSE_NAME")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    client = FabricClient()
    workspace = workspace_id(client)
    lakehouse_name = args.lakehouse_name or os.getenv("FABRIC_GOLD_LAKEHOUSE_NAME", "gold_lh")
    item = item_by_name(client, workspace, lakehouse_name, "Lakehouse")
    print(json.dumps(update(client, workspace, str(item["id"]), apply=args.apply, role_name=args.role_name), indent=2))


if __name__ == "__main__":
    main()

