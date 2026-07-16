Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:SciPosterRoot = Split-Path -Parent $PSScriptRoot
$script:FastClawExe = Join-Path $script:SciPosterRoot 'bin\fastclaw\fastclaw.exe'
$script:PythonExe = Join-Path $script:SciPosterRoot 'runtime\python\python.exe'
$script:NodeRoot = Join-Path $script:SciPosterRoot 'runtime\node'
$script:LocalConfig = Join-Path $script:SciPosterRoot 'config\deploy.local.json'
$script:AgentsConfig = Join-Path $script:SciPosterRoot 'config\agents.json'
$script:StateFile = Join-Path $script:SciPosterRoot 'state\deploy-state.json'
$script:BootstrapPy = Join-Path $script:SciPosterRoot 'bootstrap\bootstrap.py'
$script:ShellRoot = $null

function Resolve-PosixShellRoot {
    $bundledCandidates = @(
        (Join-Path $script:SciPosterRoot 'runtime\shell\bin'),
        (Join-Path $script:SciPosterRoot 'runtime\shell\usr\bin')
    )
    foreach ($candidate in $bundledCandidates) {
        if (Test-Path -LiteralPath (Join-Path $candidate 'sh.exe') -PathType Leaf) {
            return $candidate
        }
    }

    $existing = Get-Command sh.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing -and $existing.Source) {
        return Split-Path -Parent $existing.Source
    }

    $git = Get-Command git.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($git -and $git.Source) {
        $gitRoot = Split-Path -Parent (Split-Path -Parent $git.Source)
        foreach ($relative in @('bin', 'usr\bin')) {
            $candidate = Join-Path $gitRoot $relative
            if (Test-Path -LiteralPath (Join-Path $candidate 'sh.exe') -PathType Leaf) {
                return $candidate
            }
        }
    }

    foreach ($candidate in @(
        (Join-Path $env:ProgramFiles 'Git\bin'),
        (Join-Path $env:ProgramFiles 'Git\usr\bin'),
        (Join-Path ${env:ProgramFiles(x86)} 'Git\bin'),
        (Join-Path ${env:ProgramFiles(x86)} 'Git\usr\bin')
    )) {
        if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate 'sh.exe') -PathType Leaf)) {
            return $candidate
        }
    }
    return $null
}

function Read-DeployConfig {
    if (-not (Test-Path -LiteralPath $script:LocalConfig -PathType Leaf)) {
        throw "Missing $script:LocalConfig. Copy config\deploy.example.json and fill all REPLACE_ME values."
    }
    return Get-Content -LiteralPath $script:LocalConfig -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Set-SciPosterEnvironment {
    param([Parameter(Mandatory = $true)]$Config)

    $env:FASTCLAW_HOME = Join-Path $script:SciPosterRoot 'data\fastclaw'
    $env:FASTCLAW_BIND = 'loopback'
    $env:FASTCLAW_PORT = [string]$Config.fastclaw.port
    $env:FASTCLAW_STORAGE_TYPE = 'sqlite'
    $env:FASTCLAW_STORAGE_AUTO_MIGRATE = 'true'
    $env:FASTCLAW_SANDBOX_ENABLED = 'false'
    # FastClaw v0.35.x stores daemon PID/log files under os.UserHomeDir()
    # rather than FASTCLAW_HOME. Override the child-process home as well so
    # this portable instance cannot collide with another FastClaw install.
    $processHome = Join-Path $script:SciPosterRoot 'data\process-home'
    New-Item -ItemType Directory -Path $processHome -Force | Out-Null
    $env:HOME = $processHome
    $env:USERPROFILE = $processHome
    $env:NODE_PATH = Join-Path $script:NodeRoot 'node_modules'
    $env:SCIPOSTER_NODE_MODULES = $env:NODE_PATH

    $script:ShellRoot = Resolve-PosixShellRoot

    $paths = @(
        $script:ShellRoot,
        $script:NodeRoot,
        (Join-Path $script:NodeRoot 'node_modules\.bin'),
        (Split-Path -Parent $script:PythonExe),
        (Join-Path (Split-Path -Parent $script:PythonExe) 'Scripts')
    )
    $inheritedPath = [Environment]::GetEnvironmentVariable('Path', 'Process')
    if (-not $inheritedPath) { $inheritedPath = [Environment]::GetEnvironmentVariable('PATH', 'Process') }
    $combinedPath = ((@($paths | Where-Object { $_ }) + @($inheritedPath)) -join [IO.Path]::PathSeparator)

    # Some launchers provide both PATH and Path entries. Go forwards both to
    # sh.exe, and MSYS may select the stale one, silently dropping the bundled
    # Python/Node paths. Collapse them to one canonical process-level entry.
    [Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
    [Environment]::SetEnvironmentVariable('Path', $null, 'Process')
    [Environment]::SetEnvironmentVariable('Path', $combinedPath, 'Process')
}

function Assert-PortableArtifacts {
    foreach ($path in @($script:FastClawExe, $script:PythonExe, (Join-Path $script:NodeRoot 'node.exe'))) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Portable deployment artifact is missing: $path"
        }
    }
    if (-not $script:ShellRoot -or -not (Test-Path -LiteralPath (Join-Path $script:ShellRoot 'sh.exe') -PathType Leaf)) {
        throw 'FastClaw host tools require sh.exe. Bundle runtime\shell or install Git for Windows, then rerun.'
    }
}

