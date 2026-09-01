-- Run in gold_wh after refresh and security application.
SELECT name, is_enabled
FROM sys.security_policies
WHERE name = 'CustomerRiskPolicy';
GO

SELECT OBJECT_SCHEMA_NAME(object_id) AS schema_name,
       OBJECT_NAME(object_id) AS table_name,
       name AS column_name,
       masking_function
FROM sys.masked_columns
WHERE is_masked = 1
ORDER BY table_name, column_name;
GO

SELECT USER_NAME() AS effective_user,
       COUNT_BIG(*) AS visible_profiles,
       SUM(CASE WHEN CustomerRiskBand = 'High' THEN 1 ELSE 0 END) AS visible_high_risk_profiles
FROM dbo.AggCustomerRiskProfile;
GO

