[CmdletBinding()]
param(
    [switch]$ReuseExistingConnection,
    [switch]$AllowUpdateFromGit,
    [switch]$FromClipboard
)

$arguments = @{}
if ($ReuseExistingConnection) { $arguments.ReuseExistingConnection = $true }
if ($AllowUpdateFromGit) { $arguments.AllowUpdateFromGit = $true }
if ($FromClipboard) { $arguments.FromClipboard = $true }

& (Join-Path $PSScriptRoot 'connect_fabric_git.ps1') @arguments
exit $LASTEXITCODE
