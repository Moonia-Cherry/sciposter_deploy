[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [string]$BaseLockFile = 'release\portable-base.lock.json',

    [string]$BaseArchive,

    [string]$OutputDirectory = 'dist'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'release-common.ps1')

Assert-SemVer -Version $Version
$git = Get-Command git -ErrorAction Stop
& $git.Source -C $repositoryRoot rev-parse --verify HEAD 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Release assembly requires a Git repository with at least one commit.' }
& $git.Source -C $repositoryRoot diff --quiet HEAD --
if ($LASTEXITCODE -eq 1) { throw 'Commit tracked changes before building a release; payload files are read from Git HEAD.' }
if ($LASTEXITCODE -ne 0) { throw 'Unable to verify the Git working tree.' }

$lockPath = Resolve-ReleasePath -Path $BaseLockFile -Root $repositoryRoot
if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) { throw "Portable base lock is missing: $lockPath" }
$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($lock.schemaVersion -ne 1 -or $lock.platform -ne 'windows-amd64') { throw 'Unsupported portable base lock.' }

$outputRoot = Resolve-ReleasePath -Path $OutputDirectory -Root $repositoryRoot
$assetName = "sciposter-windows-amd64-$Version.zip"
$archive = Join-Path $outputRoot $assetName
$sidecar = "$archive.sha256"
foreach ($path in @($archive, $sidecar)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite existing release output: $path" }
}

$stage = Join-Path ([IO.Path]::GetTempPath()) "sciposter-release-$PID-$([guid]::NewGuid().ToString('N'))"
$downloadRoot = Join-Path ([IO.Path]::GetTempPath()) "sciposter-download-$PID-$([guid]::NewGuid().ToString('N'))"
try {
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    if ($BaseArchive) {
        $basePath = Resolve-ReleasePath -Path $BaseArchive -Root $repositoryRoot
    }
    else {
        $gh = Get-Command gh -ErrorAction SilentlyContinue
        if (-not $gh) { throw 'gh is required to download the portable base; install gh or pass -BaseArchive.' }
        New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null
        Invoke-CheckedNative -FilePath $gh.Source -Arguments @(
            'release', 'download', [string]$lock.releaseTag,
            '--repo', [string]$lock.repository,
            '--pattern', [string]$lock.assetName,
            '--dir', $downloadRoot
        )
        $basePath = Join-Path $downloadRoot ([string]$lock.assetName)
    }
    if (-not (Test-Path -LiteralPath $basePath -PathType Leaf)) { throw "Portable base archive is missing: $basePath" }
    $actualBaseHash = Get-Sha256 $basePath
    if ($actualBaseHash -ne ([string]$lock.sha256).ToUpperInvariant()) {
        throw "Portable base SHA-256 mismatch. Expected $($lock.sha256), got $actualBaseHash."
    }

    Invoke-CheckedNative -FilePath 'tar.exe' -Arguments @('-x', '-f', $basePath, '-C', $stage)
    Assert-BaseLayout -Root $stage
    Assert-PortableComponents -Root $stage -Components $lock.components
    Assert-DependencyLocks -Root $stage -RepositoryRoot $repositoryRoot

    $payloadSpecPath = Join-Path $repositoryRoot 'release\payload.json'
    $payload = Get-Content -LiteralPath $payloadSpecPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($payload.schemaVersion -ne 1 -or -not $payload.paths) { throw 'Invalid release payload specification.' }
    $payloadArchive = Join-Path $downloadRoot 'tracked-payload.zip'
    New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null
    $payloadPaths = @($payload.paths | ForEach-Object { [string]$_ })
    & $git.Source -C $repositoryRoot archive --format=zip "--output=$payloadArchive" HEAD -- @payloadPaths
    if ($LASTEXITCODE -ne 0) { throw 'git archive failed while collecting the tracked release payload.' }
    Invoke-CheckedNative -FilePath 'tar.exe' -Arguments @('-x', '-f', $payloadArchive, '-C', $stage)

    foreach ($forbidden in @(
        '.git', '.gitignore', 'build', 'data', 'dist', 'logs', 'release', 'scripts', 'state',
        'config\deploy.local.json'
    )) {
        if (Test-Path -LiteralPath (Join-Path $stage $forbidden)) {
            throw "Forbidden path entered the release payload: $forbidden"
        }
    }

    $manifestTool = Join-Path $stage 'bootstrap\package_manifest.py'
    $python = Join-Path $stage 'runtime\python\python.exe'
    Invoke-CheckedNative -FilePath $python -Arguments @(
        $manifestTool, 'generate', '--root', $stage,
        '--package-version', $Version, '--metadata', $lockPath,
        '--payload', $payloadSpecPath
    )
    Invoke-CheckedNative -FilePath $python -Arguments @($manifestTool, 'validate', '--root', $stage)

    New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
    Invoke-CheckedNative -FilePath 'tar.exe' -Arguments @('-a', '-c', '-f', $archive, '-C', $stage, '.')
    Write-Sha256Sidecar -Archive $archive -Sidecar $sidecar
    Write-Host "[sciposter] Release package created: $archive"
    Write-Host "[sciposter] SHA-256 sidecar: $sidecar"
}
finally {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    if (Test-Path -LiteralPath $downloadRoot) { Remove-Item -LiteralPath $downloadRoot -Recurse -Force }
}
