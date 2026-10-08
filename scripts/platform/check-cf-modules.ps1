$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir "..\python\run-python.ps1") "check-cf-modules" @args
exit $LASTEXITCODE
