# Known limitations and findings

## Current findings

- Databricks external Delta tables, Fabric shortcuts, initial counts, and deterministic incremental changes are verified. Unity Catalog permissions still don't transfer to Fabric.
- The Cosmos private path is verified end to end: private endpoint, DNS, Fabric VNet data gateway, workspace ACL, OAuth connection, initial mirroring, and deterministic incremental changes. Public fallback wasn't used; this evidence does not claim the account's public-network setting was disabled afterward.
- The checked-in Cosmos Bicep now matches the deployed serverless/private-network source posture.
- Fabric source items, downstream medallion processing, baseline reconciliation, Warehouse serving, Viewer-context Warehouse RLS/DDM, Catalog descriptions/search, and incremental source propagation are verified. Git synchronization and OneLake CLS through SQL user-identity mode remain to be completed.

## Product limitations affecting the design

### Mirrored Azure Databricks catalog

- It mirrors metadata and uses shortcuts; it doesn't replicate Delta data.
- Underlying changes can take seconds to minutes to appear through Fabric; no latency SLA is claimed.
- Unity Catalog policies don't transfer to Fabric.
- Views, materialized/streaming/federated/Delta Sharing tables and tables with RLS/column-mask policies are unsupported; non-Delta external tables aren't shown.
- Schema/table renaming isn't supported for included/excluded objects.
- Source storage must be reachable by Fabric and firewalled ADLS requires the documented workspace-identity/trusted-access configuration.

Sources: [overview](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks), [limitations](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks-limitations), [security](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks-security).

### Mirrored Azure Cosmos DB

- Only API for NoSQL is supported for this Azure source scenario.
- Mirroring requires 7- or 30-day continuous backup. Continuous backup can't be disabled afterward, and multi-region write accounts are among continuous-backup restrictions.
- Nested objects/arrays are surfaced as JSON strings; schema/type variation can upcast or produce nulls.
- TTL-based soft deletes aren't supported; source deletes are reflected.
- Custom target partitioning isn't supported.
- Stop/start reseeds target tables.
- OneLake target data doesn't support private endpoints, customer-managed keys, or double encryption according to the current limitations page; source private networking uses the documented ACL bypass path.

Sources: [tutorial](https://learn.microsoft.com/en-us/fabric/mirroring/azure-cosmos-db-tutorial), [limitations](https://learn.microsoft.com/en-us/fabric/mirroring/azure-cosmos-db-limitations), [FAQ](https://learn.microsoft.com/en-us/fabric/mirroring/azure-cosmos-db-faq).

### POC implementation

- Silver and Gold are full refreshes. This is deterministic and retry-safe at current volume but not a production incremental-processing design.
- Audit tables live in `gold_lh`; no empty audit-only or Bronze Lakehouse is created.
- The risk score is an explainable synthetic heuristic, not trained, calibrated, or suitable for decisions.
- Cosmos seed scale and default 500,000-row Databricks scale don't establish performance, concurrency, skew, recovery, or cost characteristics.
- The two sources use source-relative 30-day watermarks. This is intentional for asynchronous clocks but differs from a single enterprise as-of timestamp.
- Warehouse security-bearing objects use local copies because RLS/DDM can't be applied to Lakehouse tables through cross-database views in this design.
- A temporary Viewer identity verified Warehouse DDM and RLS, then its role and credential were removed. The Lakehouse SQL endpoint remained in delegated-identity mode, where OneLake roles aren't the SQL enforcement model; its Viewer query could still read the restricted column. Switching to user identity mode is intentionally left as a documented follow-up because it changes the endpoint security model and can remove inline SQL metadata.
- The reused F4 may experience contention and can't be paused without considering other workspaces.
- Disaster recovery, production HA, SLA/SLOs, data retention, formal Purview policy design, semantic model/report deployment, and performance benchmarking are out of scope.

## Documentation freshness

Fabric mirroring, networking, Git, and security limitations change. Recheck every linked Microsoft Learn page before production adoption or a later demo. The statements here were reviewed on 2026-09-01.
