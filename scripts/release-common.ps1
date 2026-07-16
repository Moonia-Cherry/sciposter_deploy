Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-ReleasePath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root
    )
    if ([IO.Path]::IsPathRooted($Path)) { return [IO.Path]::GetFullPath($Path) }
    return [IO.Path]::GetFullPath((Join-Path $Root $Path))
}

function Assert-SemVer {
    param([Parameter(Mandatory = $true)][string]$Version)
    if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$') {
        throw "Version must be a semantic version without a leading v: $Version"
    }
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Invoke-CheckedNative {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter()][string[]]$Arguments = @()
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $FilePath $($Arguments -join ' ')"
    }
}

function Assert-TextEqual {
    param(
        [Parameter(Mandatory = $true)][string]$ExpectedPath,
        [Parameter(Mandatory = $true)][string]$ActualPath,
        [Parameter(Mandatory = $true)][string]$Description
    )
    if (-not (Test-Path -LiteralPath $ExpectedPath -PathType Leaf)) { throw "Missing tracked dependency lock: $ExpectedPath" }
    if (-not (Test-Path -LiteralPath $ActualPath -PathType Leaf)) { throw "Missing runtime dependency lock: $ActualPath" }
    $expected = ((Get-Content -LiteralPath $ExpectedPath -Encoding UTF8) -join "`n").Trim()
    $actual = ((Get-Content -LiteralPath $ActualPath -Encoding UTF8) -join "`n").Trim()
    if ($expected -cne $actual) {
        throw "$Description differs from the tracked dependency lock."
    }
}

function Assert-JsonEqual {
    param(
        [Parameter(Mandatory = $true)][string]$ExpectedPath,
        [Parameter(Mandatory = $true)][string]$ActualPath,
        [Parameter(Mandatory = $true)][string]$NodeExe,
        [Parameter(Mandatory = $true)][string]$Description
    )
    foreach ($path in @($ExpectedPath, $ActualPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing dependency lock: $path" }
    }
    $comparison = @'
const fs = require('fs');
const expected = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
const actual = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
process.exit(JSON.stringify(expected) === JSON.stringify(actual) ? 0 : 1);
'@
    & $NodeExe -e $comparison $ExpectedPath $ActualPath
    if ($LASTEXITCODE -ne 0) { throw "$Description differs from the tracked dependency lock." }
}

function Assert-PortableComponents {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)]$Components
    )
    $fastClaw = Join-Path $Root 'bin\fastclaw\fastclaw.exe'
    $python = Join-Path $Root 'runtime\python\python.exe'
    $nodeRoot = Join-Path $Root 'runtime\node'
    $node = Join-Path $nodeRoot 'node.exe'
    foreach ($path in @($fastClaw, $python, $node)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required portable component is missing: $path" }
    }

    $fastClawOutput = (& $fastClaw version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Unable to query FastClaw version.' }
    $expectedFastClaw = "FastClaw v$($Components.fastclaw)"
    if (-not $fastClawOutput.StartsWith($expectedFastClaw, [StringComparison]::Ordinal)) {
        throw "FastClaw version mismatch. Expected '$expectedFastClaw', got '$($fastClawOutput.Split([Environment]::NewLine)[0])'."
    }
    if ($Components.fastclawBuild -and $fastClawOutput -notmatch [regex]::Escape([string]$Components.fastclawBuild)) {
        throw "FastClaw build mismatch. Expected output to contain '$($Components.fastclawBuild)'."
    }

    $pythonVersion = (& $python --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne "Python $($Components.python)") {
        throw "Python version mismatch. Expected 'Python $($Components.python)', got '$pythonVersion'."
    }
    $nodeVersion = (& $node --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $nodeVersion -ne "v$($Components.node)") {
        throw "Node version mismatch. Expected 'v$($Components.node)', got '$nodeVersion'."
    }

    foreach ($package in @('pptxgenjs', 'sharp')) {
        $packageJson = Join-Path $nodeRoot "node_modules\$package\package.json"
        if (-not (Test-Path -LiteralPath $packageJson -PathType Leaf)) { throw "Node package is missing: $package" }
        $actualVersion = (& $node -p 'require(process.argv[1]).version' $packageJson 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $actualVersion -ne [string]$Components.$package) {
            throw "$package version mismatch. Expected '$($Components.$package)', got '$actualVersion'."
        }
    }
}

function Assert-DependencyLocks {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot
    )
    Assert-TextEqual `
        (Join-Path $RepositoryRoot 'release\deps\python-requirements.lock.txt') `
        (Join-Path $Root 'runtime\python\requirements.lock.txt') `
        'Python requirements.lock.txt'
    $node = Join-Path $Root 'runtime\node\node.exe'
    Assert-JsonEqual `
        (Join-Path $RepositoryRoot 'release\deps\node\package.json') `
        (Join-Path $Root 'runtime\node\package.json') `
        $node `
        'Node package.json'
    Assert-JsonEqual `
        (Join-Path $RepositoryRoot 'release\deps\node\npm-shrinkwrap.json') `
        (Join-Path $Root 'runtime\node\npm-shrinkwrap.json') `
        $node `
        'Node npm-shrinkwrap.json'
}

function Copy-ReleaseTree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    & robocopy.exe $Source $Destination /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP /XD __pycache__ /XF *.pyc *.pyo | Out-Null
    $exitCode = $LASTEXITCODE
    if ($exitCode -gt 7) { throw "robocopy failed with exit code $exitCode while copying $Source" }
}

function Write-Sha256Sidecar {
    param(
        [Parameter(Mandatory = $true)][string]$Archive,
        [Parameter(Mandatory = $true)][string]$Sidecar
    )
    $line = "$(Get-Sha256 $Archive)  $([IO.Path]::GetFileName($Archive))`n"
    [IO.File]::WriteAllText($Sidecar, $line, [Text.UTF8Encoding]::new($false))
}

function Assert-BaseLayout {
    param([Parameter(Mandatory = $true)][string]$Root)
    $entries = @(Get-ChildItem -LiteralPath $Root -Force)
    $names = @($entries | ForEach-Object Name | Sort-Object)
    if (($names -join '|') -ne 'bin|runtime' -or @($entries | Where-Object { -not $_.PSIsContainer }).Count -ne 0) {
        throw "Portable base must contain only top-level bin and runtime directories; found: $($names -join ', ')"
    }
    $runtimeNames = @(Get-ChildItem -LiteralPath (Join-Path $Root 'runtime') -Force | ForEach-Object Name | Sort-Object)
    if (($runtimeNames -join '|') -ne 'node|python') {
        throw "Portable base runtime must contain exactly node and python; found: $($runtimeNames -join ', ')"
    }
}
