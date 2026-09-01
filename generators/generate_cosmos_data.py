#!/usr/bin/env python3
"""Generate deterministic, wholly synthetic Cosmos DB for NoSQL documents.

The output is JSON Lines so it can be inspected, versioned selectively, and
loaded with ``cosmos/load_initial.py`` or ``cosmos/load_incremental.py``.
No value is sourced from a real person or production system.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_SEED = 20260831
DEFAULT_AS_OF = "2026-08-31T12:00:00Z"
CONTAINERS = ("digitalSessions", "devices", "fraudAlerts")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def customer_id(number: int) -> str:
    return f"CUST-{number:06d}"


def transaction_id(number: int) -> str:
    return f"TXN-{number:09d}"


def device_id(number: int) -> str:
    return f"DEVICE-{number:06d}"


def generate_initial(
    *,
    seed: int = DEFAULT_SEED,
    as_of: str = DEFAULT_AS_OF,
    customer_count: int = 100,
    device_count: int = 150,
    session_count: int = 500,
    alert_count: int = 60,
) -> dict[str, list[dict[str, Any]]]:
    """Return a repeatable initial snapshot with useful nested structures."""
    if min(customer_count, device_count, session_count) < 1 or alert_count < 0:
        raise ValueError("customer, device, and session counts must be positive; alerts cannot be negative")

    rng = random.Random(seed)
    anchor = _dt(as_of)
    cities = [
        ("US", "NY", "New York"),
        ("US", "WA", "Seattle"),
        ("US", "IL", "Chicago"),
        ("US", "TX", "Austin"),
        ("CA", "ON", "Toronto"),
    ]
    systems = [("iOS", "18.3", "Mobile"), ("Android", "15", "Mobile"), ("Windows", "11", "Desktop")]

    devices: list[dict[str, Any]] = []
    for i in range(1, device_count + 1):
        cid = customer_id(((i - 1) % customer_count) + 1)
        os_name, os_version, device_type = systems[(i - 1) % len(systems)]
        first_seen = anchor - timedelta(days=30 + (i * 17) % 700)
        last_seen = anchor - timedelta(hours=(i * 7) % 240)
        trusted = i % 7 != 0
        home = cities[(i - 1) % len(cities)]
        doc: dict[str, Any] = {
            "id": device_id(i),
            "deviceId": device_id(i),
            "customerId": cid,
            "firstSeen": _iso(first_seen),
            "lastSeen": _iso(last_seen),
            "trusted": trusted,
            "deviceFingerprint": f"SYNTH-FP-{i:08X}",
            "operatingSystem": {"name": os_name, "version": os_version},
            "appVersion": f"6.{i % 8}.{i % 13}",
            "riskSignals": (
                []
                if trusted
                else [{"type": "emulator" if i % 2 else "rootedDevice", "score": round(0.55 + (i % 4) * 0.1, 2)}]
            ),
            "geoHistory": [
                {"observedAt": _iso(last_seen - timedelta(days=7)), "country": home[0], "state": home[1], "city": home[2]},
                {"observedAt": _iso(last_seen), "country": home[0], "state": home[1], "city": home[2]},
            ],
            "synthetic": True,
        }
        # Deliberate, bounded schema variation for NoSQL normalization tests.
        if i % 10 == 0:
            doc["biometricCapabilities"] = ["face", "fingerprint"] if device_type == "Mobile" else []
        devices.append(doc)

    sessions: list[dict[str, Any]] = []
    methods = ["password+mfa", "passkey", "biometric"]
    activity_types = ["login", "viewBalance", "transferPreview", "payBill", "logout"]
    for i in range(1, session_count + 1):
        dev = devices[(i * 37 - 1) % device_count]
        started = anchor - timedelta(minutes=i * 31)
        duration = 3 + (i * 11) % 87
        failed = 2 if i % 29 == 0 else (1 if i % 11 == 0 else 0)
        unusual_geo = i % 43 == 0
        home = cities[(i * 7) % len(cities)]
        geo = ("GB", "ENG", "London") if unusual_geo else home
        activities = []
        for offset in range(2 + i % 4):
            activity: dict[str, Any] = {
                "type": activity_types[offset % len(activity_types)],
                "timestamp": _iso(started + timedelta(minutes=offset * 2)),
                "successful": not (failed and offset == 0),
            }
            if activity["type"] == "transferPreview":
                activity["details"] = {"amount": round(25 + (i % 400) * 1.17, 2), "currency": "USD"}
            activities.append(activity)
        risk = min(100, 8 + failed * 24 + (35 if unusual_geo else 0) + (22 if not dev["trusted"] else 0))
        session: dict[str, Any] = {
            "id": f"SESSION-{i:09d}",
            "sessionId": f"SESSION-{i:09d}",
            "customerId": dev["customerId"],
            "device": {
                "deviceId": dev["deviceId"],
                "deviceType": systems[(int(dev["deviceId"].split("-")[1]) - 1) % 3][2],
                "operatingSystem": dev["operatingSystem"],
                "appVersion": dev["appVersion"],
            },
            "loginTimestamp": _iso(started),
            "logoutTimestamp": _iso(started + timedelta(minutes=duration)),
            "ipAddress": f"192.0.2.{1 + i % 253}",
            "geo": {"country": geo[0], "state": geo[1], "city": geo[2]},
            "authentication": {"method": methods[i % len(methods)], "mfaUsed": i % 5 != 0, "failedAttempts": failed},
            "activities": activities,
            "sessionRiskScore": risk,
            "synthetic": True,
        }
        if i % 12 == 0:
            session["clientContext"] = {"language": "en-US", "accessibilityMode": i % 24 == 0}
        sessions.append(session)

    alerts: list[dict[str, Any]] = []
    severities = ["low", "medium", "high", "critical"]
    for i in range(1, alert_count + 1):
        cid_num = ((i * 13 - 1) % customer_count) + 1
        created = anchor - timedelta(hours=i * 9)
        status = "resolved" if i % 4 == 0 else ("investigating" if i % 3 == 0 else "open")
        alert: dict[str, Any] = {
            "id": f"ALERT-{i:08d}",
            "alertId": f"ALERT-{i:08d}",
            "customerId": customer_id(cid_num),
            "transactionId": transaction_id(1 + ((i * 7919) % 500_000)),
            "createdTimestamp": _iso(created),
            "alertType": "accountTakeover" if i % 3 == 0 else "transactionAnomaly",
            "severity": severities[i % len(severities)],
            "status": status,
            "signals": [
                {"name": "transactionRisk", "score": round(0.45 + (i % 5) * 0.1, 2)},
                {"name": "digitalBehavior", "score": round(0.35 + (i % 6) * 0.09, 2)},
            ],
            "investigatorNotes": [] if status == "open" else [{"timestamp": _iso(created + timedelta(hours=2)), "note": "Synthetic POC review"}],
            "synthetic": True,
        }
        if status == "resolved":
            alert["resolution"] = {"outcome": "falsePositive" if i % 8 else "confirmedFraud", "resolvedTimestamp": _iso(created + timedelta(hours=6))}
        alerts.append(alert)

    # Consume the seeded RNG in one controlled field so changing seed changes output.
    for session in sessions:
        session["telemetrySample"] = rng.randint(1000, 9999)
    return {"digitalSessions": sessions, "devices": devices, "fraudAlerts": alerts}


def generate_incremental(*, as_of: str = DEFAULT_AS_OF) -> dict[str, list[dict[str, Any]]]:
    """Return deterministic upserts: new session/alert plus changed device/alert."""
    anchor = _dt(as_of) + timedelta(days=1)
    new_session = {
        "id": "SESSION-INC-000001",
        "sessionId": "SESSION-INC-000001",
        "customerId": customer_id(1),
        "device": {"deviceId": device_id(1), "deviceType": "Mobile", "operatingSystem": {"name": "iOS", "version": "18.3"}, "appVersion": "6.1.1"},
        "loginTimestamp": _iso(anchor),
        "logoutTimestamp": _iso(anchor + timedelta(minutes=12)),
        "ipAddress": "192.0.2.250",
        "geo": {"country": "GB", "state": "ENG", "city": "London"},
        "authentication": {"method": "password+mfa", "mfaUsed": True, "failedAttempts": 3},
        "activities": [{"type": "login", "timestamp": _iso(anchor), "successful": False}],
        "sessionRiskScore": 93,
        "changeType": "insert",
        "synthetic": True,
    }
    changed_device = generate_initial(as_of=as_of, customer_count=100, device_count=1, session_count=1, alert_count=0)["devices"][0]
    changed_device.update({"trusted": False, "lastSeen": _iso(anchor), "riskSignals": [{"type": "impossibleTravel", "score": 0.94}], "changeType": "update"})
    base_alert = generate_initial(as_of=as_of, customer_count=100, device_count=1, session_count=1, alert_count=1)["fraudAlerts"][0]
    base_alert.update({"status": "resolved", "resolution": {"outcome": "confirmedFraud", "resolvedTimestamp": _iso(anchor)}, "changeType": "update"})
    new_alert = {
        "id": "ALERT-INC-000001",
        "alertId": "ALERT-INC-000001",
        "customerId": customer_id(1),
        "transactionId": transaction_id(1),
        "createdTimestamp": _iso(anchor),
        "alertType": "accountTakeover",
        "severity": "critical",
        "status": "open",
        "signals": [{"name": "failedAuthentication", "score": 0.97}, {"name": "untrustedDevice", "score": 0.91}],
        "investigatorNotes": [],
        "changeType": "insert",
        "synthetic": True,
    }
    return {"digitalSessions": [new_session], "devices": [changed_device], "fraudAlerts": [base_alert, new_alert]}


def _write_jsonl(path: Path, documents: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    docs = list(documents)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for document in docs:
            handle.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
    return len(docs)


def write_batch(root: Path, batch: dict[str, list[dict[str, Any]]], name: str) -> dict[str, Any]:
    target = root / name
    counts = {container: _write_jsonl(target / f"{container}.jsonl", batch[container]) for container in CONTAINERS}
    manifest = {"batch": name, "partitionKey": "/customerId", "counts": counts, "synthetic": True}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("data/cosmos"))
    parser.add_argument("--batch", choices=("initial", "incremental", "all"), default="all")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    parser.add_argument("--customers", type=int, default=100)
    parser.add_argument("--devices", type=int, default=150)
    parser.add_argument("--sessions", type=int, default=500)
    parser.add_argument("--alerts", type=int, default=60)
    args = parser.parse_args()
    manifests = []
    if args.batch in ("initial", "all"):
        manifests.append(write_batch(args.out_dir, generate_initial(seed=args.seed, as_of=args.as_of, customer_count=args.customers, device_count=args.devices, session_count=args.sessions, alert_count=args.alerts), "initial"))
    if args.batch in ("incremental", "all"):
        manifests.append(write_batch(args.out_dir, generate_incremental(as_of=args.as_of), "incremental"))
    print(json.dumps(manifests, indent=2))


if __name__ == "__main__":
    main()
