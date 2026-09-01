"""Shared passwordless Cosmos DB loader utilities."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

CONTAINERS = ("digitalSessions", "devices", "fraudAlerts")


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                document = json.loads(line)
                if not document.get("id") or not document.get("customerId"):
                    raise ValueError(f"{path}:{line_number}: id and customerId are required")
                yield document


def load_directory(data_dir: Path, *, endpoint: str | None = None, database_name: str | None = None) -> dict[str, int]:
    """Upsert one batch using Microsoft Entra credentials; safe to rerun."""
    try:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:  # pragma: no cover - depends on optional runtime packages
        raise RuntimeError("Install repository requirements before loading Cosmos DB") from exc

    endpoint = endpoint or os.environ.get("COSMOS_ENDPOINT")
    database_name = database_name or os.environ.get("COSMOS_DATABASE_NAME", "banking_poc")
    if not endpoint:
        raise ValueError("Set COSMOS_ENDPOINT or pass --endpoint; account keys are intentionally unsupported")

    credential = DefaultAzureCredential()
    client = CosmosClient(endpoint, credential=credential)
    database = client.get_database_client(database_name)
    counts: dict[str, int] = {}
    try:
        for container_name in CONTAINERS:
            path = data_dir / f"{container_name}.jsonl"
            container = database.get_container_client(container_name)
            count = 0
            for document in read_jsonl(path):
                container.upsert_item(document)
                count += 1
            counts[container_name] = count
    finally:
        client.close()
        credential.close()
    return counts
