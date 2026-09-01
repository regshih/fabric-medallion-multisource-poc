-- Execute through a deployment tool that substitutes the SQLCMD variable.
-- Example value is a Microsoft Entra UPN, supplied at deploy time; do not
-- commit a real principal to this repository.
DECLARE @principal VARCHAR(256) = '$(RISK_INVESTIGATOR_PRINCIPAL)';

IF @principal = '' OR @principal LIKE '$(%'
    THROW 50000, 'Set RISK_INVESTIGATOR_PRINCIPAL at deployment time.', 1;

IF NOT EXISTS
(
    SELECT 1
    FROM Security.RiskInvestigatorPrincipal
    WHERE PrincipalName = @principal
)
BEGIN
    INSERT INTO Security.RiskInvestigatorPrincipal (PrincipalName)
    VALUES (@principal);
END;
GO

