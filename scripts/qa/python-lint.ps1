$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir "..\python\run-python.ps1") "python-lint" @args
exit $LASTEXITCODE
