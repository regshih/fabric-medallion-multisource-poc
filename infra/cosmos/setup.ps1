<#
.SYNOPSIS
Deploys the Mirroring-ready Cosmos account and grants passwordless data access.

.DESCRIPTION
Uses the current Azure CLI context. The Bicep template is idempotent, enforces
continuous backup, disables local/key authentication, and creates all containers
with /customerId. Provide PrincipalId for a user, service principal, or managed
identity that will run the loaders. No secrets are read or emitted.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SubscriptionId,
    [Parameter(Mandatory)][string]$ResourceGroup,
    [Parameter(Mandatory)][string]$AccountName,
    [string]$Location = 'westus3',
    [string]$DatabaseName = 'banking_poc',
    [string]$PrincipalId
)

$ErrorActionPreference = 'Stop'
$template = Join-Path $PSScriptRoot 'main.bicep'

az account set --subscription $SubscriptionId
if ($LASTEXITCODE -ne 0) { throw 'Azure CLI authentication/subscription selection failed. Run az login and retry.' }

az group create --name $ResourceGroup --location $Location --only-show-errors | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Resource group creation failed.' }

$deployment = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file $template `
    --parameters accountName=$AccountName location=$Location databaseName=$DatabaseName `
    --name 'cosmos-multisource-poc' `
    --only-show-errors `
    --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Cosmos DB deployment failed.' }

if (-not $PrincipalId) {
    $PrincipalId = az ad signed-in-user show --query id --output tsv 2>$null
}
if (-not $PrincipalId) {
    throw 'Could not infer a signed-in user. Pass -PrincipalId for the loader identity.'
}

$accountId = $deployment.properties.outputs.accountId.value
$contributorDefinitionId = "$accountId/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
$existing = az cosmosdb sql role assignment list `
    --resource-group $ResourceGroup --account-name $AccountName `
    --query "[?principalId=='$PrincipalId' && roleDefinitionId=='$contributorDefinitionId'].id | [0]" `
    --output tsv
if (-not $existing) {
    az cosmosdb sql role assignment create `
        --resource-group $ResourceGroup --account-name $AccountName `
        --scope $accountId --principal-id $PrincipalId `
        --role-definition-id $contributorDefinitionId --only-show-errors | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cosmos DB data-plane RBAC assignment failed.' }
}

$endpoint = $deployment.properties.outputs.endpoint.value
[pscustomobject]@{
    AccountName = $AccountName
    DatabaseName = $DatabaseName
    Endpoint = $endpoint
    BackupMode = $deployment.properties.outputs.backupMode.value
    PrincipalId = $PrincipalId
} | ConvertTo-Json
