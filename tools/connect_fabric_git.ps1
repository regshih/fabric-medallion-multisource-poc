[CmdletBinding()]
param(
    [switch]$ReuseExistingConnection,
    [switch]$AllowUpdateFromGit,
    [switch]$FromClipboard
)

$ErrorActionPreference = 'Stop'
$securePat = $null
if ($FromClipboard) {
    $clipboardPat = (Get-Clipboard -Raw).Trim()
    if (-not $clipboardPat) {
        throw 'The clipboard is empty. Copy the generated PAT value, then rerun.'
    }
    $env:GITHUB_PAT = $clipboardPat
    $clipboardPat = $null
    # Windows PowerShell 5 rejects an empty string; one blank character still
    # removes the credential from the clipboard without retaining its value.
    Set-Clipboard -Value ' '
}
else {
    $securePat = Read-Host 'Paste the GitHub personal access token' -AsSecureString
    $env:GITHUB_PAT = [System.Net.NetworkCredential]::new('', $securePat).Password
}
$env:FABRIC_WORKSPACE_NAME = 'fabric-medallion-multisource-poc'
$env:GITHUB_OWNER = 'regshih'
$env:GITHUB_REPOSITORY = 'fabric-medallion-multisource-poc'
$env:GITHUB_BRANCH = 'main'
$env:FABRIC_GIT_DIRECTORY = '/fabric_git'

$arguments = @('-m', 'infra.fabric.git_integration')
if ($ReuseExistingConnection) {
    $arguments += '--reuse-existing-connection'
}
if ($AllowUpdateFromGit) {
    $arguments += '--allow-update-from-git'
}

$pushedLocation = $false
try {
    Push-Location (Split-Path $PSScriptRoot -Parent)
    $pushedLocation = $true
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Fabric Git setup exited with code $LASTEXITCODE"
    }
}
finally {
    if ($pushedLocation) {
        Pop-Location
    }
    Remove-Item Env:\GITHUB_PAT -ErrorAction SilentlyContinue
    if ($null -ne $securePat) {
        $securePat.Dispose()
    }
}
