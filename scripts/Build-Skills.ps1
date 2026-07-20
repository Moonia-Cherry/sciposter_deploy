[CmdletBinding()]
param(
    [switch]$CheckReproducible
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root 'runtime\python\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

$arguments = @(Join-Path $PSScriptRoot 'build_skills.py')
if ($CheckReproducible) {
    $arguments += '--check-reproducible'
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Skill archive build failed with exit code $LASTEXITCODE."
}
