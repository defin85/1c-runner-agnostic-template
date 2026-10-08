$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir "..\python\run-python.ps1") "analyze-bsl-external" @args
exit $LASTEXITCODE
