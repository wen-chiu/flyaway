# build.ps1 — Windows PyInstaller build script for flyaway
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File .\packaging\build.ps1

[CmdletBinding()]
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== Flyaway PyInstaller build ===" -ForegroundColor Cyan
Write-Host "Repo root: $RepoRoot"

# 1. Clean previous build artifacts.
if ($Clean -or (Test-Path "build") -or (Test-Path "dist")) {
    Write-Host "Cleaning build/ and dist/ ..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "build", "dist"
}

# 2. Sanity checks.
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python not found in PATH."
}
if (-not (python -m pip show pyinstaller 2>$null)) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    python -m pip install "pyinstaller==6.7.0"
}

# 3. Run PyInstaller against the spec file.
Write-Host "Running PyInstaller..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm "packaging/build.spec"

# 4. Post-processing: copy README + LICENSE alongside the exe.
$distDir = Join-Path $RepoRoot "dist\flyaway"
if (Test-Path $distDir) {
    foreach ($f in @("README.md", "LICENSE")) {
        if (Test-Path $f) { Copy-Item $f -Destination $distDir -Force }
    }
    Write-Host "Build complete: $distDir" -ForegroundColor Green
} else {
    throw "PyInstaller finished but $distDir not found."
}
