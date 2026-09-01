#!/usr/bin/env python3
"""Idempotently load the generated initial Cosmos DB snapshot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cosmos.common import load_directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/cosmos/initial"))
    parser.add_argument("--endpoint")
    parser.add_argument("--database-name")
    args = parser.parse_args()
    print(json.dumps(load_directory(args.data_dir, endpoint=args.endpoint, database_name=args.database_name), indent=2))


if __name__ == "__main__":
    main()
