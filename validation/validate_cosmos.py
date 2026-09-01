#!/usr/bin/env python3
"""Validate generated files or a live Cosmos DB source and emit JSON evidence."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cosmos.common import CONTAINERS, read_jsonl

ID_PATTERNS = {
    "digitalSessions": re.compile(r"^SESSION-(?:\d{9}|INC-\d{6})$"),
    "devices": re.compile(r"^DEVICE-\d{6}$"),
    "fraudAlerts": re.compile(r"^ALERT-(?:\d{8}|INC-\d{6})$"),
}
CUSTOMER_PATTERN = re.compile(r"^CUST-\d{6}$")
TRANSACTION_PATTERN = re.compile(r"^TXN-\d{9}$")


def _timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None
    except ValueError:
        return False


def validate_documents(documents: dict[str, list[dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    device_lookup = {d.get("deviceId"): d for d in documents.get("devices", [])}
    seen: dict[str, set[tuple[str, str]]] = {name: set() for name in CONTAINERS}

    for container in CONTAINERS:
        for index, doc in enumerate(documents.get(container, []), 1):
            prefix = f"{container}[{index}]"
            identity = (doc.get("id"), doc.get("customerId"))
            if identity in seen[container]:
                errors.append(f"{prefix}: duplicate id/partition pair {identity}")
            seen[container].add(identity)
            if not ID_PATTERNS[container].match(str(doc.get("id", ""))):
                errors.append(f"{prefix}: invalid id")
            if not CUSTOMER_PATTERN.match(str(doc.get("customerId", ""))):
                errors.append(f"{prefix}: invalid customerId")
            if doc.get("synthetic") is not True:
                errors.append(f"{prefix}: synthetic marker must be true")

            if container == "digitalSessions":
                device = doc.get("device")
                auth = doc.get("authentication")
                if not isinstance(device, dict) or not device.get("deviceId"):
                    errors.append(f"{prefix}: nested device.deviceId is required")
                if not isinstance(auth, dict) or not isinstance(auth.get("failedAttempts"), int):
                    errors.append(f"{prefix}: authentication.failedAttempts must be an integer")
                if not isinstance(doc.get("activities"), list):
                    errors.append(f"{prefix}: activities must be an array")
                if not _timestamp(doc.get("loginTimestamp")):
                    errors.append(f"{prefix}: invalid loginTimestamp")
                if not isinstance(doc.get("sessionRiskScore"), int) or not 0 <= doc["sessionRiskScore"] <= 100:
                    errors.append(f"{prefix}: sessionRiskScore must be 0..100")
                linked = device_lookup.get(device.get("deviceId")) if isinstance(device, dict) else None
                if linked is not None and linked.get("customerId") != doc.get("customerId"):
                    errors.append(f"{prefix}: device/customer relationship mismatch")

            elif container == "devices":
                if doc.get("id") != doc.get("deviceId"):
                    errors.append(f"{prefix}: id and deviceId must match")
                if not isinstance(doc.get("operatingSystem"), dict):
                    errors.append(f"{prefix}: operatingSystem must be an object")
                if not isinstance(doc.get("riskSignals"), list) or not isinstance(doc.get("geoHistory"), list):
                    errors.append(f"{prefix}: riskSignals and geoHistory must be arrays")
                if not _timestamp(doc.get("lastSeen")):
                    errors.append(f"{prefix}: invalid lastSeen")

            elif container == "fraudAlerts":
                if doc.get("id") != doc.get("alertId"):
                    errors.append(f"{prefix}: id and alertId must match")
                if not TRANSACTION_PATTERN.match(str(doc.get("transactionId", ""))):
                    errors.append(f"{prefix}: transactionId is not a conformed cross-source key")
                if not isinstance(doc.get("signals"), list):
                    errors.append(f"{prefix}: signals must be an array")
                if doc.get("status") not in {"open", "investigating", "resolved"}:
                    errors.append(f"{prefix}: invalid status")
                if doc.get("status") == "resolved" and not isinstance(doc.get("resolution"), dict):
                    errors.append(f"{prefix}: resolved alert requires resolution")
                if not _timestamp(doc.get("createdTimestamp")):
                    errors.append(f"{prefix}: invalid createdTimestamp")
    return errors


def load_files(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    return {container: list(read_jsonl(data_dir / f"{container}.jsonl")) for container in CONTAINERS}


def validate_files(data_dir: Path) -> dict[str, Any]:
    documents = load_files(data_dir)
    errors = validate_documents(documents)
    return {
        "mode": "files",
        "source": str(data_dir),
        "partitionKey": "/customerId",
        "counts": {name: len(docs) for name, docs in documents.items()},
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }


def validate_live(endpoint: str, database_name: str, *, subscription_id: str | None = None, resource_group: str | None = None, account_name: str | None = None) -> dict[str, Any]:
    try:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install repository requirements before live validation") from exc

    credential = DefaultAzureCredential()
    client = CosmosClient(endpoint, credential=credential)
    database = client.get_database_client(database_name)
    checks: list[dict[str, Any]] = []
    all_documents: dict[str, list[dict[str, Any]]] = {}
    try:
        for name in CONTAINERS:
            container = database.get_container_client(name)
            properties = container.read()
            partition_paths = properties.get("partitionKey", {}).get("paths", [])
            checks.append({"check": f"{name}.partitionKey", "expected": ["/customerId"], "actual": partition_paths, "status": "PASS" if partition_paths == ["/customerId"] else "FAIL"})
            docs = list(container.query_items("SELECT * FROM c", enable_cross_partition_query=True))
            all_documents[name] = docs
            checks.append({"check": f"{name}.count", "actual": len(docs), "status": "PASS" if docs else "FAIL"})
    finally:
        client.close()

    document_errors = validate_documents(all_documents)
    checks.append({"check": "documentContract", "errorCount": len(document_errors), "status": "PASS" if not document_errors else "FAIL", "errors": document_errors[:25]})

    if all((subscription_id, resource_group, account_name)):
        try:
            from azure.mgmt.cosmosdb import CosmosDBManagementClient
            management = CosmosDBManagementClient(credential, subscription_id)
            account = management.database_accounts.get(resource_group, account_name)
            mode = getattr(account.backup_policy, "type", None)
            checks.append({"check": "continuousBackup", "expected": "Continuous", "actual": mode, "status": "PASS" if mode == "Continuous" else "FAIL"})
        except Exception as exc:  # report inability without hiding it
            checks.append({"check": "continuousBackup", "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
    else:
        checks.append({"check": "continuousBackup", "status": "NOT_RUN", "notes": "Pass subscription, resource group, and account to verify the Mirroring prerequisite."})

    credential.close()
    failed = [check for check in checks if check["status"] == "FAIL"]
    return {"mode": "live", "endpoint": endpoint, "database": database_name, "status": "PASS" if not failed else "FAIL", "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("files", "live"), default="files")
    parser.add_argument("--data-dir", type=Path, default=Path("data/cosmos/initial"))
    parser.add_argument("--endpoint", default=os.environ.get("COSMOS_ENDPOINT"))
    parser.add_argument("--database-name", default=os.environ.get("COSMOS_DATABASE_NAME", "banking_poc"))
    parser.add_argument("--subscription-id", default=os.environ.get("AZURE_SUBSCRIPTION_ID"))
    parser.add_argument("--resource-group", default=os.environ.get("AZURE_RESOURCE_GROUP"))
    parser.add_argument("--account-name", default=os.environ.get("COSMOS_ACCOUNT_NAME"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "live":
        if not args.endpoint:
            parser.error("--endpoint or COSMOS_ENDPOINT is required in live mode")
        result = validate_live(args.endpoint, args.database_name, subscription_id=args.subscription_id, resource_group=args.resource_group, account_name=args.account_name)
    else:
        result = validate_files(args.data_dir)
    output = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
