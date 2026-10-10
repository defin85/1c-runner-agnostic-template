# KD 2.01 rules workbench executor; the logic lives in scripts/migration/kd_cycle_*.py.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir "..\python\run-python.ps1") "kd-rules-cycle" @args
exit $LASTEXITCODE
