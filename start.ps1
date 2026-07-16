[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bootstrap\common.ps1')

$config = Read-DeployConfig
Set-SciPosterEnvironment -Config $config
Assert-PortableArtifacts
$baseUrl = Get-BaseUrl -Config $config
$listener = Get-PortListenerInfo -Port $config.fastclaw.port

if (Test-FastClawEndpoint -BaseUrl $baseUrl -Endpoint '/healthz') {
    if (-not (Test-SciPosterListener -Listener $listener)) {
        $owner = if ($listener) { "PID $($listener.ProcessId), $($listener.ProcessPath)" } else { 'unknown listener' }
        throw "A foreign healthy service owns port $($config.fastclaw.port) ($owner)."
    }
    Write-Host "[sciposter] FastClaw is already running at $baseUrl"
    exit 0
}
if ($listener) { throw "Port $($config.fastclaw.port) is occupied by PID $($listener.ProcessId) ($($listener.ProcessPath))." }

$startExit = Invoke-FastClawCommand -Arguments @('daemon', 'start', '--port', [string]$config.fastclaw.port)
if ($startExit -ne 0) { throw 'FastClaw daemon start failed.' }
Wait-FastClawReady -BaseUrl $baseUrl -TimeoutSeconds 90
Write-Host "[sciposter] FastClaw is ready at $baseUrl"
