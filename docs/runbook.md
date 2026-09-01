# Operations runbook

## Daily/operator flow

1. Confirm the reused F4 capacity is active.
2. Confirm Databricks table access and Cosmos replication states are healthy.
3. Start `pl_multisource_medallion`, optionally passing an ISO `run_date`.
4. Monitor both parallel source validations, then Silver, Gold, Warehouse, reconciliation, and terminal logging.
5. Query `gold_lh.control_pipeline_run_log` and `gold_lh.reconciliation_results` by `pipeline_run_id`.
6. Treat any reconciliation `FAIL` as a failed run. Investigate `WARN` relationship results explicitly.

Capacity inspection and safe controls:

```powershell
python infra\fabric\capacity.py status
python infra\fabric\capacity.py resume
python infra\fabric\capacity.py suspend --confirm-name '<exact-capacity-name>'
```

Because the F4 capacity is reused, suspension affects other attached workspaces. Confirm ownership and workload activity before suspending it.

## Incremental demonstration

Only run this after a successful initial end-to-end baseline.

1. Record initial Databricks/Cosmos source counts, mirror counts, and UTC observation time.
2. Run `databricks/02_apply_incremental_batch.py` in the configured Databricks job.
3. Load the deterministic Cosmos incremental documents:

   ```powershell
   python cosmos\load_incremental.py --endpoint '<cosmos-endpoint>' --database-name banking_poc
   ```

4. Poll the mirrored objects at a reasonable interval and record first visibility time for each source separately.
5. Rerun the medallion pipeline with a new run ID/date.
6. Verify inserts and updates in Silver/Gold, including the untrusted device, resolved/new alert, new session, new transactions, changed risk scores, and new merchant.
7. Save measured propagation observations as POC results; do not claim an SLA or imply equal semantics for shortcut visibility and Cosmos replication.

## Failure triage

| Symptom | Likely check |
|---|---|
| Databricks catalogs aren't visible | Metastore external access, `EXTERNAL USE SCHEMA`, source privileges, connection identity |
| Databricks table shortcut returns 403 | ADLS access/firewall, Fabric workspace identity, trusted workspace access |
| Cosmos mirror can't connect | Private networking/Network ACL Bypass, organizational-account RBAC, continuous backup |
| Cosmos container stuck or absent | Selected database/container, replication status, supported API/account configuration |
| Source validation fails | Required columns, source item IDs, source table accessibility |
| Silver count mismatch | Quarantine count, deduplication key/order, malformed nested JSON, source schema evolution |
| Alert/transaction relationship warns | Confirm synthetic key range and Databricks initial/incremental batch completion |
| Warehouse publish fails | Gold SQL endpoint readiness, object names, Warehouse permissions, ordered SQL contract |
| Masking appears ineffective | Test as a least-privileged Viewer without `CONTROL`/`UNMASK` |
| Git update fails | Unsupported/dependent items, folder/path limits, workspace admin permission, sync direction |

For product-specific diagnosis, use the [Fabric mirroring troubleshooting guide](https://learn.microsoft.com/en-us/fabric/mirroring/troubleshooting).

## Cost controls

The principal cost surfaces are the reused F4 capacity while active, Databricks job compute, Cosmos serverless operations/storage plus continuous backup, source storage, and any Fabric mirror/OneLake storage. Prices vary by region, agreement, runtime, and data volume, so this repository intentionally provides no dollar estimate.

- Terminate Databricks job compute after seed/incremental work and use auto-termination.
- Avoid repeated full local data generation when a smaller validation sample is sufficient.
- Keep the Cosmos workload synthetic and bounded; inspect serverless request metrics.
- Pause the F4 only with the capacity owner's approval because it is shared.
- Remove unused Fabric items/mirrors after evidence capture.
- Remember that enabling Cosmos continuous backup is not reversible for the account according to current product limitations.

Use the official [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/) and Fabric Capacity Metrics app for an environment-specific estimate.

## Cleanup

Cleanup is destructive. First export non-sensitive evidence, verify exact targets in the Azure portal/CLI and Fabric workspace, and confirm the resource group contains only POC resources.

Recommended order:

1. Disconnect Fabric Git if the POC branch/directory should stop syncing.
2. Delete the two Fabric source items/mirrors and downstream notebooks, pipeline, Lakehouses, and Warehouse; then delete the dedicated POC workspace.
3. Do **not** delete or suspend the reused F4 capacity as part of workspace cleanup.
4. Terminate Databricks compute. Delete only the POC catalog/schema/tables and, if dedicated, the POC Databricks workspace after verifying its exact resource.
5. Delete only the dedicated Cosmos POC account, or delete the resource group only after confirming every contained resource belongs to this POC.
6. Remove local `.env`, generated data, and non-committed evidence containing environment IDs. These are ignored and not recoverable unless separately backed up.
7. Review billing/resource inventory after cleanup.

Do not issue a blanket resource-group delete when the group is shared or its contents haven't been inspected.

