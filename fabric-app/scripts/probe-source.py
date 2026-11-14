"""Read-only SQL view contract probe. Run only when the approved capacity is active."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.fabric_sql import connect  # noqa: E402


EXPECTED = {
    "CustomerProfile": {"CustomerID", "TransactionCount30D", "TotalTransactionAmount30D", "AverageTransactionRiskScore", "HighRiskTransactionCount", "FailedLoginCount", "DistinctDeviceCount", "UntrustedDeviceCount", "GeographicAnomalyCount", "FraudAlertCount", "CustomerRiskScore", "CustomerRiskBand", "gold_loaded_at", "pipeline_run_id"},
    "CustomerTransaction": {"CustomerID", "TransactionID", "TransactionTimestamp", "Amount", "Currency", "Channel", "RiskScore", "TransactionStatus"},
    "CustomerSession": {"CustomerID", "SessionID", "LoginTimestamp", "AuthenticationMethod", "MfaUsed", "FailedAttempts", "Country"},
    "CustomerAlert": {"CustomerID", "AlertID", "CreatedTimestamp", "Severity", "Status", "alertType", "TransactionID"},
    "QualityCheck": {"source", "object", "status", "quarantine_count", "pipeline_run_id", "run_date"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    results = []
    with connect(args.server, args.database) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT v.name,c.name FROM sys.views v JOIN sys.schemas s ON v.schema_id=s.schema_id JOIN sys.columns c ON c.object_id=v.object_id WHERE s.name=?", "risk_app")
        found: dict[str, set[str]] = {}
        for view, column in cursor.fetchall():
            found.setdefault(view, set()).add(column)
        for view, columns in EXPECTED.items():
            missing = sorted(columns - found.get(view, set()))
            if missing:
                results.append({"view": view, "status": "FAIL", "missingColumns": missing})
                continue
            # View/column names are fixed code constants, never caller input.
            selection = ",".join(f"[{column}]" for column in sorted(columns))
            cursor.execute(f"SELECT TOP (1) {selection} FROM [risk_app].[{view}]")
            has_row = cursor.fetchone() is not None
            results.append({"view": view, "status": "PASS", "permittedSampleRow": has_row})
    print(json.dumps({"mode": "read-only", "results": results, "securityEnforcement": "not assessed by this source probe"}, indent=2))
    return 1 if any(result["status"] != "PASS" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
