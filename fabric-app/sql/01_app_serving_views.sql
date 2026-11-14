-- OPTIONAL additive serving contract. Run only in an APPROVED gold_wh environment.
-- No existing tables, views, policies or pipeline definitions are modified.
-- Run this after warehouse/00_refresh_gold_serving.sql + 10_apply_security.sql.
-- Every detail view joins the RLS-protected profile, keeping high-risk row access
-- under the existing Warehouse security policy. No bigint surrogate enters JS.
IF SCHEMA_ID(N'risk_app') IS NULL EXEC(N'CREATE SCHEMA risk_app');
GO
CREATE OR ALTER VIEW risk_app.CustomerProfile AS
SELECT CustomerID,
 CAST(TransactionCount30D AS INT) AS TransactionCount30D,
 CAST(TotalTransactionAmount30D AS DECIMAL(18,2)) AS TotalTransactionAmount30D,
 CAST(AverageTransactionRiskScore AS DECIMAL(8,2)) AS AverageTransactionRiskScore,
 CAST(HighRiskTransactionCount AS INT) AS HighRiskTransactionCount,
 CAST(FailedLoginCount AS INT) AS FailedLoginCount,
 CAST(DistinctDeviceCount AS INT) AS DistinctDeviceCount,
 CAST(UntrustedDeviceCount AS INT) AS UntrustedDeviceCount,
 CAST(GeographicAnomalyCount AS INT) AS GeographicAnomalyCount,
 CAST(FraudAlertCount AS INT) AS FraudAlertCount,
 CAST(CustomerRiskScore AS DECIMAL(8,2)) AS CustomerRiskScore,
 CustomerRiskBand,
 CONVERT(VARCHAR(33), gold_loaded_at, 126) + 'Z' AS gold_loaded_at,
 pipeline_run_id
FROM dbo.AggCustomerRiskProfile;
GO
CREATE OR ALTER VIEW risk_app.CustomerTransaction AS
SELECT p.CustomerID,t.TransactionID,
 CONVERT(VARCHAR(33),t.TransactionTimestamp,126)+'Z' AS TransactionTimestamp,
 CAST(t.Amount AS DECIMAL(18,2)) AS Amount,t.Currency,t.Channel,
 CAST(t.RiskScore AS DECIMAL(8,2)) AS RiskScore,t.TransactionStatus
FROM dbo.AggCustomerRiskProfile p
JOIN dbo.FactTransactions t ON t.CustomerSK=p.CustomerSK;
GO
CREATE OR ALTER VIEW risk_app.CustomerSession AS
SELECT p.CustomerID,s.SessionID,
 CONVERT(VARCHAR(33),s.LoginTimestamp,126)+'Z' AS LoginTimestamp,
 s.AuthenticationMethod,s.MfaUsed,CAST(s.FailedAttempts AS INT) AS FailedAttempts,s.Country
FROM dbo.AggCustomerRiskProfile p
JOIN dbo.FactDigitalSessions s ON s.CustomerSK=p.CustomerSK;
GO
CREATE OR ALTER VIEW risk_app.CustomerAlert AS
SELECT p.CustomerID,a.AlertID,
 CONVERT(VARCHAR(33),a.CreatedTimestamp,126)+'Z' AS CreatedTimestamp,
 a.Severity,a.Status,a.alertType,a.TransactionID
FROM dbo.AggCustomerRiskProfile p
JOIN dbo.FactFraudAlerts a ON a.CustomerSK=p.CustomerSK;
GO
CREATE OR ALTER VIEW risk_app.QualityCheck AS
SELECT r.source,r.object,r.status,CAST(r.quarantine_count AS INT) AS quarantine_count,
 r.pipeline_run_id,CAST(r.run_date AS VARCHAR(33)) AS run_date
FROM gold_lh.dbo.reconciliation_results r
WHERE r.pipeline_run_id=(SELECT TOP 1 pipeline_run_id
 FROM gold_lh.dbo.control_pipeline_run_log
 WHERE stage='reconciliation' ORDER BY ended_at DESC,pipeline_run_id DESC);
GO
-- Grant SELECT on these views only to approved reader principals using your
-- normal identity administration process. Do not grant workspace Contributor
-- just to read. High-risk access uses the EXISTING investigator allowlist;
-- this script never edits it.
