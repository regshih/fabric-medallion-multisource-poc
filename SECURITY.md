# Security

This public proof of concept contains synthetic data and no credentials. Use Azure CLI / Microsoft Entra ID authentication and Fabric connections. Never place passwords, account keys, SAS tokens, PATs, service-principal secrets, connection strings, or bearer tokens in files, notebook output, command history captures, pipeline JSON, or Fabric Git artifacts.

## Local configuration

Copy `.env.example` to `.env` and populate identifiers only. `.env` is ignored. Prefer `az login`, Databricks OAuth, Fabric organizational-account connections, managed identities, and Fabric workspace identity.

## Public-release gate

Run `python tools/security_scan.py --working-tree --git-history` before every public release. Review all findings manually. If a real credential was ever committed, revoke/rotate it first, then remove it from the full Git history before publishing.

If that scanner is not yet present in the working tree, the public-release gate is **not complete**. Use an approved secret scanner against both the working tree and every reachable Git commit, and manually inspect `.env*`, notebooks/outputs, pipeline JSON, Fabric Git artifacts, generated data, logs, and documentation. Search at minimum for `AccountKey=`, `SharedAccessSignature=`, `Password=`, `pwd=`, `client_secret`, `access_token`, `Bearer`, `sig=`, and `Authorization:`. Record only pass/fail and affected file paths; never paste a discovered value into an issue or report.

Before publishing, also verify that Azure subscription/tenant/resource IDs, workspace/item IDs, account endpoints, principal IDs, job run URLs, and screenshots containing tenant context haven't been added to tracked documentation. These identifiers are not credentials, but this public POC intentionally keeps environment inventory private.

Notebook source files are committed without outputs. Generated data and logs are ignored.

## Synthetic-data statement

Every customer, account, transaction, device, session, merchant, IP address, and alert is generated for this POC. Identifiers use conspicuous formats such as `CUST-######`, `TXN-#########`, and `DEVICE-######`; no production or real-person data is permitted.

## Reporting

If a credential is found, do not open a public issue containing it. Revoke it and remove it locally before reporting the affected file path to the repository owner.
