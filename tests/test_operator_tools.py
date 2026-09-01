from __future__ import annotations

import pytest

from infra.fabric.git_integration import _connection_url, github_pat
from tools.fabric_sql import split_batches


def test_split_batches_handles_go_lines_only() -> None:
    sql = "SELECT 'GO is data';\nGO\nSELECT 2;\n go -- next batch\nSELECT 3;"
    assert split_batches(sql) == ["SELECT 'GO is data';", "SELECT 2;", "SELECT 3;"]


def test_github_pat_rejects_cli_oauth_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_PAT", "gho_not-a-fabric-pat")
    with pytest.raises(RuntimeError, match="classic or fine-grained"):
        github_pat()


def test_github_pat_accepts_fine_grained_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_PAT", "github_pat_synthetic_test_value")
    assert github_pat().startswith("github_pat_")


def test_connection_url_reads_named_parameter() -> None:
    connection = {
        "connectionDetails": {
            "parameters": [
                {"name": "unrelated", "value": "x"},
                {"name": "url", "value": "https://github.com/example/repo/"},
            ]
        }
    }
    assert _connection_url(connection) == "https://github.com/example/repo"
