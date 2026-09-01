[CmdletBinding()]
param(
    [switch]$ReuseExistingConnection,
    [switch]$AllowUpdateFromGit
)

$ErrorActionPreference = 'Stop'
$securePat = Read-Host 'Paste the GitHub personal access token' -AsSecureString
$env:GITHUB_PAT = [System.Net.NetworkCredential]::new('', $securePat).Password
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

try {
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Fabric Git setup exited with code $LASTEXITCODE"
    }
}
finally {
    Remove-Item Env:\GITHUB_PAT -ErrorAction SilentlyContinue
    $securePat.Dispose()
}
