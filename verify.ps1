[CmdletBinding()]
param(
    [switch]$Smoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bootstrap\common.ps1')

$config = Read-DeployConfig
Set-SciPosterEnvironment -Config $config
Assert-PortableArtifacts
$baseUrl = Get-BaseUrl -Config $config
Wait-FastClawReady -BaseUrl $baseUrl -TimeoutSeconds 15

$args = @(
    $script:BootstrapPy, 'verify',
    '--root', $script:SciPosterRoot,
    '--config', $script:LocalConfig,
    '--agents', $script:AgentsConfig,
    '--state', $script:StateFile
)
if ($Smoke) { $args += '--smoke' }
& $script:PythonExe @args
if ($LASTEXITCODE -ne 0) { throw 'FastClaw verification failed.' }
Write-Host '[sciposter] Verification passed.'

