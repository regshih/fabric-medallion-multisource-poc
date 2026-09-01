#!/usr/bin/env python3
"""Idempotently create the Databricks catalog and Cosmos Bronze source items."""
from __future__ import annotations

import base64
import json
import os
import time
import uuid

from dotenv import load_dotenv

from infra.fabric.client import FabricApiError, FabricClient


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.startswith("<"):
        raise RuntimeError(f"Set {name} before creating source mirrors")
    return value


def encoded(value: dict) -> str:
    return base64.b64encode(json.dumps(value, separators=(",", ":")).encode()).decode()


def enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def definition_part(definition: dict, path: str) -> dict:
    parts = definition.get("definition", definition).get("parts", [])
    part = next((value for value in parts if value.get("path") == path), None)
    if not part:
        raise FabricApiError(f"Fabric item definition is missing {path!r}")
    try:
        return json.loads(base64.b64decode(part["payload"]))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise FabricApiError(f"Fabric item definition part {path!r} is invalid") from exc


def get_definition(client: FabricClient, workspace_id: str, item_id: str) -> dict:
    response = client.request(
        "POST", f"workspaces/{workspace_id}/items/{item_id}/getDefinition", json={}
    )
    return client.wait_for_operation(response)


def ensure_databricks(client: FabricClient, workspace_id: str) -> dict:
    name = required("FABRIC_DATABRICKS_MIRROR_NAME")
    catalog = required("DATABRICKS_CATALOG")
    databricks_connection_id = required("FABRIC_DATABRICKS_CONNECTION_ID")
    storage_connection_id = required("FABRIC_DATABRICKS_STORAGE_CONNECTION_ID")
    path = f"workspaces/{workspace_id}/mirroredAzureDatabricksCatalogs"
    existing = client._named(client.list_all(path), name)
    existing_properties = existing.get("properties", {}) if existing else {}
    immutable_drift = existing and (
        existing_properties.get("databricksWorkspaceConnectionId") != databricks_connection_id
        or existing_properties.get("catalogName", catalog) != catalog
    )
    if immutable_drift:
        if not enabled("FABRIC_ALLOW_DATABRICKS_MIRROR_RECREATE"):
            raise FabricApiError(
                "The Databricks connection on an existing mirror is immutable. Set "
                "FABRIC_ALLOW_DATABRICKS_MIRROR_RECREATE=true to replace the metadata-only item."
            )
        response = client.request("DELETE", f"{path}/{existing['id']}")
        client.wait_for_operation(response)
        for _ in range(30):
            if not client._named(client.list_all(path), name):
                break
            time.sleep(2)
        else:
            raise FabricApiError("Timed out waiting for the prior Databricks mirror to be removed")
        existing = None
    if not existing:
        response = client.request(
            "POST",
            path,
            json={
                "displayName": name,
                "description": "Source-aligned Bronze Unity Catalog metadata mirror with zero-copy Delta shortcuts.",
                "creationPayload": {
                    "catalogName": catalog,
                    "databricksWorkspaceConnectionId": databricks_connection_id,
                    "mirroringMode": "Full",
                    "storageConnectionId": storage_connection_id,
                },
            },
        )
        client.wait_for_operation(response)
        existing = client._named(client.list_all(path), name)
    if not existing:
        raise FabricApiError("Databricks mirrored catalog was not visible after creation")
    properties = existing.get("properties", {})
    if (
        properties.get("storageConnectionId") != storage_connection_id
        or properties.get("autoSync") != "Enabled"
    ):
        response = client.request(
            "PATCH",
            f"{path}/{existing['id']}",
            json={
                "displayName": name,
                "description": existing.get("description", ""),
                "properties": {
                    "storageConnectionId": storage_connection_id,
                    "mirroringMode": "Full",
                    "autoSync": "Enabled",
                }
            },
        )
        client.wait_for_operation(response)
        existing = client._named(client.list_all(path), name) or existing
    if existing.get("properties", {}).get("mirrorStatus") != "Mirrored":
        response = client.request(
            "POST", f"{path}/{existing['id']}/refreshCatalogMetadata", json={}
        )
        client.wait_for_operation(response)
        existing = client.request("GET", f"{path}/{existing['id']}").json()
    return existing


