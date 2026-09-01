# Azure Cosmos DB for NoSQL mirroring

## Replication behavior

Unlike the Databricks integration, Cosmos DB Mirroring is physical database mirroring. It incrementally and continuously replicates Azure Cosmos DB for NoSQL documents into Delta tables in Fabric OneLake. Microsoft describes this as near-real-time replication without consuming source request units or affecting transactional workload performance in the [Cosmos mirroring tutorial](https://learn.microsoft.com/en-us/fabric/mirroring/azure-cosmos-db-tutorial) and [FAQ](https://learn.microsoft.com/en-us/fabric/mirroring/azure-cosmos-db-faq).

This is not a zero-copy shortcut. The mirrored `cosmos_bronze` item is the physical source-aligned Bronze replica. Delete operations are reflected, while TTL soft deletes are currently unsupported.

## Source configuration

The deployed source evidence is a serverless Cosmos DB for NoSQL account with `Continuous7Days` backup, database, and these containers:

| Container | Partition key | Role |
|---|---|---|
| `digitalSessions` | `/customerId` | Nested device, authentication, geo, and activity behavior |
| `devices` | `/customerId` | Trust, synthetic fingerprint, OS, risk signals, and geo history |
| `fraudAlerts` | `/customerId` | Alert-to-transaction linkage, severity, status, signals, notes, resolution |

All values are synthetic. Initial defaults are 500 sessions, 150 devices, and 60 alerts across 100 customers. The incremental batch inserts a session and alert, changes a device from trusted to untrusted, and resolves an existing alert.

The checked-in Bicep matches the deployed source posture: serverless capacity, continuous backup, local/key authentication disabled, and public network access disabled.

## Partition-key rationale

`/customerId` aligns with the dominant access pattern: customer investigation and cross-source risk aggregation. It distributes expected traffic across many customer values and keeps a customer's operational records addressable within one logical partition per container.

Limitations are explicit: queries by device/transaction/time/status alone fan out; a very active customer may become hot; customer reassignment can't update the partition key in place; and the POC population is too small to validate production distribution. Production sizing requires observed RU, storage, logical-partition, and skew metrics. Fabric Mirroring doesn't support custom target partitioning, so no separate mirrored layout is promised.

## Schema and nested values

Cosmos documents deliberately include bounded schema variation. Mirroring detects new properties and adds columns; missing properties become null. Mixed property types may be upcast where possible and otherwise become null. It is therefore unsafe to treat the mirror as a contract-enforced relational schema.

Current [Cosmos mirroring limitations](https://learn.microsoft.com/en-us/fabric/mirroring/azure-cosmos-db-limitations) state that nested objects and arrays appear as JSON strings in Warehouse tables. `OPENJSON` can selectively expand them in T-SQL. This POC uses Spark in `nb_silver_transform` to flatten commonly queried fields and retains arrays as JSON text where preserving the structure is more useful.

## Required configuration and authentication

- Only Azure Cosmos DB API for NoSQL is supported for this source type.
- The account must use 7-day or 30-day continuous backup. Continuous backup can't later be disabled, and its own restrictions apply.
- Supported Fabric connection authentication is a read-write account key or Microsoft Entra organizational account. Read-only keys and managed identity aren't supported for the mirror connection.
- Entra authentication requires `Microsoft.DocumentDB/databaseAccounts/readMetadata` and `Microsoft.DocumentDB/databaseAccounts/readAnalytics` data-plane permissions.
- Workspace Admin or Member is required to enable the mirror.

The repository's loaders use Entra ID and data-plane RBAC. No keys are stored. Note that the checked-in Bicep disables local/key authentication; therefore the intended Fabric connection path is an organizational account with the documented data-plane permissions.

## Private networking

Public Cosmos networking remains disabled. The deployed design uses an approved Cosmos private endpoint, private DNS linked to the POC VNet, a dedicated `Microsoft.PowerPlatform/vnetaccesslinks` subnet, outbound-only NAT for the gateway's Entra OAuth exchange, a Fabric VNet data gateway, and the workspace-specific Cosmos network ACL bypass.

The Fabric connection must be an Azure Cosmos DB v2 virtual-network connection using OAuth 2.0. Fabric's current mirroring UI can't select that connection when creating the mirror, so create the connection in **Manage connections and gateways**, then create the mirror with the Fabric REST API as described in Microsoft's [private-network mirroring guide](https://learn.microsoft.com/en-us/fabric/mirroring/azure-cosmos-db-private-network). Keep public networking as a break-glass fallback, not the normal path.

## Create and verify the mirror

After the private OAuth connection is ready:

1. Verify the Cosmos endpoint and all three containers using Entra authentication.
2. In Fabric create a `Mirrored Azure Cosmos DB` item named `cosmos_bronze`.
3. Use organizational-account authentication and select only `banking_poc` and the three containers.
4. Start replication and monitor each container until it is running and has an initial refresh/count.
5. Query the target SQL analytics endpoint and Lakehouse-access path.
6. Run `nb_source_validation`, then the full medallion pipeline.
7. Load the deterministic incremental batch, record source observation time and mirrored observation time, and confirm inserts and updates.

Stopping and restarting replication reseeds target tables from scratch. Do not use that as routine pause/resume. The continuous-backup commitment remains on the Azure account even if the Fabric mirror is removed.
