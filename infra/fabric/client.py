"""Small, resilient client for the Microsoft Fabric REST API.

Authentication uses Microsoft Entra ID through ``DefaultAzureCredential``.  The
client deliberately contains no tenant IDs, item IDs, or credentials.
"""
from __future__ import annotations

import email.utils
import json
import time
from collections.abc import Callable, Iterator, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from azure.identity import DefaultAzureCredential

FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
TERMINAL_SUCCESS = frozenset({"Succeeded", "Completed", "Deduped"})
TERMINAL_FAILURE = frozenset({"Failed", "Cancelled", "Canceled"})


class FabricApiError(RuntimeError):
    """A Fabric operation reached a terminal failure state."""


def _retry_seconds(value: str | None, default: float) -> float:
    if not value:
        return default
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            parsed = email.utils.parsedate_to_datetime(value)
            return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            return default


def _with_continuation_token(url: str, token: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["continuationToken"] = token
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class FabricClient:
    """Fabric REST client with token refresh, pagination, and bounded polling."""

    def __init__(
        self,
        credential: Any | None = None,
        *,
        session: requests.Session | None = None,
        base_url: str = FABRIC_API,
        request_timeout: float = 60,
        poll_interval: float = 5,
        lro_timeout: float = 1800,
        job_timeout: float = 43200,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        epoch: Callable[[], float] = time.time,
    ) -> None:
        self.credential = credential or DefaultAzureCredential()
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.poll_interval = poll_interval
        self.lro_timeout = lro_timeout
        self.job_timeout = job_timeout
        self._sleep = sleep
        self._monotonic = monotonic
        self._epoch = epoch
        self._expires_on = 0.0

    def _authorize(self, *, force: bool = False) -> None:
        # Refresh five minutes early so a token does not expire during a request.
        if not force and self._expires_on - self._epoch() > 300:
            return
        token = self.credential.get_token(FABRIC_SCOPE)
        self._expires_on = float(getattr(token, "expires_on", self._epoch() + 300))
        self.session.headers.update(
            {"Authorization": f"Bearer {token.token}", "Content-Type": "application/json"}
        )

    def url(self, path_or_url: str) -> str:
        if path_or_url.startswith(("https://", "http://")):
            return path_or_url
        return f"{self.base_url}/{path_or_url.lstrip('/')}"

    def request(self, method: str, path_or_url: str, **kwargs: Any) -> requests.Response:
        self._authorize()
        kwargs.setdefault("timeout", self.request_timeout)
        response = self.session.request(method, self.url(path_or_url), **kwargs)
        if response.status_code == 401:
            self._authorize(force=True)
            response = self.session.request(method, self.url(path_or_url), **kwargs)
        response.raise_for_status()
        return response

    def pages(self, path_or_url: str) -> Iterator[Mapping[str, Any]]:
        """Yield every list response page, honoring both Fabric paging styles."""
        url = self.url(path_or_url)
        while url:
            response = self.request("GET", url)
            body = response.json()
            if not isinstance(body, Mapping):
                raise FabricApiError("Fabric list response was not a JSON object")
            yield body
            continuation_uri = body.get("continuationUri")
            if continuation_uri:
                url = urljoin(url, str(continuation_uri))
            elif body.get("continuationToken"):
                url = _with_continuation_token(url, str(body["continuationToken"]))
            else:
                url = ""

    def list_all(self, path_or_url: str) -> list[dict[str, Any]]:
        return [dict(item) for page in self.pages(path_or_url) for item in page.get("value", [])]

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        if not response.content:
            return {}
        body = response.json()
        return body if isinstance(body, dict) else {"value": body}

    def wait_for_operation(
        self, response: requests.Response, *, timeout: float | None = None
    ) -> dict[str, Any]:
        """Resolve a 202 long-running operation, or return a synchronous body."""
        if response.status_code != 202:
            return self._json(response)
        location = response.headers.get("Location")
        if not location:
            raise FabricApiError("Fabric returned 202 without a Location header")
        deadline = self._monotonic() + (self.lro_timeout if timeout is None else timeout)
        delay = _retry_seconds(response.headers.get("Retry-After"), self.poll_interval)
        last: dict[str, Any] = {}
        while self._monotonic() < deadline:
            self._sleep(min(delay, max(0.0, deadline - self._monotonic())))
            poll = self.request("GET", location)
            last = self._json(poll)
            status = str(last.get("status", ""))
            if status in TERMINAL_FAILURE:
                raise FabricApiError(f"Fabric operation {status}: {json.dumps(last, sort_keys=True)}")
            if status in TERMINAL_SUCCESS:
                result_url = last.get("resultUrl") or poll.headers.get("Location")
                if not result_url:
                    return last
                result = self.request("GET", str(result_url))
                return self._json(result) or last
            delay = _retry_seconds(poll.headers.get("Retry-After"), self.poll_interval)
        raise TimeoutError(f"Fabric operation did not finish within {timeout or self.lro_timeout}s; last={last}")

    def capacities(self) -> list[dict[str, Any]]:
        return self.list_all("capacities")

    def workspaces(self) -> list[dict[str, Any]]:
        return self.list_all("workspaces")

    def items(self, workspace_id: str) -> list[dict[str, Any]]:
        return self.list_all(f"workspaces/{workspace_id}/items")

    @staticmethod
    def _named(objects: list[dict[str, Any]], name: str, item_type: str | None = None) -> dict[str, Any] | None:
        matches = [
            obj for obj in objects
            if obj.get("displayName") == name and (item_type is None or obj.get("type") == item_type)
        ]
        if len(matches) > 1:
            raise FabricApiError(f"Multiple {item_type or 'objects'} named {name!r} are visible")
        return matches[0] if matches else None

    def ensure_workspace(self, name: str, capacity_id: str, description: str) -> dict[str, Any]:
        existing = self._named(self.workspaces(), name)
        if existing:
            if existing.get("capacityId") != capacity_id:
                response = self.request(
                    "POST", f"workspaces/{existing['id']}/assignToCapacity", json={"capacityId": capacity_id}
                )
                self.wait_for_operation(response)
                existing["capacityId"] = capacity_id
            return existing
        response = self.request(
            "POST",
            "workspaces",
            json={"displayName": name, "description": description, "capacityId": capacity_id},
        )
        result = self.wait_for_operation(response)
        return result if result.get("id") else self._named(self.workspaces(), name) or result

    def ensure_item(
        self,
        workspace_id: str,
        display_name: str,
        item_type: str,
        definition: dict[str, Any] | None = None,
        *,
        description: str | None = None,
    ) -> dict[str, Any]:
        existing = self._named(self.items(workspace_id), display_name, item_type)
        if existing:
            if definition is not None:
                response = self.request(
                    "POST",
                    f"workspaces/{workspace_id}/items/{existing['id']}/updateDefinition",
                    json={"definition": definition},
                )
                self.wait_for_operation(response)
            return existing
        payload: dict[str, Any] = {"displayName": display_name, "type": item_type}
        if description:
            payload["description"] = description
        if definition is not None:
            payload["definition"] = definition
        response = self.request("POST", f"workspaces/{workspace_id}/items", json=payload)
        result = self.wait_for_operation(response)
        return result if result.get("id") else self._named(self.items(workspace_id), display_name, item_type) or result

    def run_item(
        self,
        workspace_id: str,
        item_id: str,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        response = self.request(
            "POST",
            f"workspaces/{workspace_id}/items/{item_id}/jobs/instances?jobType={job_type}",
            json=payload or {},
        )
        location = response.headers.get("Location")
        if not location:
            body = self._json(response)
            if response.status_code == 202:
                raise FabricApiError("Fabric job returned 202 without a Location header")
            return body
        limit = self.job_timeout if timeout is None else timeout
        deadline = self._monotonic() + limit
        delay = _retry_seconds(response.headers.get("Retry-After"), self.poll_interval)
        last: dict[str, Any] = {}
        while self._monotonic() < deadline:
            self._sleep(min(delay, max(0.0, deadline - self._monotonic())))
            poll = self.request("GET", location)
            last = self._json(poll)
            status = str(last.get("status", ""))
            if status in TERMINAL_SUCCESS:
                return last
            if status in TERMINAL_FAILURE:
                raise FabricApiError(f"Fabric job {status}: {json.dumps(last, sort_keys=True)}")
            delay = _retry_seconds(poll.headers.get("Retry-After"), self.poll_interval)
        raise TimeoutError(f"Fabric {job_type} job did not finish within {limit}s; last={last}")
