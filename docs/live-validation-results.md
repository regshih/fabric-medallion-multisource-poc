# Live validation results

The following checks were executed on 2026-09-01 using deterministic synthetic data. Environment-specific resource, workspace, item, principal, and run identifiers are intentionally omitted from this public-repository record.

## Source and medallion counts

| Object | Baseline | After incremental batch | Silver | Gold/Warehouse |
|---|---:|---:|---:|---:|
| Databricks transactions | 500,000 | 510,000 | 510,000 | 510,000 |
| Databricks transaction risk | 500,000 | 510,000 | 510,000 | n/a at independent fact grain |
| Databricks merchants | 5,000 | 5,001 | 5,001 | 5,001 |
| Cosmos digital sessions | 10,000 | 10,001 | 10,001 | 10,001 |
| Cosmos devices | 5,000 | 5,000 | 5,000 | 5,000 |
| Cosmos fraud alerts | 1,000 | 1,001 | 1,001 | 1,001 |

Databricks values are two query paths over the same external Delta data through zero-copy shortcuts; they aren't evidence of replication. Cosmos values compare the source workload with its physical OneLake mirror at the observation time.

## Pipeline and quality

- The baseline and incremental eight-activity pipeline runs completed with no failure reason.
- Both source validations, Silver, Gold, Warehouse contract publication, reconciliation, and terminal audit logging succeeded.
- A targeted post-review check ran both source validations with the same run key and verified distinct `source_validation_databricks` and `source_validation_cosmos` audit rows, eliminating the prior parallel-stage overwrite risk.
- All seven baseline and incremental reconciliation rows are `PASS`, including the Cosmos fraud-alert to Databricks transaction relationship.
- All six Silver quarantine tables contain zero rows for the generated dataset.
- `AggCustomerRiskProfile` contains 50,000 cross-source customer rows.
- The incremental batch verified 10,000 new Databricks transactions, 10,000 new risk rows, 1,000 deterministic risk-score updates, one new merchant, one new Cosmos session, one device update, one existing-alert resolution, and one new alert.

## Serving and governance

- Warehouse zero-copy views and security-bearing local copies returned the incremental counts above.
- Two dynamic data masks are present on the local customer/device copies.
- The customer-risk security policy is enabled and schema-bound.
- A temporary Viewer identity observed a masked customer ID and zero visible high-risk rows; its workspace assignment and short-lived credential were removed immediately afterward.
- The Gold OneLake `DefaultReader` role replacement passed the server dry run and was applied with ETag concurrency protection while preserving existing roles/rules.
- Catalog descriptions were applied and OneLake Catalog discovery returned the POC items.

## Remaining user-context checks

- The OneLake allowlist wasn't enforced through the Lakehouse SQL endpoint while it remained in delegated-identity mode: the temporary Viewer could read the restricted column. Per the [documented SQL endpoint access modes](https://learn.microsoft.com/en-us/fabric/onelake/security/sql-analytics-endpoint-onelake-security), SQL enforcement of OneLake roles requires user identity mode. That security-model switch wasn't made because it can remove inline SQL metadata; it remains an explicit follow-up rather than a successful claim.
- Fabric Git requires a classic or fine-grained GitHub PAT. GitHub CLI OAuth tokens are rejected by Fabric, so Git initialization remains pending that short-lived credential.
