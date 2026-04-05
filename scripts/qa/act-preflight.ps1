$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bash = Get-Command bash -ErrorAction Stop
& $bash.Path (Join-Path $scriptDir "act-preflight.sh") @args
exit $LASTEXITCODE
