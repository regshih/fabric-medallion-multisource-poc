from __future__ import annotations

from pathlib import Path

import pytest

from cosmos.common import read_jsonl

ROOT = Path(__file__).resolve().parents[1]


def test_bicep_enforces_mirroring_prerequisites_and_partitioning() -> None:
    template = (ROOT / "infra" / "cosmos" / "main.bicep").read_text(encoding="utf-8")
    assert "type: 'Continuous'" in template
    assert "tier: 'Continuous7Days'" in template
    assert "disableLocalAuth: true" in template
    assert "name: 'EnableServerless'" in template
    assert "publicNetworkAccess: 'Disabled'" in template
    assert "autoscaleSettings" not in template
    assert template.count("paths: ['/customerId']") == 3
    assert "digitalSessions" in template and "devices" in template and "fraudAlerts" in template


def test_setup_uses_entra_data_plane_role_without_keys() -> None:
    setup = (ROOT / "infra" / "cosmos" / "setup.ps1").read_text(encoding="utf-8")
    assert "00000000-0000-0000-0000-000000000002" in setup
    assert "sql role assignment" in setup
    assert "listKeys" not in setup
    assert "connection-string" not in setup


def test_jsonl_reader_rejects_missing_partition_key(tmp_path: Path) -> None:
    source = tmp_path / "bad.jsonl"
    source.write_text('{"id":"DEVICE-000001"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="id and customerId"):
        list(read_jsonl(source))
