[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"
if ($RemainingArgs.Length -eq 0) {
    Write-Error "usage: direct-platform.ps1 <command> [args...]"
    exit 1
}
if ($RemainingArgs.Length -eq 1) {
    & $RemainingArgs[0]
} else {
    & $RemainingArgs[0] $RemainingArgs[1..($RemainingArgs.Length - 1)]
}
exit $LASTEXITCODE
