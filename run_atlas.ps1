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

function Get-ExtraArgs([string[]] $parts) {
    # PowerShell's range operator counts down when start > end (e.g. `1..0`
    # yields @(1,0), not an empty array), which corrupts single-word
    # commands like "python3" if sliced with $parts[1..($parts.Length-1)].
    if ($parts.Length -gt 1) { return $parts[1..($parts.Length - 1)] }
    return @()
}

function Resolve-BasePython {
    # Candidates are tried in order and must actually execute and report
    # Python >= 3.10; a candidate merely being present on PATH is not enough
    # (e.g. the Windows "py" launcher can be a non-functional stub that
    # resolves via Get-Command but never runs, silently producing no venv).
    $candidates = @("py -3", "python3", "python")
    foreach ($c in $candidates) {
        $parts = $c -split " "
        $cmd = $parts[0]
        $exists = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $exists) { continue }
        try {
            $versionOutput = & $parts[0] @(Get-ExtraArgs $parts) -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        } catch {
            $versionOutput = $null
        }
        if ($LASTEXITCODE -eq 0 -and $versionOutput) {
            $verParts = $versionOutput.Trim() -split "\."
            if ([int]$verParts[0] -eq 3 -and [int]$verParts[1] -ge 10) {
                return $c
            }
        }
    }
    throw "No working Python >= 3.10 interpreter found on PATH (candidates tried: $($candidates -join ', ')). Install Python 3.10+ before running AOED."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "AOED: creating virtual environment at $VenvDir ..."
    $base = Resolve-BasePython
    $baseParts = $base -split " "
    & $baseParts[0] @(Get-ExtraArgs $baseParts) -m venv $VenvDir
    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment creation failed: $VenvPython was not created. Base interpreter used: $base"
    }
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
