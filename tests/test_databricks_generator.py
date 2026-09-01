import csv
import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_databricks_data", ROOT / "generators" / "generate_databricks_data.py"
)
GENERATOR = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(GENERATOR)
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_databricks", ROOT / "validation" / "validate_databricks.py"
)
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


def test_generation_is_deterministic_and_cross_keys_are_valid(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    manifest = GENERATOR.generate(first, rows=100, customers=20, merchants=10)
    GENERATOR.generate(second, rows=100, customers=20, merchants=10)
    assert manifest["counts"] == {"transactions": 100, "transaction_risk": 100, "merchants": 10}
    assert (first / "transactions.csv").read_bytes() == (second / "transactions.csv").read_bytes()

    with (first / "transactions.csv").open(newline="", encoding="utf-8") as handle:
        transactions = list(csv.DictReader(handle))
    with (first / "transaction_risk.csv").open(newline="", encoding="utf-8") as handle:
        risks = list(csv.DictReader(handle))
    assert {row["TransactionID"] for row in transactions} == {row["TransactionID"] for row in risks}
    assert all(row["CustomerID"].startswith("CUST-") for row in transactions)
    assert all(row["TransactionID"].startswith("TXN-") for row in transactions)
    assert all(row["DeviceID"].startswith("DEVICE-") for row in transactions)
    assert all(0 <= float(row["RiskScore"]) <= 100 for row in risks)
    assert VALIDATOR.validate_files(first)["status"] == "PASS"


def test_invalid_counts_are_rejected(tmp_path):
    try:
        GENERATOR.generate(tmp_path, rows=0, customers=10, merchants=10)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected ValueError")
