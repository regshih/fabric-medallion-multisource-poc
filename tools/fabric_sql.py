#!/usr/bin/env python3
"""Run Fabric SQL queries or GO-delimited scripts with Azure CLI authentication."""

from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

import pyodbc
from azure.identity import AzureCliCredential


SQL_COPT_SS_ACCESS_TOKEN = 1256


def connect(server: str, database: str) -> pyodbc.Connection:
    token = AzureCliCredential().get_token("https://database.windows.net/.default").token
    token_bytes = token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    connection_string = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={server};Database={database};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30"
    )
    return pyodbc.connect(
        connection_string,
        attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct},
        autocommit=True,
    )


def split_batches(sql: str) -> list[str]:
    return [batch.strip() for batch in re.split(r"(?im)^\s*GO\s*(?:--.*)?$", sql) if batch.strip()]


def rows_as_dicts(cursor: pyodbc.Cursor) -> list[dict[str, object]]:
    columns = [column[0] for column in cursor.description or []]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True)
    parser.add_argument("--database", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--query")
    source.add_argument("--file", type=Path)
    args = parser.parse_args()

    with connect(args.server, args.database) as connection:
        cursor = connection.cursor()
        if args.query:
            cursor.execute(args.query)
            print(json.dumps(rows_as_dicts(cursor), indent=2, default=str))
            return

        sql = args.file.read_text(encoding="utf-8")
        batches = split_batches(sql)
        for batch in batches:
            cursor.execute(batch)
        print(json.dumps({"database": args.database, "batchesExecuted": len(batches)}))


if __name__ == "__main__":
    main()
