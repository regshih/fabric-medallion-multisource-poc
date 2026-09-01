# Validation and evidence

## Evidence rules

Use these labels consistently:

- **Implemented**: source/configuration exists locally and local tests pass.
- **Deployed**: a resource exists in Azure or Fabric.
- **Executed**: a job/pipeline completed.
- **Verified**: an explicit check observed the expected result.
- **Blocked**: a named prerequisite prevents the next check.

Never infer `Verified` from `Deployed`, or successful mirroring from a source resource existing.

## Current evidence snapshot

| Check | Status | Evidence/next action |
|---|---|---|
| Local unit/contract tests | Verified | 47 passed on 2026-09-01 |
| Azure resource group | Deployed | Do not publish IDs |
| Premium Databricks workspace | Verified | Premium workspace and single-node job execution succeeded |
| Databricks tables/counts | Verified | Initial 500,000 transactions/risk rows and 5,000 merchants; incremental 510,000/510,000/5,001 visible through Fabric shortcuts |
| Databricks metastore external access | Verified | Enabled by metastore administrator |
| Cosmos serverless account/database/containers | Deployed | `Continuous7Days`; three `/customerId` containers |
| Cosmos source records | Verified | Initial 10,000 sessions, 5,000 devices, and 1,000 alerts; incremental insert/update batch loaded passwordlessly |
| Cosmos Fabric connectivity | Verified | Private endpoint and Fabric VNet data gateway OAuth path; public fallback wasn't used |
| Fabric workspace on reused F4 | Verified | Dedicated workspace inventory and deployed items queried through REST |
| Databricks/Cosmos Fabric source items | Verified | Both source items running; SQL and Spark access paths returned expected counts |
| Silver/Gold/pipeline/Warehouse | Verified baseline | All seven reconciliations pass, six quarantine tables are empty, serving counts match, two DDM masks and RLS policy are present |
| Governance/Catalog/Git | Partial | Descriptions, Catalog discovery, and OneLake role applied; least-privileged user tests and Fabric Git PAT connection remain |
| Incremental propagation | Verified | Insert and update changes reached Silver, Gold, reconciliation, and Warehouse with expected counts |

## Local checks

```powershell
python -m pytest -q
python generators\generate_cosmos_data.py --batch all
python validation\validate_cosmos.py --mode files --data-dir data\cosmos\initial
python generators\generate_databricks_data.py --rows 1000 --customers 100 --merchants 25 --output-dir generated\databricks-smoke
python validation\validate_databricks.py --input-dir generated\databricks-smoke --base-rows 1000
```

Generated data is ignored and must not be committed as execution evidence.

## Source and mirror checks

For every source table/container record:

- existence and expected schema/properties;
- source count and observation time;
- mirror access type (`shortcut` for Databricks, `Delta replica` for Cosmos);
- Fabric-visible count and observation time;
- sample synthetic business-key shape, without dumping records containing fingerprints/IP-like fields;
- initial and incremental behavior.

For Databricks, equal row counts compare two access paths to the same Delta data; they do not demonstrate replication. For Cosmos, source-versus-Fabric counts validate a replicated target snapshot at an observation time.

## Pipeline acceptance

A valid initial run requires:

1. both source-validation activities succeeded;
2. Silver wrote all six valid tables and six quarantine tables;
3. Gold wrote five dimensions, three facts, and `AggCustomerRiskProfile`;
4. Warehouse publication completed and serving objects query successfully;
5. reconciliation has no `FAIL` rows;
6. stage log contains start/end, status, duration, rows read/written, and run ID;
7. a cross-source customer profile and alert-to-transaction investigation return expected synthetic links.

Capture the Fabric run ID and UTC timestamps, but keep tenant/workspace/resource IDs out of public documentation.

## Security validation

- Test OneLake column restrictions using a Viewer/read-only identity; Admin/Member/Contributor aren't constrained by OneLake data-access roles.
- Test Warehouse DDM using a least-privileged Viewer without `CONTROL` or `UNMASK`.
- Test Warehouse RLS with the intended investigator and non-investigator principals.
- Confirm Unity Catalog permissions did not implicitly carry into Fabric.
- Review item sharing, workspace roles, connections, and source credential ownership.
- Run the public-release secret review described in `SECURITY.md` over both working tree and Git history.

## Independent review checklist

An independent reviewer should challenge:

- whether the diagram correctly distinguishes shortcuts from replication;
- whether every status claim has a reproducible observation;
- whether the Gold aggregate demonstrably combines both sources;
- whether source-relative time windows and score logic are documented;
- whether quarantine math accounts for rejected rows;
- whether incremental updates, not only inserts, appear downstream;
- whether governance controls were tested using a non-admin identity;
- whether Git contains only supported artifact definitions and no secrets;
- whether cleanup avoids the shared F4 and any shared resource group assets.
