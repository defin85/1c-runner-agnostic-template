[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Target = "help",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Resolve-TargetScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    return Join-Path $root $RelativePath
}

$targets = @{
    "agent-verify" = @((Resolve-TargetScript "scripts\qa\agent-verify.ps1"))
    "act-preflight" = @((Resolve-TargetScript "scripts\qa\act-preflight.ps1"))
    "qa" = @((Resolve-TargetScript "scripts\qa\agent-verify.ps1"))
    "analyze-bsl" = @((Resolve-TargetScript "scripts\qa\analyze-bsl.ps1"))
    "format-bsl" = @((Resolve-TargetScript "scripts\qa\format-bsl.ps1"))
    "check-agent-docs" = @((Resolve-TargetScript "scripts\qa\check-agent-docs.ps1"))
    "check-skill-bindings" = @((Resolve-TargetScript "scripts\qa\check-skill-bindings.ps1"))
    "check-overlay-manifest" = @((Resolve-TargetScript "scripts\qa\check-overlay-manifest.ps1"))
    "codex-onboard" = @((Resolve-TargetScript "scripts\qa\codex-onboard.ps1"))
    "imported-skills-readiness" = @((Resolve-TargetScript "scripts\skills\run-imported-skill.ps1"), "--readiness")
    "create-ib" = @((Resolve-TargetScript "scripts\platform\create-ib.ps1"))
    "dump-src" = @((Resolve-TargetScript "scripts\platform\dump-src.ps1"))
    "load-src" = @((Resolve-TargetScript "scripts\platform\load-src.ps1"))
    "load-diff-src" = @((Resolve-TargetScript "scripts\platform\load-diff-src.ps1"))
    "load-task-src" = @((Resolve-TargetScript "scripts\platform\load-task-src.ps1"))
    "update-db" = @((Resolve-TargetScript "scripts\platform\update-db.ps1"))
    "diff-src" = @((Resolve-TargetScript "scripts\platform\diff-src.ps1"))
    "doctor" = @((Resolve-TargetScript "scripts\diag\doctor.ps1"))
    "test-xunit" = @((Resolve-TargetScript "scripts\test\run-xunit.ps1"))
    "tdd-xunit" = @((Resolve-TargetScript "scripts\test\tdd-xunit.ps1"))
    "test-bdd" = @((Resolve-TargetScript "scripts\test\run-bdd.ps1"))
    "smoke" = @((Resolve-TargetScript "scripts\test\run-smoke.ps1"))
    "export-context" = @((Resolve-TargetScript "scripts\llm\export-context.ps1"))
    "export-context-preview" = @((Resolve-TargetScript "scripts\llm\export-context.ps1"), "--preview")
    "export-context-check" = @((Resolve-TargetScript "scripts\llm\export-context.ps1"), "--check")
    "export-context-write" = @((Resolve-TargetScript "scripts\llm\export-context.ps1"), "--write")
    "verify-traceability" = @((Resolve-TargetScript "scripts\llm\verify-traceability.ps1"))
    "template-check-update" = @((Resolve-TargetScript "scripts\template\check-update.ps1"))
    "template-update" = @((Resolve-TargetScript "scripts\template\update-template.ps1"))
}

if ($Target -eq "help") {
    @(
        "Available targets:",
        "  ./make.ps1 agent-verify",
        "  ./make.ps1 act-preflight",
        "  ./make.ps1 qa",
        "  ./make.ps1 analyze-bsl",
        "  ./make.ps1 format-bsl",
        "  ./make.ps1 check-agent-docs",
        "  ./make.ps1 check-skill-bindings",
        "  ./make.ps1 check-overlay-manifest",
        "  ./make.ps1 codex-onboard",
        "  ./make.ps1 imported-skills-readiness",
        "  ./make.ps1 create-ib",
        "  ./make.ps1 dump-src",
        "  ./make.ps1 load-src",
        "  ./make.ps1 load-diff-src",
        "  ./make.ps1 load-task-src",
        "  ./make.ps1 update-db",
        "  ./make.ps1 diff-src",
        "  ./make.ps1 doctor",
        "  ./make.ps1 test-xunit",
        "  ./make.ps1 tdd-xunit",
        "  ./make.ps1 test-bdd",
        "  ./make.ps1 smoke",
        "  ./make.ps1 export-context",
        "  ./make.ps1 export-context-preview",
        "  ./make.ps1 export-context-check",
        "  ./make.ps1 export-context-write",
        "  ./make.ps1 verify-traceability",
        "  ./make.ps1 template-check-update",
        "  ./make.ps1 template-update"
    ) | ForEach-Object { Write-Output $_ }
    exit 0
}

if (-not $targets.ContainsKey($Target)) {
    Write-Error "Unknown target: $Target"
    exit 1
}

$invoke = {
    param([string[]]$Command)
    $preArgs = @()
    if ($Command.Length -gt 1) {
        $preArgs = $Command[1..($Command.Length - 1)]
    }
    & $Command[0] @preArgs @RemainingArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

if ($Target -eq "qa") {
    & $invoke @((Resolve-TargetScript "scripts\qa\analyze-bsl.ps1"))
    & $invoke @((Resolve-TargetScript "scripts\qa\check-agent-docs.ps1"))
    & $invoke @((Resolve-TargetScript "scripts\qa\check-skill-bindings.ps1"))
    & $invoke @((Resolve-TargetScript "scripts\qa\check-overlay-manifest.ps1"))
    & $invoke @((Resolve-TargetScript "scripts\llm\verify-traceability.ps1"))
    exit 0
}

$preArgs = @()
if ($targets[$Target].Length -gt 1) {
    $preArgs = $targets[$Target][1..($targets[$Target].Length - 1)]
}
& $targets[$Target][0] @preArgs @RemainingArgs
exit $LASTEXITCODE
