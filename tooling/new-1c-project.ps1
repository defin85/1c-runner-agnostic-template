$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir "..\scripts\python\run-python.ps1") "new-project" @args
exit $LASTEXITCODE