function Get-BaseUrl {
    param([Parameter(Mandatory = $true)]$Config)
    return "http://$($Config.fastclaw.host):$($Config.fastclaw.port)"
}

function Test-FastClawEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [string]$Endpoint = '/healthz',
        [int]$TimeoutSeconds = 2
    )
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri ($BaseUrl + $Endpoint) -TimeoutSec $TimeoutSeconds
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Get-PortListenerInfo {
    param([Parameter(Mandatory = $true)][int]$Port)
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) { return $null }
    $pids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($pids.Count -ne 1) {
        throw "Port $Port has multiple listening owners: $($pids -join ', ')"
    }
    $process = Get-Process -Id $pids[0] -ErrorAction SilentlyContinue
    $processPath = $null
    if ($process) {
        try { $processPath = [IO.Path]::GetFullPath($process.Path) } catch { $processPath = $null }
    }
    return [pscustomobject]@{
        Port = $Port
        ProcessId = $pids[0]
        ProcessPath = $processPath
    }
}

function Test-SciPosterListener {
    param($Listener)
    if (-not $Listener -or -not $Listener.ProcessPath) { return $false }
    $expected = [IO.Path]::GetFullPath($script:FastClawExe)
    return [string]::Equals($Listener.ProcessPath, $expected, [StringComparison]::OrdinalIgnoreCase)
}

function Stop-SciPosterProcesses {
    param([Parameter(Mandatory = $true)][int]$Port)
    $listener = Get-PortListenerInfo -Port $Port
    if (-not $listener) {
        Write-Host "[sciposter] No listener exists on port $Port."
        return
    }
    if (-not (Test-SciPosterListener -Listener $listener)) {
        throw "Refusing to stop foreign listener PID $($listener.ProcessId) ($($listener.ProcessPath))."
    }

    $expected = [IO.Path]::GetFullPath($script:FastClawExe)
    $ids = [System.Collections.Generic.List[int]]::new()
    $ids.Add([int]$listener.ProcessId)
    try {
        $gateway = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.ProcessId)"
        if ($gateway -and $gateway.ParentProcessId) {
            $parent = Get-Process -Id $gateway.ParentProcessId -ErrorAction SilentlyContinue
            $parentPath = $null
            if ($parent) { try { $parentPath = [IO.Path]::GetFullPath($parent.Path) } catch { $parentPath = $null } }
            if ($parentPath -and [string]::Equals($parentPath, $expected, [StringComparison]::OrdinalIgnoreCase)) {
                $ids.Insert(0, [int]$gateway.ParentProcessId)
            }
        }
    }
    catch {
        Write-Host '[sciposter] Could not inspect the daemon parent; stopping the verified listener only.'
    }

    foreach ($id in $ids | Select-Object -Unique) {
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
    $deadline = (Get-Date).AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 200
        $remaining = Get-PortListenerInfo -Port $Port
    } while ($remaining -and (Get-Date) -lt $deadline)
    if ($remaining) { throw "SciPoster FastClaw did not release port $Port." }

    $pidFile = Join-Path $env:USERPROFILE '.fastclaw\fastclaw.pid'
    if (Test-Path -LiteralPath $pidFile) { Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue }
}

function Wait-FastClawReady {
    param(
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [int]$TimeoutSeconds = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if ((Test-FastClawEndpoint -BaseUrl $BaseUrl -Endpoint '/healthz') -and
            (Test-FastClawEndpoint -BaseUrl $BaseUrl -Endpoint '/readyz')) {
            return
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "FastClaw did not become healthy and ready within $TimeoutSeconds seconds."
}

function Protect-LocalConfig {
    if (-not (Test-Path -LiteralPath $script:LocalConfig -PathType Leaf)) { return }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    # Modify includes the delete/rename right required for atomic os.replace
    # when bootstrap rotates the middleware token.
    & icacls.exe $script:LocalConfig '/inheritance:r' '/grant:r' "${identity}:(M)" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to restrict ACL on $script:LocalConfig"
    }
}

function Invoke-FastClawCommand {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$Quiet
    )
    # Windows PowerShell converts native stderr lines into ErrorRecord objects.
    # With ErrorActionPreference=Stop that aborts even when FastClaw later exits
    # successfully (its structured INFO logs are written to stderr).
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $script:FastClawExe @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
    if (-not $Quiet) {
        foreach ($line in $output) { Write-Host ([string]$line) }
    }
    return $exitCode
}
