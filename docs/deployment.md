# Deployment guide

This guide is ordered so that prerequisites and source access are proven before Fabric transformations are deployed. Commands contain placeholders only. Keep environment-specific IDs in ignored `.env` or shell variables.

## 1. Authenticate and test locally

```powershell
az login
az account set --subscription '<subscription-id>'
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m pytest -q
```

Expected current local baseline: `39 passed`. A local pass proves definitions and helper behavior; it does not prove Azure or Fabric execution.

## 2. Configure identifiers

Populate `.env` from `.env.example` with resource names/IDs/endpoints only. Do not add keys, tokens, passwords, SAS strings, connection strings, or client secrets. Verify the intended Azure subscription, tenant, resource group, region, reused F4 capacity, and new Fabric workspace name before continuing.

## 3. Cosmos source

The Bicep provisions a serverless NoSQL account, continuous backup, database, three `/customerId` containers, and data-plane RBAC for the loader identity:

```powershell
.\infra\cosmos\setup.ps1 `
  -SubscriptionId '<subscription-id>' `
  -ResourceGroup '<resource-group>' `
  -AccountName '<globally-unique-account-name>' `
  -Location '<region>'
```

The intended path keeps public networking disabled. Provision a Cosmos private endpoint and DNS, a dedicated Fabric VNet data gateway subnet, outbound access for OAuth, `EnableFabricNetworkAclBypass`, and the workspace-specific network ACL bypass before creating the mirror.

Generate, validate, and load the synthetic documents:

```powershell
python generators\generate_cosmos_data.py --batch all
python validation\validate_cosmos.py --mode files --data-dir data\cosmos\initial
python cosmos\load_initial.py --endpoint '<cosmos-endpoint>' --database-name banking_poc
python validation\validate_cosmos.py --mode live --endpoint '<cosmos-endpoint>' --database-name banking_poc
```

## 4. Databricks source

Use the deployed Premium workspace and a Unity Catalog-enabled compute/job identity. Import and run `databricks/01_seed_delta_tables.py` with the desired catalog/schema parameters. The initial defaults target 500,000 transactions, 500,000 scores, and 5,000 merchants. Confirm the job has succeeded before proceeding; a running job isn't proof of table creation.

External data access must be enabled on the metastore by a metastore admin. Then grant the Fabric connection identity the narrow source privileges including `EXTERNAL USE SCHEMA` and only the catalog/schema/table access it needs. Do not grant broad metastore administration to solve the connection.

Validate in Databricks:

```text
%run /path/to/validation/validate_databricks
```

or run the validation module in a Spark context. Record table schemas/counts and the job run link in a private evidence log without exporting credentials.

## 5. Create source-aligned Fabric items

These two portal operations precede the repository deployment because `infra/fabric/deploy.py` resolves the source items by name.

1. Create `databricks_bronze` using **Mirrored Azure Databricks catalog**. Select the configured catalog/schema and exactly `transactions`, `transaction_risk`, and `merchants`. This is metadata sync plus zero-copy shortcuts.
2. Create `cosmos_bronze` using **Mirrored Azure Cosmos DB**. Select `banking_poc` and exactly `digitalSessions`, `devices`, and `fraudAlerts`. This is continuous physical replication.
3. Verify both source items and their six tables before deploying downstream items.

Databricks external data access and the private Cosmos network path must be verified first. The private Cosmos OAuth connection is created interactively in **Manage connections and gateways**; the mirror that references it is created with REST. Do not fabricate item IDs in `.env` to bypass either source.

## 6. Deploy Fabric medallion items

The deployment script uses Azure CLI/Entra credentials through `DefaultAzureCredential`. It idempotently creates or updates the new workspace, `silver_lh`, `gold_lh`, `gold_wh`, six orchestration notebooks, the Gold consumption-demo notebook, and the pipeline. It reuses the configured capacity; it doesn't provision or resize it.

```powershell
python infra\fabric\deploy.py
```

Inspect the returned item inventory, then run:

```powershell
python infra\fabric\deploy.py --run --run-date 2026-08-31
```

The consumption-demo notebook is deployed but intentionally not part of the scheduled orchestration chain; run it after Gold exists.

## 7. Apply governance and Warehouse controls

Descriptions default to dry-run:

```powershell
python infra\governance\catalog_setup.py
python infra\governance\catalog_setup.py --apply
python infra\governance\catalog_search.py --search multisource
```

Assign an existing domain only when the approved domain ID is available:

```powershell
python infra\governance\catalog_setup.py --assign-domain --domain-id '<domain-id>' --apply
```

OneLake column restriction also defaults to dry-run and performs a server dry run before applying:

```powershell
python infra\governance\onelake_data_access.py
python infra\governance\onelake_data_access.py --apply
```

Execute Warehouse scripts in numeric order as documented in `warehouse/README.md`. Configure a deploy-time Entra risk-investigator principal using the template; never commit an identity or token. Validate masking using a least-privileged Viewer, because privileged workspace roles can see unmasked data.

## 8. Connect Fabric Git

From workspace settings, connect the new workspace to the intended GitHub repository/branch and `/fabric_git` directory. Only a workspace admin can manage the connection. Review the proposed synchronization before committing because Fabric can overwrite item-definition folder contents. Confirm supported items appear; unsupported items must be documented rather than claimed.

Follow the current [Fabric Git integration process](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-integration-process). The connection and synchronization are not yet verified in this POC.

## 9. Evidence gate

Complete [validation.md](validation.md) before labeling the POC complete. At minimum capture source object/count validation, mirror behavior, a successful pipeline run ID, quarantine and reconciliation results, Gold cross-source output, Warehouse queries/security tests, incremental propagation observations, catalog discovery, Git sync, and a secret scan.
