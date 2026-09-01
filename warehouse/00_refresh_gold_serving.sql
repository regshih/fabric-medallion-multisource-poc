-- gold_wh refresh step 1 of 2: publish the Gold serving objects.
--
-- Run this script in gold_wh after nb_gold_build completes, then run
-- 10_apply_security.sql.  Security is deliberately removed before the three
-- local CTAS copies are replaced because Fabric attaches RLS/DDM metadata to
-- the physical Warehouse table, not to the Lakehouse source object.
--
-- Lakehouse-backed views remain zero-copy.  Only objects that need Warehouse
-- security metadata are copied locally.

DROP SECURITY POLICY IF EXISTS Security.CustomerRiskPolicy;
GO

DROP VIEW IF EXISTS dbo.DimCustomer;
DROP VIEW IF EXISTS dbo.DimDevice;
DROP VIEW IF EXISTS dbo.AggCustomerRiskProfile;
GO

DROP TABLE IF EXISTS dbo._base_DimCustomer;
DROP TABLE IF EXISTS dbo._base_DimDevice;
DROP TABLE IF EXISTS dbo._base_AggCustomerRiskProfile;
GO

CREATE TABLE dbo._base_DimCustomer AS
SELECT * FROM gold_lh.dbo.DimCustomer;
GO

CREATE TABLE dbo._base_DimDevice AS
SELECT * FROM gold_lh.dbo.DimDevice;
GO

CREATE TABLE dbo._base_AggCustomerRiskProfile AS
SELECT * FROM gold_lh.dbo.AggCustomerRiskProfile;
GO

CREATE OR ALTER VIEW dbo.DimCustomer AS
SELECT * FROM dbo._base_DimCustomer;
GO

CREATE OR ALTER VIEW dbo.DimDevice AS
SELECT * FROM dbo._base_DimDevice;
GO

CREATE OR ALTER VIEW dbo.AggCustomerRiskProfile AS
SELECT * FROM dbo._base_AggCustomerRiskProfile;
GO

CREATE OR ALTER VIEW dbo.DimAccount AS
SELECT * FROM gold_lh.dbo.DimAccount;
GO

CREATE OR ALTER VIEW dbo.DimMerchant AS
SELECT * FROM gold_lh.dbo.DimMerchant;
GO

CREATE OR ALTER VIEW dbo.DimDate AS
SELECT * FROM gold_lh.dbo.DimDate;
GO

CREATE OR ALTER VIEW dbo.FactTransactions AS
SELECT * FROM gold_lh.dbo.FactTransactions;
GO

CREATE OR ALTER VIEW dbo.FactDigitalSessions AS
SELECT * FROM gold_lh.dbo.FactDigitalSessions;
GO

CREATE OR ALTER VIEW dbo.FactFraudAlerts AS
SELECT * FROM gold_lh.dbo.FactFraudAlerts;
GO

