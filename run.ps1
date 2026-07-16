$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project environment is missing. Run .\setup.ps1 first."
}

Set-Location $ProjectRoot
& $Python (Join-Path $ProjectRoot "main.py") @args
