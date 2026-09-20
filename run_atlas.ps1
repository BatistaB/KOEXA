<#
.SYNOPSIS
    AOED / Aspergillus oryzae Transcriptome Atlas - local launcher.

.DESCRIPTION
    Thin wrapper so the user never has to remember Python venv activation or
    Nextflow invocation details (PROJECT_MASTER_SPEC.md section 25). It:
      1. Locates the repo root (this script's directory).
      2. Creates a local virtual environment (.venv) on first run.
      3. Installs/updates the aoryzae_atlas package in editable mode when needed.
      4. Forwards all arguments to the `atlas` CLI.

    Long-running pipeline commands are expected to support graceful
    interruption (Ctrl+C) and `atlas resume`; this launcher does not swallow
    Ctrl+C.

.EXAMPLE
    .\run_atlas.ps1 doctor
    .\run_atlas.ps1 status
    .\run_atlas.ps1 init
#>

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $AtlasArgs
)

$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$VenvDir  = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$MarkerFile = Join-Path $VenvDir ".install-marker"

function Resolve-BasePython {
    $candidates = @("py -3", "python3", "python")
    foreach ($c in $candidates) {
        $parts = $c -split " "
        $cmd = $parts[0]
        $exists = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($exists) { return $c }
    }
    throw "No Python 3 interpreter found on PATH. Install Python 3.10+ before running AOED."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "AOED: creating virtual environment at $VenvDir ..."
    $base = Resolve-BasePython
    $baseParts = $base -split " "
    & $baseParts[0] $baseParts[1..($baseParts.Length - 1)] -m venv $VenvDir
}

$PyprojectHash = (Get-FileHash (Join-Path $RepoRoot "pyproject.toml") -Algorithm SHA256).Hash
$NeedsInstall = $true
if (Test-Path $MarkerFile) {
    $lastHash = Get-Content $MarkerFile -Raw
    if ($lastHash.Trim() -eq $PyprojectHash) {
        $NeedsInstall = $false
    }
}

if ($NeedsInstall) {
    Write-Host "AOED: installing/updating aoryzae_atlas (editable) ..."
    & $VenvPython -m pip install --quiet --upgrade pip
    & $VenvPython -m pip install --quiet -e "$RepoRoot"
    Set-Content -Path $MarkerFile -Value $PyprojectHash
}

if (-not $AtlasArgs -or $AtlasArgs.Count -eq 0) {
    $AtlasArgs = @("status")
}

& $VenvPython -m aoryzae_atlas.cli.main @AtlasArgs
exit $LASTEXITCODE
