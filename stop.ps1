[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bootstrap\common.ps1')

$config = Read-DeployConfig
Set-SciPosterEnvironment -Config $config
Assert-PortableArtifacts
Stop-SciPosterProcesses -Port $config.fastclaw.port
Write-Host '[sciposter] FastClaw stopped.'
