from __future__ import annotations

import json

from generators.generate_cosmos_data import generate_incremental, generate_initial, write_batch
from validation.validate_cosmos import validate_documents, validate_files


def test_initial_generation_is_deterministic_and_conformed() -> None:
    left = generate_initial(seed=17, customer_count=10, device_count=15, session_count=30, alert_count=8)
    right = generate_initial(seed=17, customer_count=10, device_count=15, session_count=30, alert_count=8)
    assert left == right
    assert validate_documents(left) == []
    assert all(doc["customerId"].startswith("CUST-") for docs in left.values() for doc in docs)
    assert all(alert["transactionId"].startswith("TXN-") for alert in left["fraudAlerts"])


def test_documents_contain_nested_objects_arrays_and_limited_variation() -> None:
    batch = generate_initial(customer_count=10, device_count=20, session_count=30, alert_count=8)
    assert isinstance(batch["digitalSessions"][0]["device"], dict)
    assert isinstance(batch["digitalSessions"][0]["activities"], list)
    assert isinstance(batch["devices"][0]["geoHistory"], list)
    assert any("biometricCapabilities" in device for device in batch["devices"])
    assert any("biometricCapabilities" not in device for device in batch["devices"])
    assert any("resolution" in alert for alert in batch["fraudAlerts"])
    assert any("resolution" not in alert for alert in batch["fraudAlerts"])


def test_incremental_batch_has_required_upsert_semantics() -> None:
    batch = generate_incremental()
    assert [doc["changeType"] for doc in batch["digitalSessions"]] == ["insert"]
    assert batch["devices"][0]["id"] == "DEVICE-000001"
    assert batch["devices"][0]["trusted"] is False
    assert {doc["changeType"] for doc in batch["fraudAlerts"]} == {"insert", "update"}
    assert next(doc for doc in batch["fraudAlerts"] if doc["changeType"] == "update")["status"] == "resolved"
    assert validate_documents(batch) == []


def test_jsonl_manifest_and_file_validation(tmp_path) -> None:
    batch = generate_initial(customer_count=5, device_count=8, session_count=12, alert_count=4)
    manifest = write_batch(tmp_path, batch, "initial")
    assert manifest["partitionKey"] == "/customerId"
    assert manifest["counts"] == {"digitalSessions": 12, "devices": 8, "fraudAlerts": 4}
    result = validate_files(tmp_path / "initial")
    assert result["status"] == "PASS"
    first_line = (tmp_path / "initial" / "digitalSessions.jsonl").read_text(encoding="utf-8").splitlines()[0]
    assert json.loads(first_line)["synthetic"] is True


def test_validator_rejects_partition_and_cross_source_key_defects() -> None:
    batch = generate_initial(customer_count=3, device_count=3, session_count=3, alert_count=1)
    batch["fraudAlerts"][0]["transactionId"] = "not-conformed"
    batch["digitalSessions"][0]["customerId"] = ""
    errors = validate_documents(batch)
    assert any("transactionId" in error for error in errors)
    assert any("customerId" in error for error in errors)
