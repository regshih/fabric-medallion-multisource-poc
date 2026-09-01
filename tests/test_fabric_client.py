from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests

from infra.fabric.client import FabricApiError, FabricClient


class Response:
    def __init__(self, status: int = 200, body: Any = None, headers: dict[str, str] | None = None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.content = b"" if body is None else b"json"

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(str(self.status_code))
            error.response = self
            raise error


@dataclass
class Token:
    token: str
    expires_on: float


class Credential:
    def __init__(self):
        self.calls = 0

    def get_token(self, scope: str):
        self.calls += 1
        return Token(f"token-{self.calls}", 10_000)


class Session:
    def __init__(self, responses: list[Response]):
        self.responses = responses
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


class Clock:
    def __init__(self):
        self.now = 0.0

    def sleep(self, seconds: float):
        self.now += seconds


def client(responses: list[Response], clock: Clock | None = None) -> tuple[FabricClient, Session, Credential]:
    session = Session(responses)
    credential = Credential()
    clock = clock or Clock()
    return (
        FabricClient(
            credential,
            session=session,
            sleep=clock.sleep,
            monotonic=lambda: clock.now,
            epoch=lambda: 0,
            poll_interval=1,
        ),
        session,
        credential,
    )


def test_request_refreshes_token_once_after_401():
    api, session, credential = client([Response(401), Response(200, {"ok": True})])
    assert api.request("GET", "workspaces").json() == {"ok": True}
    assert credential.calls == 2
    assert session.headers["Authorization"].endswith("token-2")
    assert len(session.calls) == 2


def test_list_all_follows_continuation_uri_and_token():
    api, session, _ = client(
        [
            Response(200, {"value": [{"id": "1"}], "continuationUri": "/v1/workspaces?page=2"}),
            Response(200, {"value": [{"id": "2"}], "continuationToken": "next token"}),
            Response(200, {"value": [{"id": "3"}]}),
        ]
    )
    assert [item["id"] for item in api.list_all("workspaces")] == ["1", "2", "3"]
    assert session.calls[1][1] == "https://api.fabric.microsoft.com/v1/workspaces?page=2"
    assert session.calls[2][1].endswith("page=2&continuationToken=next+token")


def test_wait_for_operation_returns_result():
    clock = Clock()
    api, session, _ = client(
        [
            Response(200, {"status": "Running"}, {"Retry-After": "2"}),
            Response(200, {"status": "Succeeded", "resultUrl": "https://result"}),
            Response(200, {"id": "new-item"}),
        ],
        clock,
    )
    initial = Response(202, None, {"Location": "https://operation", "Retry-After": "1"})
    assert api.wait_for_operation(initial, timeout=10) == {"id": "new-item"}
    assert clock.now == 3
    assert session.calls[-1][1] == "https://result"


def test_wait_for_operation_is_bounded():
    clock = Clock()
    api, _, _ = client([Response(200, {"status": "Running"})] * 3, clock)
    with pytest.raises(TimeoutError, match="within 3s"):
        api.wait_for_operation(Response(202, None, {"Location": "https://operation"}), timeout=3)
    assert clock.now == 3


def test_wait_for_operation_raises_terminal_error():
    api, _, _ = client([Response(200, {"status": "Failed", "error": "bad"})])
    with pytest.raises(FabricApiError, match="bad"):
        api.wait_for_operation(Response(202, None, {"Location": "https://operation"}), timeout=3)


def test_ensure_item_updates_existing_definition_instead_of_creating_duplicate():
    api, session, _ = client(
        [
            Response(200, {"value": [{"id": "n1", "displayName": "nb", "type": "Notebook"}]}),
            Response(200, {}),
        ]
    )
    result = api.ensure_item("ws", "nb", "Notebook", {"parts": []})
    assert result["id"] == "n1"
    assert session.calls[-1][0] == "POST"
    assert session.calls[-1][1].endswith("/items/n1/updateDefinition")


def test_duplicate_named_items_fail_closed():
    api, _, _ = client(
        [Response(200, {"value": [
            {"id": "1", "displayName": "same", "type": "Lakehouse"},
            {"id": "2", "displayName": "same", "type": "Lakehouse"},
        ]})]
    )
    with pytest.raises(FabricApiError, match="Multiple"):
        api.ensure_item("ws", "same", "Lakehouse")
