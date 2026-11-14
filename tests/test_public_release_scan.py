"""Prevent live deployment inventory from returning to public source."""
from tools.security_scan import scan_text


def test_inventory_patterns_detect_environment_context_without_echoing_values():
    identifier = "11111111" + "-2222-3333-4444-555555555555"
    examples = {
        "azure-resource-inventory": "/subscriptions/" + identifier + "/resourceGroups/demo",
        "fabric-workspace-inventory": "https://app.fabric.microsoft.com/groups/" + identifier + "/items/demo",
        "fabric-host-inventory": "https://demo.webapp." + "fabricapps.net",
        "tenant-user-inventory": "operator@" + "demo.onmicrosoft.com",
    }
    for kind, value in examples.items():
        findings = scan_text("example.md", value)
        assert f"example.md:1: {kind}" in findings
        assert all(value not in finding for finding in findings)


def test_public_placeholders_and_official_documentation_remain_allowed():
    text = "\n".join([
        "https://learn.microsoft.com/en-us/fabric/apps/overview",
        "https://app.fabric.microsoft.com/groups/<workspace-id>/items/<item-id>",
        "https://<warehouse-sql-host>",
        "AZURE_SUBSCRIPTION_ID=<subscription-id>",
        "VITE_FABRIC_WORKSPACE_ID=00000000-0000-4000-8000-000000000001",
    ])
    assert scan_text("example.md", text) == []
