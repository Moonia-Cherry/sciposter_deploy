[CmdletBinding()]
param(
    [switch]$Reconcile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bootstrap\common.ps1')

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'This deployment package supports Windows only.' }
if ([Environment]::Is64BitOperatingSystem -ne $true) { throw 'A 64-bit Windows operating system is required.' }

if (-not (Test-Path -LiteralPath $script:LocalConfig -PathType Leaf)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'config\deploy.example.json') -Destination $script:LocalConfig
    Protect-LocalConfig
    throw "Created $script:LocalConfig. Fill all REPLACE_ME values, then rerun deploy.ps1."
}

$config = Read-DeployConfig
Set-SciPosterEnvironment -Config $config
Assert-PortableArtifacts
Protect-LocalConfig

& $script:PythonExe $script:BootstrapPy validate --root $script:SciPosterRoot --config $script:LocalConfig --agents $script:AgentsConfig --state $script:StateFile
if ($LASTEXITCODE -ne 0) { throw 'Package/configuration validation failed.' }

$baseUrl = Get-BaseUrl -Config $config
$alreadyHealthy = Test-FastClawEndpoint -BaseUrl $baseUrl -Endpoint '/healthz'
$listener = Get-PortListenerInfo -Port $config.fastclaw.port
if ($alreadyHealthy -and -not (Test-SciPosterListener -Listener $listener)) {
    $owner = if ($listener) { "PID $($listener.ProcessId), $($listener.ProcessPath)" } else { 'unknown listener' }
    throw "Port $($config.fastclaw.port) serves a healthy but foreign FastClaw ($owner). No process was changed."
}
if (-not $alreadyHealthy) {
    if ($listener) {
        throw "Port $($config.fastclaw.port) is already owned by PID $($listener.ProcessId) ($($listener.ProcessPath)). No process was stopped."
    }

    $adminArgs = @(
        'admin', 'create-user',
        '--username', [string]$config.administrator.username,
        '--email', [string]$config.administrator.email,
        '--password', [string]$config.administrator.password,
        '--display-name', 'SciPoster Administrator',
        '--role', 'super_admin'
    )
    $adminExit = Invoke-FastClawCommand -Arguments $adminArgs -Quiet
    if ($adminExit -ne 0) {
        Write-Host '[sciposter] Administrator creation did not succeed; login will determine whether the account already exists.'
    }
    else {
        Write-Host '[sciposter] Created the super_admin account.'
    }

    $startExit = Invoke-FastClawCommand -Arguments @('daemon', 'start', '--port', [string]$config.fastclaw.port)
    if ($startExit -ne 0) { throw 'FastClaw daemon start failed.' }
}
else {
    Write-Host '[sciposter] Reusing the healthy FastClaw instance for this deployment directory.'
}

Wait-FastClawReady -BaseUrl $baseUrl -TimeoutSeconds 90

& $script:PythonExe $script:BootstrapPy reconcile --root $script:SciPosterRoot --config $script:LocalConfig --agents $script:AgentsConfig --state $script:StateFile
if ($LASTEXITCODE -ne 0) { throw 'FastClaw reconciliation failed.' }
Protect-LocalConfig

& (Join-Path $PSScriptRoot 'verify.ps1') -Smoke
if ($LASTEXITCODE -ne 0) { throw 'Deployment verification failed.' }

Write-Host "[sciposter] FastClaw is ready at $baseUrl"
Write-Host "[sciposter] Agent mapping: $script:StateFile"
if ($Reconcile) {
    Write-Host '[sciposter] Reconciliation completed.'
}
