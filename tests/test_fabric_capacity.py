from dataclasses import dataclass

import pytest

from infra.fabric.capacity import CapacityManager

RID = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Fabric/capacities/poc-cap"


@dataclass
class Token:
    token: str = "test-token"


class Credential:
    def get_token(self, scope):
        return Token()


class Response:
    def __init__(self, body, status=200):
        self.body = body
        self.status_code = status

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def test_requires_exact_capacity_resource_id():
    with pytest.raises(ValueError, match="complete"):
        CapacityManager("poc-cap", Credential())


def test_suspend_requires_exact_name_confirmation_before_mutation():
    session = Session([])
    manager = CapacityManager(RID, Credential(), session=session)
    with pytest.raises(ValueError, match="Refusing"):
        manager.suspend(confirm_name="wrong-cap")
    assert session.calls == []


def test_resume_is_idempotent_when_already_active():
    session = Session([Response({"properties": {"state": "Active"}})])
    manager = CapacityManager(RID, Credential(), session=session)
    assert manager.state(manager.resume()) == "Active"
    assert [call[0] for call in session.calls] == ["GET"]


def test_suspend_posts_action_and_waits_for_suspended_state():
    session = Session([
        Response({"properties": {"state": "Active"}}),
        Response(None, 202),
        Response({"properties": {"state": "Suspended"}}),
    ])
    manager = CapacityManager(RID, Credential(), session=session, sleep=lambda _: None)
    assert manager.state(manager.suspend(confirm_name="poc-cap")) == "Suspended"
    assert session.calls[1][0] == "POST"
    assert "/suspend?api-version=" in session.calls[1][1]
