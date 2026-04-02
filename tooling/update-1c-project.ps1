$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir "..\scripts\python\run-python.ps1") "update-project" @args
exit $LASTEXITCODE
