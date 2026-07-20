[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root 'runtime\python\python.exe'
$fastclaw = Join-Path $root 'bin\fastclaw\fastclaw.exe'
$testRoot = Join-Path $root '_e2e'
$resolvedRoot = [IO.Path]::GetFullPath($root)
$resolvedTest = [IO.Path]::GetFullPath($testRoot)
if (-not $resolvedTest.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe test root.' }
if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null

$configPath = Join-Path $testRoot 'deploy.local.json'
$statePath = Join-Path $testRoot 'deploy-state.json'
$config = Get-Content -LiteralPath (Join-Path $root 'config\deploy.example.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$config.fastclaw.port = 19953
$config.administrator.username = 'e2e-admin'
$config.administrator.email = 'e2e@local'
$config.administrator.password = 'SciPoster-E2E-Only-9x!'
$config.provider.name = 'mock'
$config.provider.apiBase = 'http://127.0.0.1:19954/v1'
$config.provider.apiKey = 'mock-key'
$config.provider.model.id = 'mock-model'
$config.provider.model.name = 'Mock model'
$config.provider.model.input = @('text')
$config.verification.modelSmoke = $true
$config | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $configPath -Encoding UTF8

$env:FASTCLAW_HOME = Join-Path $testRoot 'fastclaw'
$processHome = Join-Path $testRoot 'process-home'
New-Item -ItemType Directory -Path $processHome -Force | Out-Null
$env:HOME = $processHome
$env:USERPROFILE = $processHome
$env:FASTCLAW_BIND = 'loopback'
$env:FASTCLAW_PORT = '19953'
$env:FASTCLAW_STORAGE_TYPE = 'sqlite'
$env:FASTCLAW_STORAGE_AUTO_MIGRATE = 'true'
$env:FASTCLAW_SANDBOX_ENABLED = 'false'
$env:NODE_PATH = Join-Path $root 'runtime\node\node_modules'
$env:PATH = ((Join-Path $root 'runtime\node'), (Join-Path $root 'runtime\python'), $env:PATH) -join [IO.Path]::PathSeparator

$provider = $null
$gateway = $null
try {
    $provider = Start-Process -FilePath $python -ArgumentList @((Join-Path $PSScriptRoot 'mock_provider.py'), '--port', '19954') -WindowStyle Hidden -PassThru
    & $fastclaw admin create-user --username $config.administrator.username --email $config.administrator.email --password $config.administrator.password --role super_admin | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'E2E administrator creation failed.' }
    $gateway = Start-Process -FilePath $fastclaw -ArgumentList @('gateway', '--port', '19953') -WindowStyle Hidden -PassThru

    $deadline = (Get-Date).AddSeconds(30)
    do {
        try { $ready = (Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:19953/readyz' -TimeoutSec 2).StatusCode -eq 200 }
        catch { $ready = $false }
        if (-not $ready) { Start-Sleep -Milliseconds 300 }
    } while (-not $ready -and (Get-Date) -lt $deadline)
    if (-not $ready) { throw 'E2E FastClaw gateway did not become ready.' }

    foreach ($round in 1..2) {
        & $python (Join-Path $root 'bootstrap\bootstrap.py') reconcile --root $root --config $configPath --agents (Join-Path $root 'config\agents.json') --state $statePath
        if ($LASTEXITCODE -ne 0) { throw "E2E reconcile round $round failed." }
    }
    & $python (Join-Path $root 'bootstrap\bootstrap.py') verify --root $root --config $configPath --agents (Join-Path $root 'config\agents.json') --state $statePath --smoke
    if ($LASTEXITCODE -ne 0) { throw 'E2E verification failed.' }
    $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (@($state.agents.PSObject.Properties).Count -ne 5) { throw 'E2E expected exactly five managed agents.' }
    $middlewareKeys = @($state.middlewareAgentKeys)
    if ($middlewareKeys.Count -ne 4 -or $middlewareKeys -contains 'poster-fastclaw-upload-agent') {
        throw 'E2E middleware scope must contain exactly four production agents and exclude the demo agent.'
    }
    Write-Host '[sciposter] E2E reconciliation, idempotency, prompt, skill, and ACL checks passed.'
}
finally {
    if ($gateway -and -not $gateway.HasExited) { Stop-Process -Id $gateway.Id -Force -ErrorAction SilentlyContinue }
    if ($provider -and -not $provider.HasExited) { Stop-Process -Id $provider.Id -Force -ErrorAction SilentlyContinue }
}
