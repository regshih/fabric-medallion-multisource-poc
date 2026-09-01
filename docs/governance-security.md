# Governance and security

## Layered authorization

The POC has distinct security planes. Source permissions aren't automatically target permissions.

| Boundary | Control |
|---|---|
| Azure management | Azure RBAC for resource management |
| Databricks source | Unity Catalog privileges and external-access authorization |
| Cosmos source | Cosmos DB data-plane RBAC for loaders/mirror connection |
| Fabric control plane | Workspace roles, item permissions, sharing |
| OneLake data plane | OneLake security roles and table/row/column constraints |
| Warehouse | T-SQL permissions, RLS, and dynamic data masking |

[Microsoft's Databricks mirroring security documentation](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks-security) says Unity Catalog policies and permissions aren't mirrored. Recreate least-privilege access in Fabric and review the source connection owner's scope.

## Implemented governance automation

- `catalog_setup.py` sets meaningful descriptions and can assign an existing approved domain. It defaults to dry-run.
- `catalog_search.py` verifies discoverability through the Fabric Catalog Search API.
- `onelake_data_access.py` preserves the full role set, applies ETag concurrency, performs a server dry run, and can restrict `DimDevice` columns so `deviceFingerprint` isn't permitted by the selected read role.
- Warehouse scripts publish selected Gold objects, apply RLS/masking where supported, and inventory policies.
- Pipeline notebooks attach run lineage and write auditable stage/reconciliation tables.

These controls are locally implemented but not yet applied or independently verified in the live Fabric workspace.

## OneLake role caveat

Per the [OneLake data security overview](https://learn.microsoft.com/en-us/fabric/onelake/security/fabric-onelake-security), OneLake security roles grant constrained access to Viewers or users with item Read permission. Workspace Admins, Members, and Contributors retain broad item data access and aren't affected by those roles. Enforcement must therefore be tested using a least-privileged identity, not the deployment administrator.

The Lakehouse SQL analytics endpoint also has an access-mode boundary. [Microsoft's SQL endpoint guidance](https://learn.microsoft.com/en-us/fabric/onelake/security/sql-analytics-endpoint-onelake-security) states that OneLake roles are enforced through SQL only in **user identity** mode; the default delegated-identity mode uses SQL permissions and the item owner's OneLake identity instead. This POC applied the OneLake column allowlist but left the endpoint in delegated mode to avoid the documented metadata changes caused by switching modes. A Viewer test consequently confirmed that the SQL endpoint did not enforce that allowlist. Switch deliberately to user identity mode and repeat the Viewer test before claiming SQL-endpoint OneLake CLS enforcement.

The `DefaultReader` role may grant `ReadAll` by default. Review its members and rules before applying the repository helper. The helper performs a full-replace API update safely, but the semantic decision to modify `DefaultReader` still requires an access review.

## Catalog and lineage

Descriptions make items discoverable by purpose/source/layer. The intended domain is `Retail Banking Analytics` if an approved domain exists and permissions allow assignment. OneLake Catalog should expose owners, location, descriptions, lineage, permissions, endorsements/tags, and refresh state as supported by each item type; see the [OneLake Catalog overview](https://learn.microsoft.com/en-us/fabric/governance/onelake-catalog-overview) and [item details](https://learn.microsoft.com/en-us/fabric/governance/onelake-catalog-item-details).

Do not claim domain assignment, endorsement, sensitivity labels, catalog discoverability, or lineage until each is observed in the live tenant.

## Synthetic sensitive-like fields

`deviceFingerprint`, account/customer identifiers, and reserved-documentation IP addresses are fictional but are treated as sensitive-like fields so the POC can demonstrate controls. They aren't evidence of production PII handling. Public screenshots/query output should still avoid row-level dumps.

## Fabric Git

The `/fabric_git` folder is reserved for Fabric-managed definitions. Fabric Git isn't a data backup and should never contain notebook output or connection credentials. Follow [Fabric Git integration concepts and limitations](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-integration-process): only supported items sync, a workspace admin manages the connection, synchronization is one direction at a time, and Fabric can remove files within item folders that aren't part of item definitions.

Review the exact workspace diff and run the security gate before every commit from Fabric.
