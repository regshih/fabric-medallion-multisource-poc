# Microsoft Fabric multisource medallion POC

This proof of concept combines synthetic Azure Databricks transaction data with synthetic Azure Cosmos DB digital-behavior data in Microsoft Fabric. It demonstrates source-native integration, substantive Silver quality processing, a cross-source Gold fraud-risk model, Warehouse serving, pipeline observability, and governance automation.

The key architectural point is that the two source integrations are intentionally different:

- The mirrored Azure Databricks catalog synchronizes Unity Catalog metadata and creates zero-copy shortcuts to the underlying Delta tables. It does **not** replicate the Delta data into OneLake.
- The mirrored Azure Cosmos DB database continuously and incrementally replicates documents into Delta tables in OneLake.

Both are treated as source-aligned Bronze access. The POC does not create a duplicate physical Bronze Lakehouse merely for naming symmetry. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Evidence status

Status is deliberately separated into local implementation, deployed infrastructure, and end-to-end verification. As of 2026-09-01:

| Area | Current evidence |
|---|---|
| Repository implementation | Implemented; 47 local tests pass |
| Azure resource group | Deployed |
| Azure Databricks workspace | Premium workspace deployed |
| Databricks source | Three external Unity Catalog Delta tables verified at 500,000 transactions, 500,000 risk rows, and 5,000 merchants |
| Databricks Fabric mirror | Running with automatic metadata sync and three working zero-copy shortcuts |
| Azure Cosmos DB | Serverless account, `Continuous7Days` backup, database, and three containers deployed |
| Cosmos network path | Private endpoint plus Fabric VNet data gateway verified; public fallback wasn't used |
| Fabric | Workspace deployed on a reused F4 capacity |
| Fabric items and source mirrors | Deployed and verified in the dedicated POC workspace |
| Pipeline, notebooks, Warehouse execution | Baseline run completed; all reconciliation checks pass; Warehouse RLS/DDM deployed |
| Fabric Git and governance | Catalog descriptions, discovery, OneLake role, Warehouse RLS/DDM verified; Fabric Git and Viewer-context enforcement remain |
| End-to-end and incremental run | Verified; baseline and incremental runs completed with all seven reconciliations passing |

Nothing in this table should be interpreted as a successful Fabric workload run until the validation evidence in [docs/validation.md](docs/validation.md) is completed.

## Analytical outcome

The primary Gold output is `AggCustomerRiskProfile`. It combines Databricks transaction volume and model scores with Cosmos sessions, failed authentication, device trust, geographic anomalies, and fraud alerts. The same question cannot be answered from either source alone.

Gold also contains:

- `DimCustomer`, `DimAccount`, `DimMerchant`, `DimDevice`, `DimDate`
- `FactTransactions`, `FactDigitalSessions`, `FactFraudAlerts`
- `AggCustomerRiskProfile`
- `reconciliation_results` and `control_pipeline_run_log`

## Repository map

| Path | Purpose |
|---|---|
| `generators/` | Deterministic synthetic source-data generation |
| `databricks/` | Initial and incremental Unity Catalog Delta jobs |
| `cosmos/` | Passwordless initial and incremental document loaders |
| `infra/cosmos/` | Cosmos DB Bicep and deployment wrapper |
| `infra/fabric/` | Fabric REST source mirrors, workspace/items, Git integration, and F-capacity controls |
| `infra/governance/` | Catalog descriptions/search, domain assignment, OneLake security |
| `notebooks/` | Source validation, Silver, Gold, Warehouse, reconciliation, audit, demo |
| `pipelines/` | `pl_multisource_medallion` definition with success/failure paths |
| `warehouse/` | Gold serving, RLS, masking, and validation SQL |
| `validation/`, `tests/` | Offline/live validators and local tests |
| `fabric_git/` | Dedicated target for Fabric-managed Git artifacts |

## Quick start

Prerequisites are Python 3.11+, Azure CLI, PowerShell 7+, an authenticated Microsoft Entra identity, and sufficient Azure/Fabric/Databricks permissions. Never put credentials in `.env`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
az login
python -m pytest -q
```

Populate `.env` with identifiers only. Follow [docs/deployment.md](docs/deployment.md) for the ordered deployment and [docs/runbook.md](docs/runbook.md) for operation, incremental changes, troubleshooting, and cleanup.

## Security

All records are deterministic synthetic test data. No production data or real-person data is allowed. Authentication uses Azure CLI/Microsoft Entra ID, Fabric connections, or managed/workspace identities. See [SECURITY.md](SECURITY.md).

## Documentation

- [Architecture and source lineage](ARCHITECTURE.md)
- [Databricks-to-Fabric integration](docs/databricks-fabric-integration.md)
- [Cosmos DB mirroring and partition design](docs/cosmos-fabric-mirroring.md)
- [Deployment guide](docs/deployment.md)
- [Operations runbook, cost, and cleanup](docs/runbook.md)
- [Validation and evidence checklist](docs/validation.md)
- [Live validation results](docs/live-validation-results.md)
- [Governance and security model](docs/governance-security.md)
- [Known limitations](docs/known-limitations.md)

## Official documentation

Product behaviors in this repository are based on current Microsoft documentation:

- [Mirroring overview](https://learn.microsoft.com/en-us/fabric/mirroring/overview)
- [Mirroring Azure Databricks Unity Catalog](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks)
- [Azure Databricks mirrored catalog tutorial](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks-tutorial)
- [Azure Databricks mirrored catalog limitations](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks-limitations)
- [Azure Cosmos DB mirroring tutorial](https://learn.microsoft.com/en-us/fabric/mirroring/azure-cosmos-db-tutorial)
- [Azure Cosmos DB mirroring limitations](https://learn.microsoft.com/en-us/fabric/mirroring/azure-cosmos-db-limitations)
- [OneLake security](https://learn.microsoft.com/en-us/fabric/onelake/security/fabric-onelake-security)
- [OneLake catalog](https://learn.microsoft.com/en-us/fabric/governance/onelake-catalog-overview)
