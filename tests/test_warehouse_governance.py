import copy
import re
from pathlib import Path

import pytest

from infra.governance.catalog_search import search
from infra.governance.catalog_setup import DESCRIPTIONS, planned_updates
from infra.governance.onelake_data_access import (
    PERMITTED_DEVICE_COLUMNS,
    TARGET_TABLE,
    build_replacement,
    update,
)


ROOT = Path(__file__).parents[1]
WAREHOUSE = ROOT / "warehouse"


def sql(name):
    return (WAREHOUSE / name).read_text(encoding="utf-8")


def test_warehouse_refresh_order_and_object_contract():
    refresh = sql("00_refresh_gold_serving.sql")
    security = sql("10_apply_security.sql")
    assert refresh.index("DROP SECURITY POLICY") < refresh.index("DROP TABLE") < refresh.index("CREATE TABLE")
    assert all(
        f"CREATE OR ALTER VIEW dbo.{name}" in refresh
        for name in [
            "DimCustomer", "DimAccount", "DimMerchant", "DimDevice", "DimDate",
            "FactTransactions", "FactDigitalSessions", "FactFraudAlerts",
            "AggCustomerRiskProfile",
        ]
    )
    assert refresh.count("CREATE TABLE dbo._base_") == 3
    assert "ADD MASKED" in security
    assert "CREATE SECURITY POLICY Security.CustomerRiskPolicy" in security
    assert "ON dbo._base_AggCustomerRiskProfile" in security
    assert "USER_NAME()" in security


def test_warehouse_assets_contain_no_embedded_identity_or_secret():
    text = "\n".join(path.read_text(encoding="utf-8") for path in WAREHOUSE.iterdir())
    guid = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I)
    assert not guid.search(text)
    assert "AccountKey=" not in text
    assert "Bearer " not in text
    assert "$(RISK_INVESTIGATOR_PRINCIPAL)" in text


def test_catalog_description_plan_is_bounded_and_idempotent():
    assert DESCRIPTIONS
    assert all(0 < len(value) <= 256 for value in DESCRIPTIONS.values())
    items = [
        {"id": "one", "displayName": "gold_lh", "description": DESCRIPTIONS["gold_lh"]},
        {"id": "two", "displayName": "gold_wh", "description": "old"},
        {"id": "three", "displayName": "unmanaged", "description": "leave me"},
    ]
    assert planned_updates(items) == [("two", DESCRIPTIONS["gold_wh"])]
    assert len(planned_updates(items, force=True)) == 2


def sample_roles():
    return [
        {
            "id": "server-assigned",
            "name": "DefaultReader",
            "kind": "Policy",
            "members": {"fabricItemMembers": [{"itemAccess": ["ReadAll"], "sourcePath": "w/i"}]},
            "decisionRules": [
                {
                    "effect": "Permit",
                    "permission": [
                        {"attributeName": "Path", "attributeValueIncludedIn": ["*"]},
                        {"attributeName": "Action", "attributeValueIncludedIn": ["Read"]},
                    ],
                    "constraints": {
                        "rows": [{"tablePath": "/Tables/Other", "value": "x = 1"}],
                        "columns": [{"tablePath": "/Tables/Other", "columnNames": ["x"],
                                     "columnEffect": "Permit", "columnAction": ["Read"]}],
                    },
                }
            ],
        },
        {"id": "custom-id", "name": "Custom", "kind": "Policy", "members": {}, "decisionRules": []},
    ]


def test_onelake_replacement_preserves_every_role_and_unrelated_constraint():
    original = sample_roles()
    payload = build_replacement(original)
    assert original == sample_roles()  # pure transform
    assert [role["name"] for role in payload["value"]] == ["DefaultReader", "Custom"]
    assert all("id" not in role for role in payload["value"])
    rule = payload["value"][0]["decisionRules"][0]
    assert rule["constraints"]["rows"] == [{"tablePath": "/Tables/Other", "value": "x = 1"}]
    columns = rule["constraints"]["columns"]
    assert any(column["tablePath"] == "/Tables/Other" for column in columns)
    target = next(column for column in columns if column["tablePath"] == TARGET_TABLE)
    assert "deviceFingerprint" not in target["columnNames"]
    assert target["columnNames"] == PERMITTED_DEVICE_COLUMNS


class Response:
    def __init__(self, body=None, headers=None):
        self._body = body or {}
        self.headers = headers or {}

    def json(self):
        return copy.deepcopy(self._body)


class FakeClient:
    def __init__(self):
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == "GET":
            return Response({"value": sample_roles()}, {"ETag": '"version-1"'})
        return Response(headers={"ETag": '"version-2"'})


def test_onelake_update_defaults_to_server_dry_run_and_uses_etag():
    client = FakeClient()
    result = update(client, "workspace", "item", apply=False, role_name="DefaultReader")
    assert result["applied"] is False
    assert [call[:2] for call in client.calls] == [
        ("GET", "workspaces/workspace/items/item/dataAccessRoles"),
        ("PUT", "workspaces/workspace/items/item/dataAccessRoles?dryRun=true"),
    ]
    assert client.calls[1][2]["headers"] == {"If-Match": '"version-1"'}


def test_onelake_apply_runs_validation_before_full_replace():
    client = FakeClient()
    result = update(client, "workspace", "item", apply=True, role_name="DefaultReader")
    assert result["applied"] is True
    assert [call[1] for call in client.calls] == [
        "workspaces/workspace/items/item/dataAccessRoles",
        "workspaces/workspace/items/item/dataAccessRoles?dryRun=true",
        "workspaces/workspace/items/item/dataAccessRoles",
    ]


def test_catalog_search_rejects_filter_injection_before_network_call():
    with pytest.raises(ValueError):
        search(FakeClient(), "risk", "Warehouse' or Type ne 'Warehouse", 100)
    with pytest.raises(ValueError):
        search(FakeClient(), "risk", None, 0)

