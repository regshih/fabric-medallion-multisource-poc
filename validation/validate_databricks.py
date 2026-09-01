#!/usr/bin/env python3
"""Validate generated Databricks CSVs or Unity Catalog Delta tables."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

PATTERNS = {
    "TransactionID": re.compile(r"^TXN-\d{9}$"),
    "CustomerID": re.compile(r"^CUST-\d{6}$"),
    "AccountID": re.compile(r"^ACCT\d{9}$"),
    "MerchantID": re.compile(r"^MER\d{6}$"),
    "DeviceID": re.compile(r"^DEVICE-\d{6}$"),
}


def validate_files(root: Path) -> dict[str, object]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    observed: dict[str, int] = {}
    transaction_ids: set[str] = set()
    referenced_merchant_ids: set[str] = set()
    merchant_ids: set[str] = set()
    for dataset in ("transactions", "transaction_risk", "merchants"):
        path = root / f"{dataset}.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            count = 0
            for row in reader:
                count += 1
                for field, pattern in PATTERNS.items():
                    if field in row and not pattern.fullmatch(row[field]):
                        failures.append(f"{dataset} row {count}: invalid {field}")
                if dataset == "transactions":
                    if row["TransactionID"] in transaction_ids:
                        failures.append(f"transactions row {count}: duplicate TransactionID")
                    transaction_ids.add(row["TransactionID"])
                    referenced_merchant_ids.add(row["MerchantID"])
                    amount = float(row["Amount"])
                    if amount <= 0:
                        failures.append(f"transactions row {count}: non-positive Amount")
                elif dataset == "transaction_risk":
                    score = float(row["RiskScore"])
                    if not 0 <= score <= 100:
                        failures.append(f"transaction_risk row {count}: RiskScore out of range")
                    if row["TransactionID"] not in transaction_ids:
                        failures.append(f"transaction_risk row {count}: orphan TransactionID")
                else:
                    merchant_ids.add(row["MerchantID"])
            observed[dataset] = count
    missing_merchants = referenced_merchant_ids - merchant_ids
    if missing_merchants:
        failures.append(f"transactions reference {len(missing_merchants)} missing merchants")
    expected = manifest["counts"]
    for name, count in observed.items():
        if count != expected[name]:
            failures.append(f"{name}: expected {expected[name]}, observed {count}")
    if manifest.get("classification") != "SYNTHETIC_TEST_DATA":
        failures.append("manifest synthetic-data classification missing")
    return {"status": "PASS" if not failures else "FAIL", "counts": observed, "failures": failures[:100]}


def validate_spark(catalog: str, schema: str, base_rows: int, incremental_rows: int) -> dict[str, object]:
    # ``spark`` is injected by Databricks. Identifiers are constrained before interpolation.
    if not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,254}", value) for value in (catalog, schema)):
        raise ValueError("Unsafe catalog or schema identifier")
    names = {name: f"`{catalog}`.`{schema}`.`{name}`" for name in ("transactions", "transaction_risk", "merchants")}
    counts = {name: spark.table(table).count() for name, table in names.items()}  # type: ignore[name-defined]
    failures = []
    expected_transactions = base_rows + incremental_rows
    if counts["transactions"] != expected_transactions:
        failures.append(f"transactions expected {expected_transactions}, observed {counts['transactions']}")
    if counts["transaction_risk"] != counts["transactions"]:
        failures.append("transaction_risk does not have one current row per transaction")
    invalid = spark.sql(  # type: ignore[name-defined]
        f"SELECT count(*) n FROM {names['transaction_risk']} WHERE RiskScore < 0 OR RiskScore > 100 OR TransactionID IS NULL"
    ).first().n
    if invalid:
        failures.append(f"transaction_risk has {invalid} invalid rows")
    orphans = spark.sql(  # type: ignore[name-defined]
        f"SELECT count(*) n FROM {names['transactions']} t LEFT ANTI JOIN {names['merchants']} m ON t.MerchantID=m.MerchantID"
    ).first().n
    if orphans:
        failures.append(f"transactions has {orphans} orphan merchant references")
    duplicate_txns = spark.sql(  # type: ignore[name-defined]
        f"SELECT count(*) n FROM (SELECT TransactionID FROM {names['transactions']} GROUP BY TransactionID HAVING count(*) > 1)"
    ).first().n
    if duplicate_txns:
        failures.append(f"transactions has {duplicate_txns} duplicate business keys")
    return {"status": "PASS" if not failures else "FAIL", "counts": counts, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--catalog", default="fabric_multisource_poc")
    parser.add_argument("--schema", default="banking_source")
    parser.add_argument("--base-rows", type=int, default=500_000)
    parser.add_argument("--incremental-rows", type=int, default=0)
    args = parser.parse_args()
    result = validate_files(args.input_dir) if args.input_dir else validate_spark(
        args.catalog, args.schema, args.base_rows, args.incremental_rows
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
