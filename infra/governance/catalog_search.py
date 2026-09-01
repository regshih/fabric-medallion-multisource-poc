#!/usr/bin/env python
"""Search OneLake Catalog and optionally limit output to the POC workspace."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
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
ITEM_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")


def search(client: FabricClient, text: str, item_type: str | None, page_size: int) -> list[dict]:
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000")
    body: dict[str, object] = {"search": text, "pageSize": page_size}
    if item_type:
        if not ITEM_TYPE.fullmatch(item_type):
            raise ValueError("item_type must contain only letters and digits")
        body["filter"] = f"Type eq '{item_type}'"
    results: list[dict] = []
    while True:
        response = client.request("POST", "catalog/search", json=body).json()
        results.extend(response.get("value", []))
        token = response.get("continuationToken")
        if not token:
            return results
        body["continuationToken"] = token


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search", default="multisource", help="full-text catalog query")
    parser.add_argument("--type", dest="item_type", help="optional Fabric item type")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--all-workspaces", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    client = FabricClient()
    entries = search(client, args.search, args.item_type, args.page_size)
    if not args.all_workspaces:
        expected = workspace_id(client)
        entries = [e for e in entries if e.get("hierarchy", {}).get("workspace", {}).get("id") == expected]
    print(json.dumps(entries, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

