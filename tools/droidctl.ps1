# DroidOS launcher for Windows (deterministic admin interface).
# Finds a Python interpreter, sets PYTHONPATH + state dir, and runs `droidctl`.
#
#   .\tools\droidctl.ps1 status
#   .\tools\droidctl.ps1 status --json
#   .\tools\droidctl.ps1 safety status
#   .\tools\droidctl.ps1 body list
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)] $Args)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $root "src"
if (-not $env:DROIDOS_STATE) { $env:DROIDOS_STATE = Join-Path $root "run-state" }

function Find-Python {
    foreach ($name in @("python", "python3", "py")) {
        $c = Get-Command $name -ErrorAction SilentlyContinue
        if ($c -and $c.Source -notlike "*WindowsApps*") { return $c.Source }
    }
    $gimp = "C:\Program Files\GIMP 3\bin\python.exe"
    if (Test-Path $gimp) { return $gimp }
    throw "No Python 3.10+ found. Install from https://www.python.org/downloads/ and re-run."
}

$py = Find-Python
& $py -m droidos.cli.droidctl @Args
exit $LASTEXITCODE
