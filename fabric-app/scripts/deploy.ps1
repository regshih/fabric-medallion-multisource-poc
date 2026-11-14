param([switch]$Execute)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:RAYFIN_TELEMETRY_OPTOUT = '1'
if (-not $Execute) {
    Write-Host 'LOCAL PREVIEW ONLY. This script did not contact or change Fabric.'
    Write-Host 'After environment approval: set GOLD_WORKSPACE_ID, GOLD_WAREHOUSE_ID, VITE_FABRIC_WORKSPACE_ID and VITE_DATA_MODE=live.'
    Write-Host 'Review docs/DEPLOYMENT.md, authenticate with npx rayfin login, then rerun with -Execute.'
    exit 0
}
if ($env:VITE_DATA_MODE -ne 'live') { throw 'Set VITE_DATA_MODE=live. Demo deployment is deliberately blocked.' }
& node scripts/validate-config.mjs --live
if ($LASTEXITCODE -ne 0) { throw 'Deployment configuration failed validation.' }
& npm.cmd run check
if ($LASTEXITCODE -ne 0) { throw 'Local checks failed.' }
& npm.cmd run schema:check
if ($LASTEXITCODE -ne 0) { throw 'Rayfin schema checks failed.' }
# Explicit -Execute is the operator assertion that this environment is approved.
# The CLI creates a new app-owned SQL database. It never runs the serving-view SQL.
& npx.cmd rayfin up --workspace-id $env:VITE_FABRIC_WORKSPACE_ID
if ($LASTEXITCODE -ne 0) { throw 'Fabric deployment failed. Review CLI output; no successful deployment is claimed.' }
& npx.cmd rayfin up status --json
if ($LASTEXITCODE -ne 0) { throw 'Fabric deployment status could not be verified.' }
