$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir "..\python\run-python.ps1") "migrate-runtime-profile-v2" @args
exit $LASTEXITCODE
