[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Command,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDir "..\.."))

function Resolve-PythonCommand {
    if ($env:ONEC_PYTHON) {
        return @($env:ONEC_PYTHON)
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @($python.Source)
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @($py.Source, "-3")
    }
    throw "Python 3.12+ was not found. Set ONEC_PYTHON or install python/py."
}

$pythonCommand = @(Resolve-PythonCommand)
$moduleArgs = @("-m", "scripts.python.cli", $Command) + $RemainingArgs
Push-Location $projectRoot
try {
    if ($pythonCommand.Length -eq 1) {
        & $pythonCommand[0] @moduleArgs
    } else {
        & $pythonCommand[0] $pythonCommand[1..($pythonCommand.Length - 1)] @moduleArgs
    }
} finally {
    Pop-Location
}
exit $LASTEXITCODE
