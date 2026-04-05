$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($args.Count -gt 0 -and $args[0] -eq "--readiness") {
    $remaining = @()
    if ($args.Count -gt 1) {
        $remaining = $args[1..($args.Count - 1)]
    }
    & (Join-Path $scriptDir "..\python\run-python.ps1") "imported-skill-readiness" @remaining
    exit $LASTEXITCODE
}

& (Join-Path $scriptDir "..\python\run-python.ps1") "imported-skill" @args
exit $LASTEXITCODE
