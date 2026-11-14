param([int]$Port = 5173)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js 24 LTS and npm, then retry.' }
if (-not (Test-Path 'node_modules')) {
    & npm.cmd ci --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
$env:VITE_DATA_MODE = 'demo'
Write-Host 'Synthetic demo only. Investigation events persist in IndexedDB in this browser.'
& npm.cmd run dev -- --port $Port
