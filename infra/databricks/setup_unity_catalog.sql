-- Run as a Unity Catalog metastore admin only when a dedicated catalog is needed.
-- External location and credential names are injected by deployment; source
-- tables are external Delta so Fabric can read them through OneLake shortcuts.
CREATE CATALOG IF NOT EXISTS fabric_multisource_poc
  COMMENT 'Synthetic multisource Fabric medallion POC';

CREATE SCHEMA IF NOT EXISTS fabric_multisource_poc.banking_source
  COMMENT 'Databricks source-aligned synthetic transaction and risk data';

-- Replace these example principals before execution. Keep least privilege and
-- use account groups/service principals managed through Microsoft Entra ID.
-- GRANT USE CATALOG ON CATALOG fabric_multisource_poc TO `poc-data-engineers`;
-- GRANT USE SCHEMA, SELECT ON SCHEMA fabric_multisource_poc.banking_source TO `fabric-reader`;
