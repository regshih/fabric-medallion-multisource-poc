-- gold_wh refresh step 2 of 2: reapply supported Warehouse security metadata.
-- Run immediately after 00_refresh_gold_serving.sql on every refresh.
--
-- All identifiers in this POC are synthetic.  The masks demonstrate how
-- sensitive-like identifiers and device fingerprints would be protected.

IF SCHEMA_ID(N'Security') IS NULL
    EXEC(N'CREATE SCHEMA Security');
GO

ALTER TABLE dbo._base_DimCustomer
ALTER COLUMN CustomerID ADD MASKED WITH (FUNCTION = 'partial(5,"******",2)');
GO

ALTER TABLE dbo._base_DimDevice
ALTER COLUMN deviceFingerprint ADD MASKED WITH (FUNCTION = 'partial(3,"********",3)');
GO

IF OBJECT_ID(N'Security.RiskInvestigatorPrincipal', N'U') IS NULL
BEGIN
    CREATE TABLE Security.RiskInvestigatorPrincipal
    (
        PrincipalName VARCHAR(256) NOT NULL
    );
END;
GO

CREATE OR ALTER FUNCTION Security.fn_customer_risk_access
(
    @CustomerRiskBand VARCHAR(16)
)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN
(
    SELECT 1 AS access_granted
    WHERE @CustomerRiskBand <> 'High'
       OR EXISTS
          (
              SELECT 1
              FROM Security.RiskInvestigatorPrincipal AS p
              WHERE p.PrincipalName = USER_NAME()
          )
);
GO

CREATE SECURITY POLICY Security.CustomerRiskPolicy
ADD FILTER PREDICATE Security.fn_customer_risk_access(CustomerRiskBand)
ON dbo._base_AggCustomerRiskProfile
WITH (STATE = ON, SCHEMABINDING = ON);
GO

-- Validation caveat:
-- * RLS policies apply to dbo/workspace admins too; add the validating admin's
--   USER_NAME() to Security.RiskInvestigatorPrincipal to test the allow path.
-- * DDM is different: Fabric Admin/Member/Contributor and principals with
--   CONTROL/UNMASK see cleartext.  Validate masking with a Viewer or other
--   least-privileged principal; an admin result cannot prove enforcement.
