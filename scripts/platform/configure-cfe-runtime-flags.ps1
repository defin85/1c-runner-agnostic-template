$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir "..\python\run-python.ps1") "configure-cfe-runtime-flags" @args
exit $LASTEXITCODE
