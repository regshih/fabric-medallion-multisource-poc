"""Shared identifier resolution for Fabric governance scripts."""
from __future__ import annotations

import os
from typing import Any

from infra.fabric.client import FabricApiError, FabricClient


def configured(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or (value.startswith("<") and value.endswith(">")):
        raise RuntimeError(f"Set {name} to a real deploy-time identifier")
    return value


def workspace_id(client: FabricClient) -> str:
    explicit = os.getenv("FABRIC_WORKSPACE_ID", "").strip()
    if explicit and not (explicit.startswith("<") and explicit.endswith(">")):
        return explicit
    name = configured("FABRIC_WORKSPACE_NAME")
    workspace = client._named(client.workspaces(), name)
    if not workspace:
        raise FabricApiError(f"Fabric workspace {name!r} is not visible")
    return str(workspace["id"])


def item_by_name(
    client: FabricClient, workspace: str, display_name: str, item_type: str | None = None
) -> dict[str, Any]:
    item = client._named(client.items(workspace), display_name, item_type)
    if not item:
        suffix = f" ({item_type})" if item_type else ""
        raise FabricApiError(f"Fabric item {display_name!r}{suffix} is not visible")
    return item

