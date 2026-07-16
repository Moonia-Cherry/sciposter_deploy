[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [string]$OutputDirectory = 'dist'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'release-common.ps1')

Assert-SemVer -Version $Version
$outputRoot = Resolve-ReleasePath -Path $OutputDirectory -Root $repositoryRoot
$assetName = "sciposter-portable-base-windows-amd64-$Version.zip"
$archive = Join-Path $outputRoot $assetName
$sidecar = "$archive.sha256"
$generatedLock = Join-Path $outputRoot 'portable-base.lock.json'
foreach ($path in @($archive, $sidecar, $generatedLock)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite existing release output: $path" }
}

$components = [ordered]@{
    fastclaw = '0.35.1-sciposter.2'
    fastclawBuild = 'c6f93858-workspacefix2'
    python = '3.12.9'
    node = '22.13.0'
    pptxgenjs = '3.12.0'
    sharp = '0.33.5'
}

Assert-PortableComponents -Root $repositoryRoot -Components ([pscustomobject]$components)
Assert-DependencyLocks -Root $repositoryRoot -RepositoryRoot $repositoryRoot

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$stage = Join-Path ([IO.Path]::GetTempPath()) "sciposter-base-$PID-$([guid]::NewGuid().ToString('N'))"
try {
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    Copy-ReleaseTree `
        -Source (Join-Path $repositoryRoot 'bin\fastclaw') `
        -Destination (Join-Path $stage 'bin\fastclaw')
    Copy-ReleaseTree `
        -Source (Join-Path $repositoryRoot 'runtime\python') `
        -Destination (Join-Path $stage 'runtime\python')
    Copy-ReleaseTree `
        -Source (Join-Path $repositoryRoot 'runtime\node') `
        -Destination (Join-Path $stage 'runtime\node')

    Assert-BaseLayout -Root $stage
    Assert-PortableComponents -Root $stage -Components ([pscustomobject]$components)
    Assert-DependencyLocks -Root $stage -RepositoryRoot $repositoryRoot

    Invoke-CheckedNative -FilePath 'tar.exe' -Arguments @('-a', '-c', '-f', $archive, '-C', $stage, 'bin', 'runtime')
    Write-Sha256Sidecar -Archive $archive -Sidecar $sidecar

    $lock = [ordered]@{
        schemaVersion = 1
        baseVersion = $Version
        platform = 'windows-amd64'
        repository = 'Moonia-Cherry/sciposter_deploy'
        releaseTag = "base-v$Version"
        assetName = $assetName
        sha256 = Get-Sha256 $archive
        components = $components
    }
    $lockJson = $lock | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($generatedLock, "$lockJson`n", [Text.UTF8Encoding]::new($false))

    Write-Host "[sciposter] Portable base created: $archive"
    Write-Host "[sciposter] SHA-256 sidecar: $sidecar"
    Write-Host "[sciposter] Generated lock: $generatedLock"
    Write-Host "[sciposter] Upload the ZIP and SHA-256 file to GitHub Release base-v$Version, then copy the lock into release\portable-base.lock.json."
}
finally {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
