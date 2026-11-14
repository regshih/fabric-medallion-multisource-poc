# Official documentation reviewed

Reviewed November 13, 2026. Product documentation and Preview capabilities can change. Installed SDK declarations and CLI source were inspected to verify the exact pinned 1.36.2 behavior used by the code.

| Source | Decision supported |
|---|---|
| [Fabric Apps overview](https://learn.microsoft.com/en-us/fabric/apps/overview) | Preview status, managed app SQL/hosting, tenant and capacity prerequisites. |
| [Create with Rayfin CLI](https://learn.microsoft.com/en-us/fabric/apps/create-app-with-cli) | Scaffold/layout alternatives, CLI dry run and deployment. Default `rayfin dev` can deploy a cloud backend; local demo uses Vite only. |
| [Fabric data connectors](https://learn.microsoft.com/en-us/fabric/apps/connectors) | Warehouse and Lakehouse connectors, read operations, explicit delegated identity, keyless entities, schema discovery caveats, version-matched packages. |
| [Authentication](https://learn.microsoft.com/en-us/fabric/apps/authentication) | Entra/Fabric session behavior and deployment auth requirements. |
| [Fabric SSO implementation](https://learn.microsoft.com/en-us/fabric/apps/fabric-authentication) | Popup gesture requirement, embedded initialization, public Vite variable aliases. |
| [Data models](https://learn.microsoft.com/en-us/fabric/apps/data-models) | TypeScript schema and managed persistence. |
| [Data permissions](https://learn.microsoft.com/en-us/fabric/apps/data-permissions) | Creator policies and action-scoped role declarations. |
| [Fabric region availability](https://learn.microsoft.com/en-us/fabric/admin/region-availability) | Verify approved deployment region before creating an app. |
| [Unity Catalog mirroring](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks) | Metadata synchronization and shortcut access without Delta replication; SQL endpoint access path. |
| [Databricks mirror security](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks-security) | Source and Fabric authorization are separate. |
| [Databricks mirror limitations](https://learn.microsoft.com/en-us/fabric/mirroring/azure-databricks-limitations) | Recheck current table-feature/network requirements rather than changing original source tables. |
| [Microsoft Rayfin source](https://github.com/microsoft/rayfin) and [official templates](https://github.com/microsoft/awesome-rayfin) | SDK package names, flat-project examples, schema registration. No template credentials, deployment IDs or sample keys copied. |
| [Vite 8 migration](https://vite.dev/guide/migration) | Oxc does not lower Stage 3 decorators. This app lowers only Rayfin models through TypeScript; tests verify their runtime metadata. |

The existing repository's integration evidence is historical, not a fresh cloud workload run. This implementation verified workspace/item visibility and inactive capacity through read-only Fabric REST calls, then stopped before any source SQL query, capacity resume, DDL or deployment.
