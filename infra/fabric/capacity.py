#!/usr/bin/env python
"""Safely inspect, resume, or suspend one explicitly named Fabric capacity."""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections.abc import Callable
from typing import Any

import requests
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

ARM_SCOPE = "https://management.azure.com/.default"
API_VERSION = "2023-11-01"
RESOURCE_ID = re.compile(
    r"^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft\.Fabric/capacities/([^/]+)$",
    re.IGNORECASE,
)


class CapacityManager:
    def __init__(
        self,
        resource_id: str,
        credential: Any | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = 900,
        request_timeout: float = 60,
        poll_interval: float = 10,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        match = RESOURCE_ID.fullmatch(resource_id.rstrip("/"))
        if not match:
            raise ValueError("FABRIC_CAPACITY_ID must be a complete Microsoft.Fabric/capacities ARM resource ID")
        self.resource_id = resource_id.rstrip("/")
        self.name = match.group(1)
        self.credential = credential or DefaultAzureCredential()
        self.session = session or requests.Session()
        self.timeout = timeout
        self.request_timeout = request_timeout
        self.poll_interval = poll_interval
        self._sleep = sleep
        self._monotonic = monotonic

    def _url(self, suffix: str = "") -> str:
        return f"https://management.azure.com{self.resource_id}{suffix}?api-version={API_VERSION}"

    def _request(self, method: str, url: str) -> requests.Response:
        token = self.credential.get_token(ARM_SCOPE)
        response = self.session.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token.token}", "Content-Type": "application/json"},
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        return response

    def get(self) -> dict[str, Any]:
        return self._request("GET", self._url()).json()

    @staticmethod
    def state(resource: dict[str, Any]) -> str:
        properties = resource.get("properties", {})
        return str(properties.get("state") or properties.get("provisioningState") or "Unknown")

    def wait_for(self, expected: set[str]) -> dict[str, Any]:
        deadline = self._monotonic() + self.timeout
        last: dict[str, Any] = {}
        while self._monotonic() < deadline:
            last = self.get()
            state = self.state(last)
            if state.lower() in {item.lower() for item in expected}:
                return last
            if state.lower() in {"failed", "canceled", "cancelled"}:
                raise RuntimeError(f"Capacity entered terminal state {state}: {json.dumps(last)}")
            self._sleep(min(self.poll_interval, max(0.0, deadline - self._monotonic())))
        raise TimeoutError(f"Capacity {self.name} did not reach {sorted(expected)}; last={self.state(last)}")

    def resume(self) -> dict[str, Any]:
        current = self.get()
        if self.state(current).lower() in {"active", "succeeded"}:
            return current
        self._request("POST", self._url("/resume"))
        return self.wait_for({"Active", "Succeeded"})

    def suspend(self, *, confirm_name: str) -> dict[str, Any]:
        if confirm_name != self.name:
            raise ValueError(f"Refusing to suspend: confirmation must exactly equal {self.name!r}")
        current = self.get()
        if self.state(current).lower() in {"paused", "suspended"}:
            return current
        self._request("POST", self._url("/suspend"))
        return self.wait_for({"Paused", "Suspended"})


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "resume", "suspend"))
    parser.add_argument("--confirm-name", default="", help="Required exact capacity name for suspend")
    args = parser.parse_args()
    resource_id = os.getenv("FABRIC_CAPACITY_ID", "")
    manager = CapacityManager(resource_id)
    if args.action == "resume":
        result = manager.resume()
    elif args.action == "suspend":
        result = manager.suspend(confirm_name=args.confirm_name)
    else:
        result = manager.get()
    print(json.dumps({"name": manager.name, "state": manager.state(result)}, indent=2))


if __name__ == "__main__":
    main()
