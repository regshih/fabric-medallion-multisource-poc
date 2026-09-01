#!/usr/bin/env python3
"""Connect the Fabric workspace to GitHub and initialize `/fabric_git` sync.

The GitHub token is accepted only through the process environment and stored in
a Fabric connection. It is never written to a repository file or printed.
"""
from __future__ import annotations

import argparse
import os
import time

from dotenv import load_dotenv

from infra.fabric.client import FabricApiError, FabricClient


CONNECTION_NAME = "fabric-medallion-multisource-poc-git-sync"


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.startswith("<"):
        raise RuntimeError(f"Set {name} before configuring Fabric Git")
    return value


def github_pat() -> str:
    """Return a GitHub PAT, rejecting GitHub CLI OAuth/app tokens early."""
    token = required("GITHUB_PAT")
    if not token.startswith(("ghp_", "github_pat_")):
        raise RuntimeError(
            "GITHUB_PAT must be a GitHub classic or fine-grained personal access token; "
            "the OAuth token returned by `gh auth token` is not accepted by Fabric"
        )
    return token


def wait_git_operation(client: FabricClient, response, timeout: float = 1800) -> None:
    if response.status_code != 202:
        return
    location = response.headers.get("Location")
    if not location:
        raise FabricApiError("Fabric Git returned 202 without a Location header")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(min(float(response.headers.get("Retry-After", 5)), 30))
        operation = client.request("GET", location)
        body = operation.json()
        if body.get("status") == "Succeeded":
            return
        if body.get("status") in {"Failed", "Cancelled", "Canceled"}:
            raise FabricApiError(f"Fabric Git operation failed: {body}")
        response = operation
    raise TimeoutError("Fabric Git operation did not finish before the timeout")


def _connection_url(connection: dict) -> str:
    parameters = connection.get("connectionDetails", {}).get("parameters", [])
    return next(
        (str(value.get("value", "")) for value in parameters if value.get("name") == "url"),
        "",
    ).rstrip("/")


def ensure_pat_connection(
    client: FabricClient, repo_url: str, pat: str, *, reuse_existing: bool
) -> str:
    existing = client._named(client.list_all("connections"), CONNECTION_NAME)
    if existing:
        details = client.request("GET", f"connections/{existing['id']}").json()
        configured_url = _connection_url(details)
        if configured_url and configured_url.casefold() != repo_url.rstrip("/").casefold():
            raise FabricApiError(
                f"Existing connection {CONNECTION_NAME!r} targets a different repository; "
                "refusing to reuse it"
            )
        if not reuse_existing:
            raise FabricApiError(
                f"Connection {CONNECTION_NAME!r} already exists. Verify or rotate its PAT in "
                "Fabric, then rerun with --reuse-existing-connection. The script will not "
                "silently overwrite a shared connection credential."
            )
        return str(existing["id"])
    response = client.request(
        "POST",
        "connections",
        json={
            "connectivityType": "ShareableCloud",
            "displayName": CONNECTION_NAME,
            "connectionDetails": {
                "type": "GitHubSourceControl",
                "creationMethod": "GitHubSourceControl.Contents",
                "parameters": [{"dataType": "Text", "name": "url", "value": repo_url}],
            },
            "credentialDetails": {"credentials": {"credentialType": "Key", "key": pat}},
        },
    )
    return str(response.json()["id"])


def configure(
    client: FabricClient,
    *,
    comment: str,
    reuse_existing_connection: bool = False,
    allow_update_from_git: bool = False,
) -> dict[str, str]:
    workspace_name = required("FABRIC_WORKSPACE_NAME")
    owner = required("GITHUB_OWNER")
    repository = required("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_BRANCH", "main").strip() or "main"
    directory = os.getenv("FABRIC_GIT_DIRECTORY", "/fabric_git").strip().strip("/")
    pat = github_pat()

    workspace = client._named(client.workspaces(), workspace_name)
    if not workspace:
        raise FabricApiError(f"Fabric workspace {workspace_name!r} was not found")
    workspace_id = str(workspace["id"])
    connection_id = ensure_pat_connection(
        client,
        f"https://github.com/{owner}/{repository}",
        pat,
        reuse_existing=reuse_existing_connection,
    )

    state = client.request("GET", f"workspaces/{workspace_id}/git/connection").json()
    if state.get("gitConnectionState") == "NotConnected":
        client.request(
            "POST",
            f"workspaces/{workspace_id}/git/connect",
            json={
                "gitProviderDetails": {
                    "gitProviderType": "GitHub",
                    "ownerName": owner,
                    "repositoryName": repository,
                    "branchName": branch,
                    "directoryName": directory,
                },
                "myGitCredentials": {
                    "source": "ConfiguredConnection",
                    "connectionId": connection_id,
                },
            },
        )

    client.request(
        "PATCH",
        f"workspaces/{workspace_id}/git/myGitCredentials",
        json={"source": "ConfiguredConnection", "connectionId": connection_id},
    )
    state = client.request("GET", f"workspaces/{workspace_id}/git/connection").json()
    if state.get("gitConnectionState") != "ConnectedAndInitialized":
        initial = client.request(
            "POST", f"workspaces/{workspace_id}/git/initializeConnection", json={}
        ).json()
        action = initial.get("requiredAction")
        if action == "CommitToGit":
            response = client.request(
                "POST",
                f"workspaces/{workspace_id}/git/commitToGit",
                json={
                    "mode": "All",
                    "workspaceHead": initial["workspaceHead"],
                    "comment": comment,
                },
            )
            wait_git_operation(client, response)
        elif action == "UpdateFromGit":
            if not allow_update_from_git:
                raise FabricApiError(
                    "Git initialization requires UpdateFromGit, which can overwrite workspace "
                    "definitions. Review the branch/directory and rerun with "
                    "--allow-update-from-git to authorize that direction explicitly."
                )
            response = client.request(
                "POST",
                f"workspaces/{workspace_id}/git/updateFromGit",
                json={
                    "remoteCommitHash": initial["remoteCommitHash"],
                    "workspaceHead": initial["workspaceHead"],
                },
            )
            wait_git_operation(client, response)
        elif action not in {None, "None"}:
            raise FabricApiError(f"Unsupported Fabric Git initialization action: {action}")

    final = client.request("GET", f"workspaces/{workspace_id}/git/connection").json()
    return {
        "workspace": workspace_name,
        "directory": directory,
        "state": str(final.get("gitConnectionState", "Unknown")),
    }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comment", default="Initialize multisource POC Fabric artifacts")
    parser.add_argument(
        "--reuse-existing-connection",
        action="store_true",
        help="reuse a repository-validated Fabric connection after its stored PAT was verified",
    )
    parser.add_argument(
        "--allow-update-from-git",
        action="store_true",
        help="explicitly authorize Git-to-workspace initialization when Fabric requires it",
    )
    args = parser.parse_args()
    print(
        configure(
            FabricClient(),
            comment=args.comment,
            reuse_existing_connection=args.reuse_existing_connection,
            allow_update_from_git=args.allow_update_from_git,
        )
    )


if __name__ == "__main__":
    main()
