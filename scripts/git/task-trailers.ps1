[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($RemainingArgs.Length -eq 0) {
    Write-Error "Usage: ./scripts/git/task-trailers.ps1 <render|validate-message|select-commits> [options]"
    exit 1
}
$verb = $RemainingArgs[0]
$rest = @()
if ($RemainingArgs.Length -gt 1) {
    $rest = $RemainingArgs[1..($RemainingArgs.Length - 1)]
}
$command = switch ($verb) {
    "render" { "task-trailers-render" }
    "validate-message" { "task-trailers-validate" }
    "select-commits" { "task-trailers-select" }
    default { throw "unknown command: $verb" }
}
& (Join-Path $scriptDir "..\python\run-python.ps1") $command @rest
exit $LASTEXITCODE
