#!/usr/bin/env python3
"""Generate deterministic, fictional Databricks source data as CSV files.

This dependency-free generator is useful for local inspection and tests. The
Databricks Spark job in ``databricks/01_seed_delta_tables.py`` uses the same
cross-source business-key contract at scale and writes managed Unity Catalog
Delta tables.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator

DEFAULT_ROWS = 500_000
DEFAULT_CUSTOMERS = 50_000
DEFAULT_MERCHANTS = 5_000
BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)

CURRENCIES = ("USD", "USD", "USD", "CAD", "EUR")
TRANSACTION_TYPES = ("Purchase", "Purchase", "Refund", "Transfer", "ATM")
CATEGORIES = ("Grocery", "Dining", "Travel", "Fuel", "Retail", "Healthcare", "Digital")
CHANNELS = ("Mobile", "Web", "POS", "ATM")
COUNTRIES = ("US", "US", "US", "CA", "GB")
STATUSES = ("Approved", "Approved", "Approved", "Declined", "Pending")


def stable_int(namespace: str, ordinal: int, modulus: int) -> int:
    """Return a process-independent pseudo-random integer."""
    digest = hashlib.sha256(f"fabric-poc:{namespace}:{ordinal}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % modulus


def business_keys(ordinal: int, customers: int, merchants: int) -> dict[str, str]:
    customer_num = stable_int("customer", ordinal, customers) + 1
    account_num = customer_num * 2 - stable_int("account", ordinal, 2)
    device_num = customer_num * 3 - stable_int("device", ordinal, 3)
    merchant_num = stable_int("merchant", ordinal, merchants) + 1
    return {
        "TransactionID": f"TXN-{ordinal + 1:09d}",
        "CustomerID": f"CUST-{customer_num:06d}",
        "AccountID": f"ACCT{account_num:09d}",
        "DeviceID": f"DEVICE-{device_num:06d}",
        "MerchantID": f"MER{merchant_num:06d}",
    }


def transaction_rows(count: int, customers: int, merchants: int) -> Iterator[dict[str, object]]:
    for ordinal in range(count):
        keys = business_keys(ordinal, customers, merchants)
        timestamp = BASE_TIME + timedelta(seconds=stable_int("timestamp", ordinal, 2_592_000))
        amount_cents = 100 + stable_int("amount", ordinal, 249_900)
        yield {
            **keys,
            "TransactionTimestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "Amount": f"{amount_cents / 100:.2f}",
            "Currency": CURRENCIES[stable_int("currency", ordinal, len(CURRENCIES))],
            "TransactionType": TRANSACTION_TYPES[stable_int("type", ordinal, len(TRANSACTION_TYPES))],
            "MerchantCategory": CATEGORIES[stable_int("category", ordinal, len(CATEGORIES))],
            "Channel": CHANNELS[stable_int("channel", ordinal, len(CHANNELS))],
            "Country": COUNTRIES[stable_int("country", ordinal, len(COUNTRIES))],
            "CardPresent": stable_int("card_present", ordinal, 2) == 1,
            "TransactionStatus": STATUSES[stable_int("status", ordinal, len(STATUSES))],
            "SourceBatch": "initial",
        }


def risk_rows(count: int) -> Iterator[dict[str, object]]:
    for ordinal in range(count):
        score = stable_int("risk", ordinal, 10_001) / 100
        band = "High" if score >= 80 else "Medium" if score >= 45 else "Low"
        scored = BASE_TIME + timedelta(seconds=stable_int("timestamp", ordinal, 2_592_000) + 30)
        factors = []
        if score >= 80:
            factors.extend(("velocity", "merchant_risk"))
        elif score >= 45:
            factors.append("device_novelty")
        yield {
            "TransactionID": f"TXN-{ordinal + 1:09d}",
            "RiskScore": f"{score:.2f}",
            "RiskBand": band,
            "ModelVersion": "synthetic-risk-v1",
            "ScoredTimestamp": scored.isoformat().replace("+00:00", "Z"),
            "RiskFactors": json.dumps(factors, separators=(",", ":")),
            "SourceBatch": "initial",
        }


def merchant_rows(count: int) -> Iterator[dict[str, object]]:
    for ordinal in range(count):
        category = CATEGORIES[stable_int("merchant_category", ordinal, len(CATEGORIES))]
        risk_num = stable_int("merchant_risk", ordinal, 10)
        yield {
            "MerchantID": f"MER{ordinal + 1:06d}",
            "MerchantName": f"Synthetic Merchant {ordinal + 1:06d}",
            "MerchantCategory": category,
            "City": f"Synthetic City {stable_int('city', ordinal, 100) + 1:03d}",
            "State": f"S{stable_int('state', ordinal, 50) + 1:02d}",
            "Country": COUNTRIES[stable_int("merchant_country", ordinal, len(COUNTRIES))],
            "MerchantRiskCategory": "High" if risk_num == 9 else "Medium" if risk_num >= 6 else "Low",
            "SourceBatch": "initial",
        }


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> int:
    iterator = iter(rows)
    try:
        first = next(iterator)
    except StopIteration:
        raise ValueError(f"Cannot write an empty dataset: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(first))
        writer.writeheader()
        writer.writerow(first)
        count = 1
        for row in iterator:
            writer.writerow(row)
            count += 1
    return count


def generate(output_dir: Path, rows: int, customers: int, merchants: int) -> dict[str, object]:
    if min(rows, customers, merchants) <= 0:
        raise ValueError("rows, customers, and merchants must all be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {
        "transactions": write_csv(output_dir / "transactions.csv", transaction_rows(rows, customers, merchants)),
        "transaction_risk": write_csv(output_dir / "transaction_risk.csv", risk_rows(rows)),
        "merchants": write_csv(output_dir / "merchants.csv", merchant_rows(merchants)),
    }
    manifest = {
        "classification": "SYNTHETIC_TEST_DATA",
        "generator_version": 1,
        "parameters": {"rows": rows, "customers": customers, "merchants": merchants},
        "counts": counts,
        "key_contract": {
            "customer": "CUST- + 6 digits",
            "account": "ACCT + 9 digits",
            "device": "DEVICE- + 6 digits",
            "merchant": "MER + 6 digits",
            "transaction": "TXN- + 9 digits",
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("generated/databricks"))
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS)
    parser.add_argument("--customers", type=int, default=DEFAULT_CUSTOMERS)
    parser.add_argument("--merchants", type=int, default=DEFAULT_MERCHANTS)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(generate(args.output_dir, args.rows, args.customers, args.merchants), indent=2))