def cosmos_definition(name: str, connection_id: str, database: str) -> dict:
    logical_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fabric-mirror:{name}"))
    mirroring = {
        "properties": {
            "source": {
                "type": "CosmosDb",
                "typeProperties": {"connection": connection_id, "database": database},
            },
            "target": {
                "type": "MountedRelationalDatabase",
                "typeProperties": {"defaultSchema": "dbo", "format": "Delta"},
            },
        }
    }
    platform = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "MirroredDatabase", "displayName": name},
        "config": {"version": "2.0", "logicalId": logical_id},
    }
    return {
        "parts": [
            {"path": "mirroring.json", "payload": encoded(mirroring), "payloadType": "InlineBase64"},
            {"path": ".platform", "payload": encoded(platform), "payloadType": "InlineBase64"},
        ]
    }


def ensure_cosmos(client: FabricClient, workspace_id: str) -> dict:
    name = required("FABRIC_COSMOS_MIRROR_NAME")
    connection_id = required("FABRIC_COSMOS_CONNECTION_ID")
    database = required("COSMOS_DATABASE_NAME")
    path = f"workspaces/{workspace_id}/mirroredDatabases"
    existing = client._named(client.list_all(path), name)
    if existing:
        current_source = definition_part(
            get_definition(client, workspace_id, str(existing["id"])), "mirroring.json"
        )["properties"]["source"]["typeProperties"]
        expected_source = {"connection": connection_id, "database": database}
        if current_source != expected_source:
            if not enabled("FABRIC_ALLOW_COSMOS_MIRROR_RECREATE"):
                raise FabricApiError(
                    "The existing Cosmos mirror targets a different connection or database. "
                    "Set FABRIC_ALLOW_COSMOS_MIRROR_RECREATE=true to authorize replacement "
                    "and a full target reseed."
                )
            response = client.request("DELETE", f"{path}/{existing['id']}")
            client.wait_for_operation(response)
            for _ in range(60):
                if not client._named(client.list_all(path), name):
                    break
                time.sleep(2)
            else:
                raise FabricApiError("Timed out waiting for the prior Cosmos mirror to be removed")
            existing = None
    if not existing:
        response = client.request(
            "POST",
            path,
            json={
                "displayName": name,
                "description": "Source-aligned Bronze physical Delta replica of synthetic Cosmos DB documents.",
                "definition": cosmos_definition(name, connection_id, database),
            },
        )
        client.wait_for_operation(response)
        existing = client._named(client.list_all(path), name)
    if not existing:
        raise FabricApiError("Cosmos mirrored database was not visible after creation")
    status = client.request(
        "POST", f"{path}/{existing['id']}/getMirroringStatus", json={}
    ).json()
    if status.get("status") not in {"Running", "Starting"}:
        response = client.request("POST", f"{path}/{existing['id']}/startMirroring", json={})
        client.wait_for_operation(response)
        status = client.request(
            "POST", f"{path}/{existing['id']}/getMirroringStatus", json={}
        ).json()
    deadline = time.monotonic() + 600
    while status.get("status") != "Running" and time.monotonic() < deadline:
        if status.get("status") in {"Failed", "Stopped"}:
            raise FabricApiError(f"Cosmos mirroring reached {status.get('status')}: {status}")
        time.sleep(5)
        status = client.request(
            "POST", f"{path}/{existing['id']}/getMirroringStatus", json={}
        ).json()
    if status.get("status") != "Running":
        raise TimeoutError(f"Cosmos mirroring did not reach Running within 600s; last={status}")
    return existing


def main() -> None:
    load_dotenv()
    client = FabricClient()
    workspace_name = required("FABRIC_WORKSPACE_NAME")
    workspace = client._named(client.workspaces(), workspace_name)
    if not workspace:
        raise FabricApiError(f"Fabric workspace {workspace_name!r} was not found")
    workspace_id = str(workspace["id"])
    databricks = ensure_databricks(client, workspace_id)
    cosmos = ensure_cosmos(client, workspace_id)
    print(
        json.dumps(
            {
                "workspace": workspace_name,
                "databricksMirror": databricks["displayName"],
                "cosmosMirror": cosmos["displayName"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
