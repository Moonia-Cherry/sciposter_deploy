[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bootstrap\common.ps1')

$config = Read-DeployConfig
Set-SciPosterEnvironment -Config $config
Assert-PortableArtifacts
$baseUrl = Get-BaseUrl -Config $config
$statusExit = Invoke-FastClawCommand -Arguments @('daemon', 'status')
if ($statusExit -ne 0) { Write-Host "Daemon status command exited $statusExit" }
$listener = Get-PortListenerInfo -Port $config.fastclaw.port
$healthy = Test-FastClawEndpoint -BaseUrl $baseUrl -Endpoint '/healthz'
$ready = Test-FastClawEndpoint -BaseUrl $baseUrl -Endpoint '/readyz'
$owned = Test-SciPosterListener -Listener $listener
Write-Host "Health: $healthy"
Write-Host "Ready:  $ready"
Write-Host "Owned:  $owned"
if ($listener) { Write-Host "PID:    $($listener.ProcessId) ($($listener.ProcessPath))" }
Write-Host "URL:    $baseUrl"
if (-not ($healthy -and $ready -and $owned)) { exit 1 }
