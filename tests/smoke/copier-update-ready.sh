#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

template_root="$tmpdir/template"
rendered_root="$tmpdir/rendered"
bindir="$tmpdir/bin"
command_log="$tmpdir/commands.log"
real_copier="$(command -v copier)"

mkdir -p "$template_root" "$bindir"

copy_template_repo() {
  local manifest=""
  if git -C "$SOURCE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    (
      cd "$SOURCE_ROOT"
      manifest="$(mktemp)"
      while IFS= read -r -d '' relpath; do
        [ -e "$relpath" ] || continue
        printf '%s\0' "$relpath" >>"$manifest"
      done < <(git ls-files -z --cached --others --modified --exclude-standard)
      tar --null -T "$manifest" -cf -
      rm -f "$manifest"
    ) | (
      cd "$template_root"
      tar xf -
    )
  else
    (
      cd "$SOURCE_ROOT"
      tar --exclude=.git -cf - .
    ) | (
      cd "$template_root"
      tar xf -
    )
  fi
}

init_git_repo() {
  local root="$1"
  local message="$2"

  git -C "$root" init -q
  git -C "$root" config user.name "Smoke Test"
  git -C "$root" config user.email "smoke@example.com"
  git -C "$root" add -A
  git -C "$root" commit -qm "$message"
}

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    printf 'actual file contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_not_contains() {
  local file="$1"
  local unexpected="$2"

  if grep -Fq -- "$unexpected" "$file"; then
    printf 'unexpected text found: %s\n' "$unexpected" >&2
    printf 'actual file contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_not_exists() {
  local path="$1"

  if [ -e "$path" ]; then
    printf 'path should not exist: %s\n' "$path" >&2
    exit 1
  fi
}

assert_exists() {
  local path="$1"

  if [ ! -e "$path" ]; then
    printf 'path does not exist: %s\n' "$path" >&2
    exit 1
  fi
}

assert_count() {
  local file="$1"
  local pattern="$2"
  local expected_count="$3"
  local actual_count

  actual_count="$(grep -Fc -- "$pattern" "$file" || true)"
  if [ "$actual_count" != "$expected_count" ]; then
    printf 'unexpected count for %s: expected %s, got %s\n' "$pattern" "$expected_count" "$actual_count" >&2
    printf 'actual log contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_line_before() {
  local file="$1"
  local first="$2"
  local second="$3"
  local first_line=""
  local second_line=""

  first_line="$(grep -nF -- "$first" "$file" | head -n 1 | cut -d: -f1)"
  second_line="$(grep -nF -- "$second" "$file" | head -n 1 | cut -d: -f1)"

  if [ -z "$first_line" ] || [ -z "$second_line" ] || [ "$first_line" -ge "$second_line" ]; then
    printf 'expected text to appear earlier in %s\nfirst: %s\nsecond: %s\n' \
      "$file" "$first" "$second" >&2
    printf 'actual file contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_jq() {
  local file="$1"
  local expr="$2"
  local label="$3"
  shift 3

  if ! jq -e "$expr" "$file" "$@" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    printf 'actual file contents:\n' >&2
    cat "$file" >&2
    exit 1
  fi
}

resolve_existing_path() {
  local candidate=""

  for candidate in "$@"; do
    if [ -e "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  printf 'none of the expected paths exist: %s\n' "$*" >&2
  exit 1
}

copy_template_repo

mkdir -p "$template_root/src/cf/DataProcessors/TestProcessor/Ext"
cat >"$template_root/src/cf/DataProcessors/TestProcessor/Ext/ObjectModule.bsl" <<'EOF'
// Smoke fixture to ensure Copier does not treat raw BSL braces as Jinja syntax.
Procedure Test()
	Сообщить("{{ raw_bsl_expression }}");
EndProcedure
EOF

cat >"$bindir/copier" <<EOF
#!/usr/bin/env bash
set -euo pipefail
printf 'copier %s\n' "\$*" >>"\$COMMAND_LOG"
exec "$real_copier" "\$@"
EOF

cat >"$bindir/openspec" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'openspec %s\n' "$*" >>"$COMMAND_LOG"

if [ "$1" = "init" ] && [ "$#" -eq 3 ] && [ "$2" = "--tools" ]; then
  mkdir -p openspec/changes openspec/specs
  cat >openspec/project.md <<'EOT'
# OpenSpec Project
EOT
  cat >AGENTS.md <<'EOT'
<!-- OPENSPEC:START -->
# OpenSpec Instructions
<!-- OPENSPEC:END -->
EOT
  exit 0
fi

if [ "$1" = "validate" ] && [ "$2" = "--all" ]; then
  exit 0
fi

printf 'unexpected openspec args: %s\n' "$*" >&2
exit 1
EOF

cat >"$bindir/bd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'bd %s\n' "$*" >>"$COMMAND_LOG"

if [ "$1" = "init" ]; then
  mkdir -p .beads
fi
EOF

chmod +x "$bindir/openspec" "$bindir/bd"
chmod +x "$bindir/copier"

init_git_repo "$template_root" "template v0.1.0"
git -C "$template_root" tag v0.1.0

PATH="$bindir:$PATH" COMMAND_LOG="$command_log" copier copy --trust --defaults \
  -d project_name="Smoke Project" \
  -d project_slug="smoke-project" \
  "$template_root" \
  "$rendered_root" \
  >/dev/null

assert_exists "$rendered_root/.copier-answers.yml"
assert_not_exists "$rendered_root/[[[ _copier_conf.answers_file ]]]"
assert_exists "$rendered_root/.codex/.gitkeep"
assert_exists "$rendered_root/.codex/config.toml"
assert_exists "$rendered_root/.codex/README.md"
assert_exists "$rendered_root/.agents/skills/README.md"
assert_exists "$rendered_root/.agents/skills/repo-agent-verify/SKILL.md"
assert_exists "$rendered_root/.claude/settings.json"
assert_exists "$rendered_root/.claude/skills/README.md"
assert_exists "$rendered_root/.claude/skills/1c-doctor/SKILL.md"
assert_exists "$rendered_root/.agents/skills/1c-load-diff-src/SKILL.md"
assert_exists "$rendered_root/.agents/skills/1c-load-task-src/SKILL.md"
assert_exists "$rendered_root/.claude/skills/1c-load-diff-src/SKILL.md"
assert_exists "$rendered_root/.claude/skills/1c-load-task-src/SKILL.md"
assert_exists "$rendered_root/.github/workflows/ci.yml"
assert_exists "$rendered_root/docs/AGENTS.md"
assert_exists "$rendered_root/docs/agent/index.md"
assert_exists "$rendered_root/docs/agent/architecture.md"
assert_exists "$rendered_root/docs/agent/generated-project-index.md"
assert_exists "$rendered_root/docs/agent/codex-workflows.md"
assert_exists "$rendered_root/docs/agent/architecture-map.md"
assert_exists "$rendered_root/docs/agent/operator-local-runbook.md"
assert_exists "$rendered_root/docs/agent/runtime-quickstart.md"
assert_exists "$rendered_root/docs/agent/generated-project-verification.md"
assert_exists "$rendered_root/docs/work-items/README.md"
assert_exists "$rendered_root/docs/work-items/TEMPLATE.md"
assert_exists "$rendered_root/docs/agent/source-vs-generated.md"
assert_exists "$rendered_root/docs/agent/verify.md"
assert_exists "$rendered_root/docs/agent/review.md"
assert_exists "$rendered_root/docs/template-maintenance.md"
assert_exists "$rendered_root/docs/exec-plans/README.md"
assert_exists "$rendered_root/docs/exec-plans/TEMPLATE.md"
assert_exists "$rendered_root/docs/exec-plans/EXAMPLE.md"
assert_exists "$rendered_root/docs/migrations/runtime-profile-v2.md"
assert_exists "$rendered_root/env/.local/README.md"
assert_exists "$rendered_root/env/AGENTS.md"
assert_exists "$rendered_root/scripts/lib/capability.sh"
assert_exists "$rendered_root/scripts/lib/ibcmd.sh"
assert_exists "$rendered_root/scripts/AGENTS.md"
assert_exists "$rendered_root/scripts/qa/agent-verify.sh"
assert_exists "$rendered_root/scripts/qa/check-agent-docs.sh"
assert_exists "$rendered_root/scripts/qa/codex-onboard.sh"
assert_exists "$rendered_root/scripts/platform/dump-src.sh"
assert_exists "$rendered_root/scripts/platform/diff-src.sh"
assert_exists "$rendered_root/scripts/platform/load-diff-src.sh"
assert_exists "$rendered_root/scripts/platform/load-task-src.sh"
assert_exists "$rendered_root/scripts/git/task-trailers.sh"
assert_exists "$rendered_root/scripts/diag/doctor.sh"
assert_exists "$rendered_root/scripts/llm/export-context.sh"
assert_exists "$rendered_root/scripts/template/migrate-runtime-profile-v2.sh"
assert_exists "$rendered_root/automation/context/project-map.md"
assert_exists "$rendered_root/automation/context/runtime-profile-policy.json"
assert_exists "$rendered_root/automation/context/runtime-support-matrix.json"
assert_exists "$rendered_root/automation/context/runtime-support-matrix.md"
assert_exists "$rendered_root/automation/context/project-delta-hints.json"
assert_exists "$rendered_root/automation/context/source-tree.generated.txt"
assert_exists "$rendered_root/automation/context/metadata-index.generated.json"
assert_exists "$rendered_root/automation/context/recommended-skills.generated.md"
assert_exists "$rendered_root/automation/context/hotspots-summary.generated.md"
assert_exists "$rendered_root/automation/context/project-delta-hotspots.generated.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-hotspots-summary.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-recommended-skills.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-architecture-map.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-operator-local-runbook.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-project-delta-hints.json"
assert_exists "$rendered_root/automation/context/templates/generated-project-project-delta-hotspots.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-project-map.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-metadata-index.json"
assert_exists "$rendered_root/automation/context/templates/generated-project-runtime-profile-policy.json"
assert_exists "$rendered_root/automation/context/templates/generated-project-runtime-quickstart.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-runtime-support-matrix.json"
assert_exists "$rendered_root/automation/context/templates/generated-project-runtime-support-matrix.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-work-items-readme.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-work-items-template.md"
assert_exists "$rendered_root/src/AGENTS.md"
assert_not_exists "$rendered_root/src/cf/AGENTS.md"
assert_not_exists "$rendered_root/src/cf/README.md"
assert_exists "$rendered_root/tests/AGENTS.md"
assert_exists "$rendered_root/tests/smoke/runtime-capability-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-doctor-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-direct-platform-xvfb-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-direct-platform-ld-preload-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-ibcmd-capability-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-ibcmd-doctor-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-ibcmd-validation-contract.sh"
assert_exists "$rendered_root/tests/smoke/git-task-trailer-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-load-task-src-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-load-task-src-validation-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-profile-legacy-rejection.sh"
assert_exists "$rendered_root/tests/smoke/runtime-profile-migration-helper.sh"
assert_exists "$rendered_root/tests/smoke/agent-docs-contract.sh"
assert_exists "$rendered_root/openspec/changes"
assert_not_exists "$rendered_root/PROJECT_RULES.md"
assert_not_exists "$rendered_root/CLAUDE.md"
assert_not_exists "$rendered_root/.claude/commands/openspec"
assert_not_exists "$rendered_root/automation/context/template-source-project-map.md"
assert_not_exists "$rendered_root/automation/context/template-source-metadata-index.json"
assert_not_exists "$rendered_root/automation/context/template-source-tree.txt"
assert_not_exists "$rendered_root/automation/context/template-source-source-files.txt"
assert_not_exists "$rendered_root/scripts/release"
assert_not_exists "$rendered_root/tests/smoke/template-release-workflow.sh"
assert_not_exists "$rendered_root/.githooks"
assert_exists "$rendered_root/docs/template-release.md"
assert_exists "$rendered_root/scripts/template/update-template.sh"
assert_exists "$rendered_root/scripts/template/check-update.sh"
assert_exists "$rendered_root/scripts/template/lib-overlay.sh"
assert_exists "$rendered_root/scripts/bootstrap/overlay-post-apply.sh"
assert_exists "$rendered_root/scripts/qa/check-overlay-manifest.sh"
assert_exists "$rendered_root/automation/context/template-managed-paths.txt"
assert_exists "$rendered_root/.template-overlay-version"
assert_contains "$rendered_root/Makefile" "template-update:"
assert_contains "$rendered_root/Makefile" "agent-verify:"
assert_contains "$rendered_root/Makefile" "check-agent-docs:"
assert_contains "$rendered_root/Makefile" "check-overlay-manifest:"
assert_contains "$rendered_root/Makefile" "codex-onboard:"
assert_contains "$rendered_root/Makefile" "imported-skills-readiness:"
assert_contains "$rendered_root/Makefile" "load-diff-src:"
assert_contains "$rendered_root/Makefile" "load-task-src:"
assert_contains "$rendered_root/Makefile" "export-context-preview:"
assert_contains "$rendered_root/Makefile" "export-context-check:"
assert_contains "$rendered_root/Makefile" "export-context-write:"
assert_contains "$rendered_root/.gitignore" ".codex/*"
assert_contains "$rendered_root/.gitignore" "!.codex/.gitkeep"
assert_contains "$rendered_root/.gitignore" "!.codex/config.toml"
assert_contains "$rendered_root/.gitignore" "!.codex/README.md"
assert_contains "$rendered_root/.gitignore" "env/local.json"
assert_contains "$rendered_root/.gitignore" "env/wsl.json"
assert_contains "$rendered_root/.gitignore" "env/.local/*.json"
assert_contains "$rendered_root/.gitignore" "src/cf/Ext/ParentConfigurations/"
assert_contains "$rendered_root/.codex/config.toml" "mcp_servers.claude-context"
assert_contains "$rendered_root/.codex/config.toml" "mcp_servers.chrome-devtools"
assert_not_contains "$rendered_root/automation/context/template-managed-paths.txt" ".codex/config.toml"
assert_contains "$rendered_root/.codex/README.md" "[docs/agent/index.md](../docs/agent/index.md)"
assert_contains "$rendered_root/.codex/README.md" "[docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md)"
assert_contains "$rendered_root/.codex/README.md" "[docs/agent/codex-workflows.md](../docs/agent/codex-workflows.md)"
assert_contains "$rendered_root/.codex/README.md" "make codex-onboard"
assert_contains "$rendered_root/.codex/README.md" "make imported-skills-readiness"
assert_contains "$rendered_root/.codex/README.md" "automation/context/recommended-skills.generated.md"
assert_contains "$rendered_root/.codex/README.md" "automation/context/runtime-support-matrix.md"
assert_contains "$rendered_root/.codex/README.md" "[env/README.md](../env/README.md)"
assert_contains "$rendered_root/.codex/README.md" "[docs/agent/review.md](../docs/agent/review.md)"
assert_contains "$rendered_root/.codex/README.md" "[docs/exec-plans/README.md](../docs/exec-plans/README.md)"
assert_contains "$rendered_root/.codex/README.md" "[docs/work-items/README.md](../docs/work-items/README.md)"
assert_contains "$rendered_root/.codex/README.md" "local-only"
assert_contains "$rendered_root/.codex/README.md" "remote-backed"
assert_contains "$rendered_root/.agents/skills/README.md" "repo-agent-verify"
assert_contains "$rendered_root/.agents/skills/README.md" "1c-load-diff-src"
assert_contains "$rendered_root/.agents/skills/README.md" "1c-load-task-src"
assert_contains "$rendered_root/.agents/skills/README.md" "cc-1c-skills"
assert_contains "$rendered_root/.agents/skills/README.md" "make imported-skills-readiness"
assert_contains "$rendered_root/.agents/skills/README.md" "cf-edit"
assert_contains "$rendered_root/.claude/skills/README.md" "1c-load-diff-src"
assert_contains "$rendered_root/.claude/skills/README.md" "1c-load-task-src"
assert_contains "$rendered_root/.claude/skills/README.md" "cc-1c-skills"
assert_contains "$rendered_root/.claude/skills/README.md" "make imported-skills-readiness"
assert_contains "$rendered_root/.claude/skills/README.md" "cf-edit"
assert_exists "$rendered_root/.agents/skills/cf-edit/SKILL.md"
assert_exists "$rendered_root/.claude/skills/cf-edit/SKILL.md"
assert_contains "$rendered_root/.agents/skills/cf-edit/SKILL.md" "./scripts/skills/run-imported-skill.sh cf-edit"
assert_contains "$rendered_root/.claude/skills/cf-edit/SKILL.md" "./scripts/skills/run-imported-skill.sh cf-edit"
assert_exists "$rendered_root/scripts/skills/run-imported-skill.sh"
assert_exists "$rendered_root/scripts/skills/run-imported-skill.ps1"
assert_exists "$rendered_root/automation/vendor/cc-1c-skills/README.md"
assert_exists "$rendered_root/automation/vendor/cc-1c-skills/imported-skills.json"
assert_exists "$rendered_root/automation/vendor/cc-1c-skills/skills/cf-edit/SKILL.md"
assert_contains "$rendered_root/.agents/skills/1c-load-task-src/SKILL.md" "--bead"
assert_contains "$rendered_root/.agents/skills/1c-load-task-src/SKILL.md" "--work-item"
assert_contains "$rendered_root/.agents/skills/1c-load-task-src/SKILL.md" "--range"
assert_contains "$rendered_root/.agents/skills/1c-load-task-src/SKILL.md" "./scripts/git/task-trailers.sh render --bead <id> --work-item <id>"
assert_contains "$rendered_root/.claude/skills/1c-load-task-src/SKILL.md" "--bead"
assert_contains "$rendered_root/.claude/skills/1c-load-task-src/SKILL.md" "--work-item"
assert_contains "$rendered_root/.claude/skills/1c-load-task-src/SKILL.md" "--range"
assert_contains "$rendered_root/.claude/skills/1c-load-task-src/SKILL.md" "./scripts/git/task-trailers.sh render --bead <id> --work-item <id>"
assert_contains "$rendered_root/docs/agent/architecture.md" "./scripts/platform/load-diff-src.sh"
assert_contains "$rendered_root/docs/agent/architecture.md" "./scripts/platform/load-task-src.sh"
assert_contains "$rendered_root/docs/agent/generated-project-verification.md" "./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run"
assert_contains "$rendered_root/docs/agent/generated-project-verification.md" "./scripts/platform/load-task-src.sh --profile env/local.json --bead task.1 --run-root /tmp/load-task-src-run"
assert_contains "$rendered_root/env/README.md" "./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run"
assert_contains "$rendered_root/env/README.md" "./scripts/platform/load-task-src.sh --profile env/local.json --bead demo.1 --run-root /tmp/load-task-src-run"
assert_contains "$rendered_root/env/README.md" "./scripts/git/task-trailers.sh render --bead demo.1 --work-item 93984"
assert_contains "$rendered_root/.github/workflows/ci.yml" "name: CI"
assert_contains "$rendered_root/.github/workflows/ci.yml" "name: Runtime doctor"
assert_contains "$rendered_root/.github/workflows/ci.yml" "name: Check agent docs"
assert_contains "$rendered_root/.github/workflows/ci.yml" "name: Agent docs contract"
assert_contains "$rendered_root/.github/workflows/ci.yml" "actions/checkout@v5"
assert_exists "$rendered_root/.github/actions/setup-openspec/action.yml"
assert_contains "$rendered_root/.github/workflows/ci.yml" "./.github/actions/setup-openspec"
assert_contains "$rendered_root/.github/workflows/ci.yml" "actions/setup-python@v6"
assert_contains "$rendered_root/.github/workflows/ci.yml" "openspec validate --all --strict --no-interactive"
assert_contains "$rendered_root/.github/workflows/ci.yml" "apt-get install -y jq ripgrep"
assert_contains "$rendered_root/.github/actions/setup-openspec/action.yml" "actions/setup-node@v5"
assert_contains "$rendered_root/.github/actions/setup-openspec/action.yml" "@fission-ai/openspec@\${{ inputs.openspec-version }}"
assert_contains "$rendered_root/.github/workflows/ci.yml" "runtime-gate:"
assert_contains "$rendered_root/.github/workflows/ci.yml" "needs.runtime-gate.outputs.ci_profile_present == 'true'"
assert_contains "$rendered_root/.github/workflows/ci.yml" "runtime-direct-platform-ld-preload-contract.sh"
assert_contains "$rendered_root/env/local.example.json" "\"driver\": \"ibcmd\""
assert_jq "$rendered_root/env/local.example.json" '.runnerAdapter == "direct-platform" and .ibcmd.runtimeMode == "file-infobase" and .ibcmd.serverAccess.mode == "data-dir" and .capabilities.loadSrc.driver == "ibcmd"' "local-example-driver"
assert_jq "$rendered_root/env/ci.example.json" '.runnerAdapter == "direct-platform" and .ibcmd.runtimeMode == "dbms-infobase" and .ibcmd.dbmsInfobase.kind == "PostgreSQL" and .capabilities.loadSrc.driver == "designer"' "ci-example-driver"
assert_jq "$rendered_root/env/wsl.example.json" '.runnerAdapter == "direct-platform" and .ibcmd.runtimeMode == "standalone-server" and .platform.xvfb.enabled == true and .platform.xvfb.serverArgs == ["-screen","0","1440x900x24","-noreset"] and .platform.ldPreload.enabled == true and .platform.ldPreload.libraries == ["/usr/lib/libstdc++.so.6","/usr/lib/libgcc_s.so.1"] and .capabilities.loadSrc.driver == "designer"' "wsl-example-driver"
assert_jq "$rendered_root/env/windows-executor.example.json" '.runnerAdapter == "remote-windows" and .capabilities.loadSrc.driver == "designer"' "windows-example-driver"
assert_jq "$rendered_root/env/local.example.json" '.capabilities.xunit.command == ["./scripts/test/run-xunit-direct-platform.sh"] and .capabilities.xunit.harnessSourceDir == "./src/epf/TemplateXUnitHarness" and .capabilities.xunit.configPath == "./tests/xunit/smoke.quickstart.json" and .capabilities.xunit.timeoutSeconds == 900 and .capabilities.smoke.unsupportedReason != null and .capabilities.bdd.unsupportedReason != null' "local-example-xunit"
assert_jq "$rendered_root/env/ci.example.json" '.capabilities.xunit.command == ["./scripts/test/run-xunit-direct-platform.sh"] and .capabilities.xunit.harnessSourceDir == "./src/epf/TemplateXUnitHarness" and .capabilities.xunit.configPath == "./tests/xunit/smoke.quickstart.json" and .capabilities.xunit.timeoutSeconds == 900 and .capabilities.smoke.unsupportedReason != null and .capabilities.bdd.unsupportedReason != null' "ci-example-xunit"
assert_jq "$rendered_root/env/wsl.example.json" '.capabilities.xunit.command == ["./scripts/test/run-xunit-direct-platform.sh"] and .capabilities.xunit.harnessSourceDir == "./src/epf/TemplateXUnitHarness" and .capabilities.xunit.configPath == "./tests/xunit/smoke.quickstart.json" and .capabilities.xunit.timeoutSeconds == 900 and .capabilities.smoke.unsupportedReason != null and .capabilities.bdd.unsupportedReason != null' "wsl-example-xunit"
assert_jq "$rendered_root/env/windows-executor.example.json" '.capabilities.smoke.unsupportedReason != null and .capabilities.xunit.unsupportedReason != null and .capabilities.bdd.unsupportedReason != null and .capabilities.publishHttp.unsupportedReason != null' "windows-example-unsupported"
assert_exists "$rendered_root/scripts/test/run-xunit-direct-platform.sh"
assert_exists "$rendered_root/scripts/test/build-xunit-epf.sh"
assert_exists "$rendered_root/scripts/test/tdd-xunit.sh"
assert_exists "$rendered_root/docs/testing/xunit-direct-platform.md"
assert_exists "$rendered_root/tests/xunit/smoke.quickstart.json"
assert_exists "$rendered_root/src/epf/TemplateXUnitHarness/TemplateXUnitHarness.xml"
assert_exists "$rendered_root/src/epf/TemplateXUnitHarness/TemplateXUnitHarness/Ext/ObjectModule.bsl"
assert_not_exists "$rendered_root/src/epf/TemplateXUnitHarness/TemplateXUnitHarness/Forms"
assert_contains "$rendered_root/src/epf/TemplateXUnitHarness/TemplateXUnitHarness.xml" "<DefaultForm/>"
assert_contains "$rendered_root/src/epf/TemplateXUnitHarness/TemplateXUnitHarness/Ext/ObjectModule.bsl" "Template xUnit harness"
assert_contains "$rendered_root/docs/testing/xunit-direct-platform.md" "./scripts/test/tdd-xunit.sh"
assert_contains "$rendered_root/docs/testing/xunit-direct-platform.md" "./scripts/platform/load-src.sh"
assert_contains "$rendered_root/README.md" "generated 1С-проект"
assert_contains "$rendered_root/README.md" "[docs/agent/generated-project-index.md](docs/agent/generated-project-index.md)"
assert_contains "$rendered_root/README.md" "[automation/context/runtime-support-matrix.md](automation/context/runtime-support-matrix.md)"
assert_contains "$rendered_root/README.md" "[automation/context/runtime-support-matrix.json](automation/context/runtime-support-matrix.json)"
assert_contains "$rendered_root/README.md" "[automation/context/project-map.md](automation/context/project-map.md)"
assert_contains "$rendered_root/README.md" "[docs/agent/architecture-map.md](docs/agent/architecture-map.md)"
assert_contains "$rendered_root/README.md" "[docs/agent/codex-workflows.md](docs/agent/codex-workflows.md)"
assert_contains "$rendered_root/README.md" "[docs/agent/operator-local-runbook.md](docs/agent/operator-local-runbook.md)"
assert_contains "$rendered_root/README.md" "[docs/agent/runtime-quickstart.md](docs/agent/runtime-quickstart.md)"
assert_contains "$rendered_root/README.md" "[docs/work-items/README.md](docs/work-items/README.md)"
assert_contains "$rendered_root/README.md" "[automation/context/recommended-skills.generated.md](automation/context/recommended-skills.generated.md)"
assert_contains "$rendered_root/README.md" "[automation/context/hotspots-summary.generated.md](automation/context/hotspots-summary.generated.md)"
assert_contains "$rendered_root/README.md" "[automation/context/project-delta-hotspots.generated.md](automation/context/project-delta-hotspots.generated.md)"
assert_contains "$rendered_root/README.md" "[automation/context/metadata-index.generated.json](automation/context/metadata-index.generated.json)"
assert_contains "$rendered_root/README.md" "[automation/context/runtime-profile-policy.json](automation/context/runtime-profile-policy.json)"
assert_contains "$rendered_root/README.md" "[docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md)"
assert_contains "$rendered_root/README.md" "[docs/agent/review.md](docs/agent/review.md)"
assert_contains "$rendered_root/README.md" "[env/README.md](env/README.md)"
assert_contains "$rendered_root/README.md" "[.agents/skills/README.md](.agents/skills/README.md)"
assert_contains "$rendered_root/README.md" "[.codex/README.md](.codex/README.md)"
assert_contains "$rendered_root/README.md" "[docs/exec-plans/README.md](docs/exec-plans/README.md)"
assert_contains "$rendered_root/README.md" "[docs/template-maintenance.md](docs/template-maintenance.md)"
assert_contains "$rendered_root/README.md" "make codex-onboard"
assert_contains "$rendered_root/README.md" "make imported-skills-readiness"
assert_contains "$rendered_root/README.md" "make agent-verify"
assert_contains "$rendered_root/README.md" "make tdd-xunit"
assert_contains "$rendered_root/README.md" "Ownership Classes"
assert_contains "$rendered_root/README.md" ".template-overlay-version"
assert_contains "$rendered_root/README.md" "local-only"
assert_contains "$rendered_root/README.md" "remote-backed"
assert_contains "$rendered_root/env/README.md" "driver=ibcmd"
assert_contains "$rendered_root/env/README.md" "xvfb-run"
assert_contains "$rendered_root/env/README.md" "LD_PRELOAD"
assert_contains "$rendered_root/env/README.md" "env/.local/"
assert_contains "$rendered_root/env/README.md" "unsupportedReason"
assert_contains "$rendered_root/env/README.md" "ONEC_PROJECT_ROOT"
assert_contains "$rendered_root/env/README.md" "ONEC_CAPABILITY_RUN_ROOT"
assert_contains "$rendered_root/env/README.md" "make imported-skills-readiness"
assert_contains "$rendered_root/env/README.md" "./scripts/test/tdd-xunit.sh"
assert_contains "$rendered_root/env/README.md" "./scripts/test/run-xunit-direct-platform.sh"
assert_contains "$rendered_root/AGENTS.md" 'Start with [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md) for the generated-project-first onboarding path.'
assert_contains "$rendered_root/AGENTS.md" 'Run `make codex-onboard` for a read-only first screen in a generated repo.'
assert_contains "$rendered_root/AGENTS.md" 'Use [automation/context/project-map.md](automation/context/project-map.md) as the project-owned repo map.'
assert_contains "$rendered_root/AGENTS.md" 'Use [automation/context/runtime-support-matrix.md](automation/context/runtime-support-matrix.md) and [automation/context/runtime-support-matrix.json](automation/context/runtime-support-matrix.json) as the checked-in runtime support truth.'
assert_contains "$rendered_root/AGENTS.md" 'Use [automation/context/recommended-skills.generated.md](automation/context/recommended-skills.generated.md) as the compact project-aware skill router before opening the full catalog.'
assert_contains "$rendered_root/AGENTS.md" 'Use [automation/context/hotspots-summary.generated.md](automation/context/hotspots-summary.generated.md) as the compact generated-derived map for the first hour.'
assert_contains "$rendered_root/AGENTS.md" 'Use [automation/context/metadata-index.generated.json](automation/context/metadata-index.generated.json) as the deeper generated-derived inventory for narrowing the `src/` search space.'
assert_contains "$rendered_root/AGENTS.md" 'Use [automation/context/runtime-profile-policy.json](automation/context/runtime-profile-policy.json) for sanctioned checked-in runtime profile policy.'
assert_contains "$rendered_root/AGENTS.md" 'Use [docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md) and `make agent-verify` as the first no-1C verification path.'
assert_contains "$rendered_root/AGENTS.md" 'Use `make imported-skills-readiness` before executable imported compatibility skills when the local contour may miss Python/Node dependencies.'
assert_contains "$rendered_root/AGENTS.md" 'Use [docs/agent/codex-workflows.md](docs/agent/codex-workflows.md) as the canonical Codex workflow guide after the first router step.'
assert_contains "$rendered_root/AGENTS.md" 'Use [docs/agent/review.md](docs/agent/review.md), [docs/agent/operator-local-runbook.md](docs/agent/operator-local-runbook.md), [env/README.md](env/README.md), [.agents/skills/README.md](.agents/skills/README.md), [docs/exec-plans/README.md](docs/exec-plans/README.md), and [docs/work-items/README.md](docs/work-items/README.md) as the main follow-up routers.'
assert_contains "$rendered_root/AGENTS.md" 'Use [docs/template-maintenance.md](docs/template-maintenance.md) only for template refresh and maintenance work.'
assert_contains "$rendered_root/AGENTS.md" './scripts/platform/load-diff-src.sh --profile <operator-profile> --run-root /tmp/load-diff-src-run'
assert_contains "$rendered_root/AGENTS.md" './scripts/platform/load-task-src.sh --profile <operator-profile> --bead <id> --run-root /tmp/load-task-src-run'
assert_contains "$rendered_root/AGENTS.md" 'For remote-backed repos with a writable Git remote, a code-change session is not complete until the verified branch state is pushed.'
assert_contains "$rendered_root/AGENTS.md" 'For local-only repos or repos without a writable remote, do not invent a push-only closeout path.'
assert_contains "$rendered_root/docs/README.md" "[docs/agent/generated-project-index.md](agent/generated-project-index.md)"
assert_contains "$rendered_root/docs/AGENTS.md" "[docs/agent/generated-project-index.md](agent/generated-project-index.md)"
assert_contains "$rendered_root/docs/template-release.md" "source repo шаблона"
assert_contains "$rendered_root/docs/template-release.md" "./scripts/release/publish-overlay-release.sh --tag v0.3.6"
assert_contains "$rendered_root/env/AGENTS.md" "automation/context/runtime-profile-policy.json"
assert_contains "$rendered_root/tests/AGENTS.md" "scripts/qa/check-agent-docs.sh"
assert_contains "$rendered_root/scripts/AGENTS.md" "automation/context/hotspots-summary.generated.md"
assert_contains "$rendered_root/scripts/AGENTS.md" "automation/context/recommended-skills.generated.md"
assert_contains "$rendered_root/src/AGENTS.md" "[docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md)"
assert_contains "$rendered_root/src/AGENTS.md" "docs/agent/architecture-map.md"
assert_contains "$rendered_root/src/AGENTS.md" "docs/agent/runtime-quickstart.md"
assert_contains "$rendered_root/src/AGENTS.md" "automation/context/project-map.md"
assert_contains "$rendered_root/src/AGENTS.md" "automation/context/recommended-skills.generated.md"
assert_contains "$rendered_root/src/AGENTS.md" "automation/context/hotspots-summary.generated.md"
assert_contains "$rendered_root/src/AGENTS.md" "automation/context/project-delta-hotspots.generated.md"
assert_contains "$rendered_root/src/AGENTS.md" "automation/context/metadata-index.generated.json"
assert_contains "$rendered_root/src/AGENTS.md" "src/cf/CommonModules"
assert_contains "$rendered_root/src/AGENTS.md" "src/cf/ScheduledJobs"
assert_contains "$rendered_root/src/README.md" "LoadConfigFromFiles"
assert_contains "$rendered_root/src/README.md" "статического анализа BSL"
assert_contains "$rendered_root/src/README.md" "сравнения изменений в Git"
assert_line_before \
  "$rendered_root/docs/agent/generated-project-index.md" \
  "docs/agent/architecture-map.md" \
  "automation/context/metadata-index.generated.json"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "docs/agent/codex-workflows.md"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "docs/agent/operator-local-runbook.md"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "automation/context/recommended-skills.generated.md"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "make imported-skills-readiness"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "automation/context/project-delta-hotspots.generated.md"
assert_line_before \
  "$rendered_root/docs/agent/generated-project-index.md" \
  "docs/agent/runtime-quickstart.md" \
  "automation/context/metadata-index.generated.json"
assert_line_before \
  "$rendered_root/docs/agent/generated-project-index.md" \
  "automation/context/hotspots-summary.generated.md" \
  "automation/context/metadata-index.generated.json"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "make codex-onboard"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "docs/agent/architecture-map.md"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "docs/agent/runtime-quickstart.md"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "automation/context/runtime-support-matrix.md"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "OpenSpec -> bd -> docs/exec-plans/TEMPLATE.md -> docs/work-items/README.md"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "docs/exec-plans/TEMPLATE.md"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "docs/work-items/README.md"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "docs/work-items/TEMPLATE.md"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "./scripts/platform/load-diff-src.sh --profile <operator-profile> --run-root /tmp/load-diff-src-run"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "./scripts/platform/load-task-src.sh --profile <operator-profile> --bead <id> --run-root /tmp/load-task-src-run"
assert_contains "$rendered_root/automation/context/project-map.md" "role: generated 1С-проект"
assert_contains "$rendered_root/automation/context/project-map.md" "Repo-Derived Snapshot"
assert_contains "$rendered_root/automation/context/project-map.md" "generated-derived"
assert_contains "$rendered_root/automation/context/project-map.md" "automation/context/runtime-profile-policy.json"
assert_contains "$rendered_root/automation/context/project-map.md" "automation/context/runtime-support-matrix.md"
assert_contains "$rendered_root/automation/context/project-map.md" "docs/agent/architecture-map.md"
assert_contains "$rendered_root/automation/context/project-map.md" "docs/agent/operator-local-runbook.md"
assert_contains "$rendered_root/automation/context/project-map.md" "docs/agent/runtime-quickstart.md"
assert_contains "$rendered_root/automation/context/project-map.md" "automation/context/recommended-skills.generated.md"
assert_contains "$rendered_root/automation/context/project-map.md" "docs/work-items/README.md"
assert_contains "$rendered_root/automation/context/project-map.md" "automation/context/project-delta-hints.json"
assert_contains "$rendered_root/automation/context/project-map.md" "automation/context/project-delta-hotspots.generated.md"
assert_contains "$rendered_root/automation/context/project-map.md" "docs/agent/review.md"
assert_contains "$rendered_root/automation/context/project-map.md" "env/README.md"
assert_contains "$rendered_root/automation/context/project-map.md" "docs/exec-plans/README.md"
assert_contains "$rendered_root/automation/context/runtime-support-matrix.md" "# Runtime Support Matrix"
assert_contains "$rendered_root/automation/context/runtime-support-matrix.md" '`operator-local`'
assert_contains "$rendered_root/automation/context/runtime-support-matrix.md" "## Optional Project-Specific Baseline Extension"
assert_jq "$rendered_root/automation/context/runtime-support-matrix.json" '.matrixRole == "project-owned-runtime-support-matrix" and (.statuses | sort) == ["operator-local","provisioned","supported","unsupported"] and ([.contours[].id] | sort) == ["agent-verify","bdd","codex-onboard","doctor","export-context-check","load-diff-src","load-task-src","publish-http","smoke","xunit"] and .projectSpecificBaselineExtension == null and (.contours[] | select(.id == "doctor") | .runbookPath) == "docs/agent/operator-local-runbook.md" and (.contours[] | select(.id == "load-diff-src") | .runbookPath) == "docs/agent/operator-local-runbook.md" and (.contours[] | select(.id == "load-task-src") | .runbookPath) == "docs/agent/operator-local-runbook.md" and (.contours[] | select(.id == "xunit") | .status) == "operator-local" and (.contours[] | select(.id == "xunit") | .runbookPath) == "docs/testing/xunit-direct-platform.md"' "generated-runtime-support-matrix"
assert_contains "$rendered_root/automation/context/recommended-skills.generated.md" "# Generated Recommended Skills"
assert_contains "$rendered_root/automation/context/recommended-skills.generated.md" "make imported-skills-readiness"
assert_contains "$rendered_root/automation/context/recommended-skills.generated.md" ".agents/skills/README.md"
assert_contains "$rendered_root/automation/context/hotspots-summary.generated.md" "# Generated Hotspots Summary"
assert_contains "$rendered_root/automation/context/hotspots-summary.generated.md" "automation/context/recommended-skills.generated.md"
assert_contains "$rendered_root/automation/context/hotspots-summary.generated.md" "## Task-to-Path Routing"
assert_contains "$rendered_root/automation/context/hotspots-summary.generated.md" "automation/context/runtime-profile-policy.json"
assert_contains "$rendered_root/automation/context/hotspots-summary.generated.md" "docs/agent/architecture-map.md"
assert_contains "$rendered_root/automation/context/hotspots-summary.generated.md" "docs/agent/runtime-quickstart.md"
assert_contains "$rendered_root/automation/context/hotspots-summary.generated.md" "docs/work-items/README.md"
assert_contains "$rendered_root/automation/context/hotspots-summary.generated.md" "automation/context/project-delta-hotspots.generated.md"
assert_contains "$rendered_root/automation/context/source-tree.generated.txt" "# Generated Project Tree"
assert_jq "$rendered_root/automation/context/project-delta-hints.json" '.hintsRole == "project-owned-project-delta-hints" and (.selectors.pathPrefixes | type == "array") and (.selectors.pathKeywords | type == "array") and (.representativePaths | type == "array")' "generated-project-delta-hints"
assert_contains "$rendered_root/automation/context/project-delta-hotspots.generated.md" "# Generated Project-Delta Hotspots"
assert_contains "$rendered_root/automation/context/project-delta-hotspots.generated.md" "automation/context/project-delta-hints.json"
assert_contains "$rendered_root/automation/context/project-delta-hotspots.generated.md" "No project-delta selectors are declared yet."
assert_contains "$rendered_root/docs/agent/codex-workflows.md" "# Codex Workflows"
assert_contains "$rendered_root/docs/agent/codex-workflows.md" "docs/exec-plans/TEMPLATE.md"
assert_contains "$rendered_root/docs/agent/codex-workflows.md" "docs/work-items/README.md"
assert_contains "$rendered_root/docs/agent/codex-workflows.md" "docs/work-items/TEMPLATE.md"
assert_contains "$rendered_root/docs/agent/operator-local-runbook.md" "# Operator-Local Runbook"
assert_contains "$rendered_root/docs/agent/operator-local-runbook.md" "automation/context/runtime-support-matrix.md"
assert_contains "$rendered_root/docs/agent/operator-local-runbook.md" "./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run"
assert_contains "$rendered_root/docs/agent/operator-local-runbook.md" "./scripts/platform/load-task-src.sh --profile env/local.json --bead task.1 --run-root /tmp/load-task-src-run"
assert_contains "$rendered_root/docs/agent/operator-local-runbook.md" "docs/testing/xunit-direct-platform.md"
assert_contains "$rendered_root/docs/agent/operator-local-runbook.md" "docs/work-items/README.md"
assert_contains "$rendered_root/docs/agent/generated-project-verification.md" "./scripts/test/tdd-xunit.sh"
assert_contains "$rendered_root/docs/agent/generated-project-verification.md" "docs/testing/xunit-direct-platform.md"
assert_contains "$rendered_root/docs/agent/generated-project-verification.md" "make imported-skills-readiness"
assert_contains "$rendered_root/docs/agent/runtime-quickstart.md" "## Contour Quick Reference"
assert_contains "$rendered_root/docs/agent/runtime-quickstart.md" "## AI-Ready First Pass"
assert_contains "$rendered_root/docs/agent/runtime-quickstart.md" "automation/context/runtime-support-matrix.md"
assert_contains "$rendered_root/docs/agent/runtime-quickstart.md" "automation/context/recommended-skills.generated.md"
assert_contains "$rendered_root/docs/agent/runtime-quickstart.md" "make imported-skills-readiness"
assert_contains "$rendered_root/docs/agent/runtime-quickstart.md" "## Optional Project-Specific Baseline Extension"
assert_contains "$rendered_root/docs/agent/runtime-quickstart.md" "docs/agent/operator-local-runbook.md"
assert_contains "$rendered_root/docs/agent/runtime-quickstart.md" "docs/work-items/README.md"
assert_contains "$rendered_root/docs/agent/architecture-map.md" "## Representative Change Scenarios"
assert_contains "$rendered_root/docs/agent/architecture-map.md" "src/cf"
assert_contains "$rendered_root/docs/agent/architecture-map.md" "scripts/test"
assert_contains "$rendered_root/docs/agent/architecture-map.md" "automation/context/recommended-skills.generated.md"
assert_contains "$rendered_root/docs/agent/architecture-map.md" "automation/context/project-delta-hotspots.generated.md"
assert_contains "$rendered_root/docs/exec-plans/TEMPLATE.md" "# Execution Plan Template"
assert_contains "$rendered_root/docs/exec-plans/EXAMPLE.md" "# Example Execution Plan"
assert_jq "$rendered_root/automation/context/metadata-index.generated.json" '.inventoryRole == "generated-derived" and .authoritativeDocs.projectMap == "automation/context/project-map.md" and .authoritativeDocs.architectureMap == "docs/agent/architecture-map.md" and .authoritativeDocs.runtimeQuickstart == "docs/agent/runtime-quickstart.md" and .authoritativeDocs.operatorLocalRunbook == "docs/agent/operator-local-runbook.md" and .authoritativeDocs.codexWorkflows == "docs/agent/codex-workflows.md" and .authoritativeDocs.workItemsGuide == "docs/work-items/README.md" and .authoritativeDocs.workItemsTemplate == "docs/work-items/TEMPLATE.md" and .authoritativeDocs.projectDeltaHints == "automation/context/project-delta-hints.json" and .authoritativeDocs.projectDeltaHotspots == "automation/context/project-delta-hotspots.generated.md" and .authoritativeDocs.review == "docs/agent/review.md" and .authoritativeDocs.envReadme == "env/README.md" and .authoritativeDocs.executionPlans == "docs/exec-plans/README.md" and .authoritativeDocs.runtimeProfilePolicy == "automation/context/runtime-profile-policy.json" and .authoritativeDocs.hotspotsSummary == "automation/context/hotspots-summary.generated.md" and .authoritativeDocs.recommendedSkills == "automation/context/recommended-skills.generated.md" and .entrypointInventory.configurationRoots == ["src/cf","src/cfe","src/epf","src/erf"]' "generated-metadata-index"
assert_jq "$rendered_root/automation/context/runtime-profile-policy.json" '.rootEnvProfiles.sanctionedAdditionalProfiles == []' "generated-runtime-policy"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "scripts/template/update-template.sh"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-hotspots-summary.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-recommended-skills.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-architecture-map.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-operator-local-runbook.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-project-delta-hints.json"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-project-delta-hotspots.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-runtime-profile-policy.json"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-runtime-quickstart.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-runtime-support-matrix.json"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-runtime-support-matrix.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-work-items-readme.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "automation/context/templates/generated-project-work-items-template.md"
assert_not_contains "$rendered_root/automation/context/template-managed-paths.txt" "docs/work-items/README.md"
assert_not_contains "$rendered_root/automation/context/template-managed-paths.txt" "docs/work-items/TEMPLATE.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "docs/agent/codex-workflows.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "docs/template-release.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "docs/exec-plans/TEMPLATE.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "docs/exec-plans/EXAMPLE.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "env/AGENTS.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "tests/AGENTS.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "scripts/AGENTS.md"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "scripts/qa/codex-onboard.sh"
assert_contains "$rendered_root/automation/context/template-managed-paths.txt" "src/README.md"
assert_not_contains "$rendered_root/automation/context/template-managed-paths.txt" "src/cf/AGENTS.md"
assert_contains "$rendered_root/.template-overlay-version" "v0.1.0"
assert_contains "$rendered_root/src/cf/DataProcessors/TestProcessor/Ext/ObjectModule.bsl" "{{ raw_bsl_expression }}"

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make agent-verify >/dev/null
)

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make export-context-check >/dev/null
)

imported_readiness_output="$tmpdir/imported-skills-readiness.txt"
(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make imported-skills-readiness >"$imported_readiness_output"
)
assert_contains "$imported_readiness_output" "Imported Skill Readiness"
assert_contains "$imported_readiness_output" "make imported-skills-readiness"
assert_contains "$imported_readiness_output" "./scripts/skills/run-imported-skill.sh --readiness"

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make check-overlay-manifest >/dev/null
)

status_before_preview="$(git -C "$rendered_root" status --short)"
codex_onboard_output="$tmpdir/codex-onboard.txt"
(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make codex-onboard >"$codex_onboard_output"
)
status_after_onboard="$(git -C "$rendered_root" status --short)"
if [ "$status_before_preview" != "$status_after_onboard" ]; then
  printf 'codex-onboard path must not change the worktree\n' >&2
  printf 'before:\n%s\n' "$status_before_preview" >&2
  printf 'after:\n%s\n' "$status_after_onboard" >&2
  exit 1
fi
assert_contains "$codex_onboard_output" "Repository role: generated-project"
assert_contains "$codex_onboard_output" "Canonical onboarding router: docs/agent/generated-project-index.md"
assert_contains "$codex_onboard_output" "Workflow guide: docs/agent/codex-workflows.md"
assert_contains "$codex_onboard_output" "Architecture map: docs/agent/architecture-map.md"
assert_contains "$codex_onboard_output" "Operator-local runbook: docs/agent/operator-local-runbook.md"
assert_contains "$codex_onboard_output" "Runtime quick reference: docs/agent/runtime-quickstart.md"
assert_contains "$codex_onboard_output" "Runtime support matrix (md): automation/context/runtime-support-matrix.md"
assert_contains "$codex_onboard_output" "Recommended skills: automation/context/recommended-skills.generated.md"
assert_contains "$codex_onboard_output" "Project-delta hints: automation/context/project-delta-hints.json"
assert_contains "$codex_onboard_output" "Project-delta hotspots: automation/context/project-delta-hotspots.generated.md"
assert_contains "$codex_onboard_output" "Work-items guide: docs/work-items/README.md"
assert_contains "$codex_onboard_output" "Work-item template: docs/work-items/TEMPLATE.md"
assert_contains "$codex_onboard_output" "Project-specific baseline extension: not declared"
assert_contains "$codex_onboard_output" "AI-readiness:"
assert_contains "$codex_onboard_output" "Codex controls:"
assert_contains "$codex_onboard_output" "/plan"
assert_contains "$codex_onboard_output" "/compact"
assert_contains "$codex_onboard_output" "/review"
assert_contains "$codex_onboard_output" "/ps"
assert_contains "$codex_onboard_output" "/mcp"
assert_contains "$codex_onboard_output" "make agent-verify"
assert_contains "$codex_onboard_output" "make imported-skills-readiness"
assert_contains "$codex_onboard_output" "docs/exec-plans/TEMPLATE.md"
assert_contains "$codex_onboard_output" "docs/work-items/README.md"

status_before_preview="$(git -C "$rendered_root" status --short)"
preview_output="$tmpdir/export-context-preview.txt"
(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make export-context-preview >"$preview_output"
)
status_after_preview="$(git -C "$rendered_root" status --short)"
if [ "$status_before_preview" != "$status_after_preview" ]; then
  printf 'preview export-context path must not change the worktree\n' >&2
  printf 'before:\n%s\n' "$status_before_preview" >&2
  printf 'after:\n%s\n' "$status_after_preview" >&2
  exit 1
fi
assert_contains "$preview_output" "=== automation/context/source-tree.generated.txt ==="
assert_contains "$preview_output" "=== automation/context/metadata-index.generated.json ==="
assert_contains "$preview_output" "=== automation/context/recommended-skills.generated.md ==="
assert_contains "$preview_output" "=== automation/context/hotspots-summary.generated.md ==="
assert_contains "$preview_output" "=== automation/context/project-delta-hotspots.generated.md ==="

status_before_export="$(git -C "$rendered_root" status --short)"
(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make export-context >/dev/null
)
status_after_export="$(git -C "$rendered_root" status --short)"
if [ "$status_before_export" != "$status_after_export" ]; then
  printf 'default export-context path must not change the worktree\n' >&2
  printf 'before:\n%s\n' "$status_before_export" >&2
  printf 'after:\n%s\n' "$status_after_export" >&2
  exit 1
fi

assert_count "$command_log" "openspec init --tools none" "1"
assert_count "$command_log" "bd init --stealth -p smoke-project" "1"

git -C "$rendered_root" config user.name "Smoke Test"
git -C "$rendered_root" config user.email "smoke@example.com"
git -C "$rendered_root" add -A
git -C "$rendered_root" commit -qm "generated v0.1.0"

cat >>"$rendered_root/README.md" <<'EOF'

## Project-Owned Smoke Marker

- README marker must survive template overlay apply.
EOF

cat >>"$rendered_root/automation/context/project-map.md" <<'EOF'

## Project-Owned Smoke Marker

- project-map marker must survive template overlay apply.
EOF

cat >>"$rendered_root/openspec/project.md" <<'EOF'

## Project-Owned Smoke Marker

- openspec marker must survive template overlay apply.
EOF

cat >>"$rendered_root/.codex/config.toml" <<'EOF'

# Project-owned Smoke Marker
LOCAL_SMOKE_MARKER = "must survive template overlay apply"
EOF

git -C "$rendered_root" add README.md automation/context/project-map.md openspec/project.md .codex/config.toml
git -C "$rendered_root" commit -qm "project-owned edits"

rm -f "$rendered_root/src/cf/DataProcessors/TestProcessor/Ext/ObjectModule.bsl"
mkdir -p "$rendered_root/src/cf/DataProcessors/ReimportedProcessor/Ext"
cat >"$rendered_root/src/cf/DataProcessors/ReimportedProcessor/Ext/ObjectModule.bsl" <<'EOF'
// Smoke fixture to prove overlay updates ignore product source churn.
Procedure Reimported()
	Сообщить("src tree churn must survive overlay apply");
EndProcedure
EOF
git -C "$rendered_root" add -A src/cf
git -C "$rendered_root" commit -qm "simulate src reimport churn"

rm -f "$rendered_root/AGENTS.md"
git -C "$rendered_root" add AGENTS.md
git -C "$rendered_root" commit -qm "remove agents"

cat >"$template_root/docs/template-update-note.txt" <<'EOF'
This file is added in template v0.2.0 to verify copier update.
EOF
printf '%s\n' "docs/template-update-note.txt" >>"$template_root/automation/context/template-managed-paths.txt"

python - <<PY
from pathlib import Path

path = Path("$template_root/scripts/bootstrap/agents-overlay.sh")
old = "6. Do not treat TODO/checklist/status files as proof of implementation.\\n\\n## Landing the Plane\\n"
new = "6. Do not treat TODO/checklist/status files as proof of implementation.\\n7. Refresh managed AGENTS overlays during template updates.\\n\\n## Landing the Plane\\n"
text = path.read_text()
if old not in text:
    raise SystemExit("overlay marker not found")
path.write_text(text.replace(old, new, 1))
PY

python - <<PY
from pathlib import Path

path = Path("$template_root/scripts/bootstrap/generated-project-surface.sh")
old = "- Template maintenance path вынесен в [docs/template-maintenance.md](docs/template-maintenance.md) и не является primary feature-delivery workflow.\\n"
new = "- Template maintenance path вынесен в [docs/template-maintenance.md](docs/template-maintenance.md) и не является primary feature-delivery workflow.\\n- Generated-derived inventory refresh-ится отдельной explicit write-командой.\\n"
text = path.read_text()
if old not in text:
    raise SystemExit("generated README router marker not found")
path.write_text(text.replace(old, new, 1))
PY

git -C "$template_root" add -A
git -C "$template_root" commit -qm "template v0.2.0"
git -C "$template_root" tag v0.2.0

status_before_template_check="$(git -C "$rendered_root" status --short)"
template_check_output="$tmpdir/template-check-update.txt"
(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make template-check-update >"$template_check_output"
)
status_after_template_check="$(git -C "$rendered_root" status --short)"
if [ "$status_before_template_check" != "$status_after_template_check" ]; then
  printf 'template-check-update must not change the worktree\n' >&2
  printf 'before:\n%s\n' "$status_before_template_check" >&2
  printf 'after:\n%s\n' "$status_after_template_check" >&2
  exit 1
fi
assert_contains "$template_check_output" "Current overlay version: v0.1.0"
assert_contains "$template_check_output" "Available overlay release: v0.2.0"
assert_contains "$template_check_output" "Overlay update available."

template_update_output="$tmpdir/template-update-v0.2.0.txt"
(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make template-update >"$template_update_output"
)
assert_contains "$template_update_output" "Current overlay version: v0.1.0"
assert_contains "$template_update_output" "Target overlay release: v0.2.0"

assert_exists "$rendered_root/docs/template-update-note.txt"
assert_exists "$rendered_root/AGENTS.md"
assert_contains "$rendered_root/AGENTS.md" "Refresh managed AGENTS overlays during template updates."
assert_contains "$rendered_root/.gitignore" ".codex/*"
assert_contains "$rendered_root/.gitignore" "!.codex/README.md"
assert_contains "$rendered_root/.gitignore" "src/cf/Ext/ParentConfigurations/"
assert_exists "$rendered_root/.codex/README.md"
assert_exists "$rendered_root/.agents/skills/README.md"
assert_exists "$rendered_root/.agents/skills/repo-agent-verify/SKILL.md"
assert_exists "$rendered_root/.agents/skills/cf-edit/SKILL.md"
assert_exists "$rendered_root/.claude/settings.json"
assert_exists "$rendered_root/.claude/skills/1c-doctor/SKILL.md"
assert_exists "$rendered_root/.claude/skills/cf-edit/SKILL.md"
assert_exists "$rendered_root/.github/workflows/ci.yml"
assert_exists "$rendered_root/docs/AGENTS.md"
assert_exists "$rendered_root/docs/agent/index.md"
assert_exists "$rendered_root/docs/agent/generated-project-index.md"
assert_exists "$rendered_root/docs/agent/codex-workflows.md"
assert_exists "$rendered_root/docs/agent/operator-local-runbook.md"
assert_exists "$rendered_root/docs/agent/generated-project-verification.md"
assert_exists "$rendered_root/docs/template-maintenance.md"
assert_exists "$rendered_root/docs/exec-plans/README.md"
assert_exists "$rendered_root/docs/work-items/README.md"
assert_exists "$rendered_root/docs/work-items/TEMPLATE.md"
assert_exists "$rendered_root/docs/migrations/runtime-profile-v2.md"
assert_exists "$rendered_root/env/.local/README.md"
assert_exists "$rendered_root/env/AGENTS.md"
assert_exists "$rendered_root/scripts/qa/agent-verify.sh"
assert_exists "$rendered_root/scripts/qa/check-agent-docs.sh"
assert_exists "$rendered_root/scripts/skills/run-imported-skill.sh"
assert_exists "$rendered_root/scripts/AGENTS.md"
assert_exists "$rendered_root/automation/context/project-map.md"
assert_exists "$rendered_root/automation/context/project-delta-hints.json"
assert_exists "$rendered_root/automation/context/runtime-profile-policy.json"
assert_exists "$rendered_root/automation/vendor/cc-1c-skills/imported-skills.json"
assert_exists "$rendered_root/automation/context/source-tree.generated.txt"
assert_exists "$rendered_root/automation/context/metadata-index.generated.json"
assert_exists "$rendered_root/automation/context/recommended-skills.generated.md"
assert_exists "$rendered_root/automation/context/hotspots-summary.generated.md"
assert_exists "$rendered_root/automation/context/project-delta-hotspots.generated.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-hotspots-summary.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-recommended-skills.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-operator-local-runbook.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-project-delta-hints.json"
assert_exists "$rendered_root/automation/context/templates/generated-project-project-delta-hotspots.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-project-map.md"
assert_exists "$rendered_root/automation/context/templates/generated-project-runtime-profile-policy.json"
assert_exists "$rendered_root/src/AGENTS.md"
assert_exists "$rendered_root/tests/AGENTS.md"
assert_exists "$rendered_root/tests/smoke/agent-docs-contract.sh"
assert_exists "$rendered_root/scripts/lib/capability.sh"
assert_exists "$rendered_root/scripts/lib/ibcmd.sh"
assert_exists "$rendered_root/scripts/platform/dump-src.sh"
assert_exists "$rendered_root/scripts/platform/diff-src.sh"
assert_exists "$rendered_root/scripts/diag/doctor.sh"
assert_exists "$rendered_root/scripts/template/migrate-runtime-profile-v2.sh"
assert_exists "$rendered_root/openspec/changes"
assert_exists "$rendered_root/tests/smoke/runtime-ibcmd-capability-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-ibcmd-doctor-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-ibcmd-validation-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-direct-platform-xvfb-contract.sh"
assert_exists "$rendered_root/tests/smoke/runtime-direct-platform-ld-preload-contract.sh"
assert_not_exists "$rendered_root/PROJECT_RULES.md"
assert_not_exists "$rendered_root/CLAUDE.md"
assert_not_exists "$rendered_root/.claude/commands/openspec"
assert_not_exists "$rendered_root/automation/context/template-source-project-map.md"
assert_not_exists "$rendered_root/automation/context/template-source-metadata-index.json"
assert_not_exists "$rendered_root/automation/context/template-source-tree.txt"
assert_not_exists "$rendered_root/automation/context/template-source-source-files.txt"
assert_contains "$rendered_root/.github/workflows/ci.yml" "actions/checkout@v5"
assert_exists "$rendered_root/.github/actions/setup-openspec/action.yml"
assert_contains "$rendered_root/.github/workflows/ci.yml" "./.github/actions/setup-openspec"
assert_contains "$rendered_root/.github/workflows/ci.yml" "actions/setup-python@v6"
assert_contains "$rendered_root/.github/workflows/ci.yml" "openspec validate --all --strict --no-interactive"
assert_contains "$rendered_root/.github/workflows/ci.yml" "apt-get install -y jq ripgrep"
assert_contains "$rendered_root/.github/actions/setup-openspec/action.yml" "actions/setup-node@v5"
assert_contains "$rendered_root/.github/actions/setup-openspec/action.yml" "@fission-ai/openspec@\${{ inputs.openspec-version }}"
assert_contains "$rendered_root/.github/workflows/ci.yml" "name: Check agent docs"
assert_contains "$rendered_root/.github/workflows/ci.yml" "name: Agent docs contract"
assert_contains "$rendered_root/.github/workflows/ci.yml" "runtime-gate:"
assert_contains "$rendered_root/.github/workflows/ci.yml" "needs.runtime-gate.outputs.ci_profile_present == 'true'"
assert_contains "$rendered_root/.github/workflows/ci.yml" "runtime-direct-platform-ld-preload-contract.sh"
assert_contains "$rendered_root/env/local.example.json" "\"driver\": \"ibcmd\""
assert_contains "$rendered_root/README.md" "Generated-derived inventory refresh-ится отдельной explicit write-командой."
assert_contains "$rendered_root/README.md" "README marker must survive template overlay apply."
assert_contains "$rendered_root/automation/context/project-map.md" "project-map marker must survive template overlay apply."
assert_contains "$rendered_root/openspec/project.md" "openspec marker must survive template overlay apply."
assert_contains "$rendered_root/.codex/config.toml" "LOCAL_SMOKE_MARKER = \"must survive template overlay apply\""
assert_exists "$rendered_root/src/cf/DataProcessors/ReimportedProcessor/Ext/ObjectModule.bsl"
assert_not_exists "$rendered_root/src/cf/DataProcessors/TestProcessor/Ext/ObjectModule.bsl"
assert_contains "$rendered_root/.template-overlay-version" "v0.2.0"
assert_line_before \
  "$rendered_root/docs/agent/generated-project-index.md" \
  "automation/context/hotspots-summary.generated.md" \
  "automation/context/metadata-index.generated.json"
assert_count "$command_log" "openspec init --tools none" "1"
assert_count "$command_log" "bd init --stealth -p smoke-project" "1"
assert_count "$command_log" "copier copy --trust --defaults" "1"

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make export-context-check >/dev/null
)

git -C "$rendered_root" add -A
git -C "$rendered_root" commit -qm "generated v0.2.0"

rm -f \
  "$rendered_root/README.md" \
  "$rendered_root/scripts/platform/load-diff-src.sh" \
  "$rendered_root/.agents/skills/1c-load-diff-src/SKILL.md" \
  "$rendered_root/.claude/skills/1c-load-diff-src/SKILL.md" \
  "$rendered_root/docs/agent/generated-project-index.md" \
  "$rendered_root/docs/agent/generated-project-verification.md"

git -C "$rendered_root" add -A
git -C "$rendered_root" commit -qm "remove readme and load-diff-src surface"

cat >"$rendered_root/src/README.md" <<'EOF'
# Source Tree

`src/` — это единственный источник deployable исходников.

Сюда не складываются:

- временные заметки;
- архив задач;
- traceability;
- тестовые отчеты;
- ad-hoc выгрузки для обсуждения.

Подкаталоги:

- `cf/` — исходники основной конфигурации
- `cfe/` — исходники расширений
- `epf/` — внешние обработки
- `erf/` — внешние отчеты
EOF

cat >"$rendered_root/src/cf/AGENTS.md" <<'EOF'
# Legacy local router
EOF
cat >"$rendered_root/src/cf/README.md" <<'EOF'
# Legacy source note
EOF
git -C "$rendered_root" add -A
git -C "$rendered_root" commit -qm "reintroduce legacy source-root docs"

cat >"$template_root/docs/template-update-v3-note.txt" <<'EOF'
This file is added in template v0.3.0 to verify README recovery.
EOF
printf '%s\n' "docs/template-update-v3-note.txt" >>"$template_root/automation/context/template-managed-paths.txt"

python - "$template_root/scripts/bootstrap/generated-project-surface.sh" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
old = "## Agent Entry Point\n\n"
new = "## Agent Entry Point\n\n- README recovery during template update must restore generated-project identity instead of the source-template overview.\n\n"
text = path.read_text()
if old not in text:
    raise SystemExit("generated README recovery marker not found")
path.write_text(text.replace(old, new, 1))
PY

git -C "$template_root" add -A
git -C "$template_root" commit -qm "template v0.3.0"
git -C "$template_root" tag v0.3.0

template_update_recovery_output="$tmpdir/template-update-v0.3.0.txt"
(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make template-update >"$template_update_recovery_output"
)

assert_contains "$template_update_recovery_output" "Target overlay release: v0.3.0"
assert_exists "$rendered_root/README.md"
assert_exists "$rendered_root/docs/template-update-v3-note.txt"
assert_exists "$rendered_root/scripts/platform/load-diff-src.sh"
assert_exists "$rendered_root/.agents/skills/1c-load-diff-src/SKILL.md"
assert_exists "$rendered_root/.claude/skills/1c-load-diff-src/SKILL.md"
assert_exists "$rendered_root/docs/agent/generated-project-index.md"
assert_exists "$rendered_root/docs/agent/generated-project-verification.md"
assert_contains "$rendered_root/src/README.md" "LoadConfigFromFiles"
assert_contains "$rendered_root/src/README.md" "статического анализа BSL"
assert_contains "$rendered_root/src/README.md" "сравнения изменений в Git"
assert_not_exists "$rendered_root/src/cf/AGENTS.md"
assert_not_exists "$rendered_root/src/cf/README.md"
assert_contains "$rendered_root/README.md" "# Smoke Project"
assert_not_contains "$rendered_root/README.md" "# 1c-runner-agnostic-template"
assert_contains "$rendered_root/.codex/config.toml" "LOCAL_SMOKE_MARKER = \"must survive template overlay apply\""
assert_contains "$rendered_root/.template-overlay-version" "v0.3.0"
assert_contains "$rendered_root/scripts/platform/load-diff-src.sh" "load-diff-src"
assert_contains "$rendered_root/.agents/skills/1c-load-diff-src/SKILL.md" "./scripts/platform/load-diff-src.sh"
assert_contains "$rendered_root/.claude/skills/1c-load-diff-src/SKILL.md" "./scripts/platform/load-diff-src.sh"
assert_contains "$rendered_root/docs/agent/generated-project-index.md" "./scripts/platform/load-diff-src.sh --profile <operator-profile> --run-root /tmp/load-diff-src-run"
assert_contains "$rendered_root/docs/agent/generated-project-verification.md" "./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run"

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make export-context-check >/dev/null
)

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make agent-verify >/dev/null
)

printf '{"fixture":true}\n' >"$rendered_root/env/.local/drift.json"
ignored_status="$(git -C "$rendered_root" status --short --ignored -- env/.local/drift.json)"
if ! grep -Fq -- "!! env/.local/drift.json" <<<"$ignored_status"; then
  printf 'env/.local drift profile must be ignored by git\n' >&2
  printf '%s\n' "$ignored_status" >&2
  exit 1
fi

runtime_fake_designer="$bindir/fake-1cv8"
runtime_fake_ibcmd="$bindir/fake-ibcmd"
runtime_wsl_bindir="$tmpdir/wsl-bin"
runtime_fake_wsl_designer="$runtime_wsl_bindir/1cv8"
runtime_fake_xvfb="$bindir/xvfb-run"
runtime_fake_xauth="$bindir/xauth"
runtime_doctor_run="$tmpdir/runtime-doctor"
runtime_layout_warning_run="$tmpdir/runtime-layout-warning"
runtime_load_run="$tmpdir/runtime-load"
runtime_wsl_doctor_run="$tmpdir/runtime-wsl-doctor"
runtime_wsl_create_run="$tmpdir/runtime-wsl-create"
wsl_libstdcpp_path=""
wsl_libgcc_path=""

mkdir -p "$runtime_wsl_bindir"

cat >"$runtime_fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'fake-1cv8 should not be invoked\n' >&2
exit 99
EOF

cat >"$runtime_fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

cat >"$runtime_fake_wsl_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

printf 'fake-wsl-1cv8\n'
printf 'ld-preload=%s\n' "${LD_PRELOAD:-}"
for arg in "$@"; do
  printf '%s\n' "$arg"
done
EOF

cat >"$runtime_fake_xvfb" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

printf 'fake-xvfb-run\n'
for arg in "$@"; do
  printf 'wrapper-arg=%s\n' "$arg"
done

while [ "$#" -gt 0 ]; do
  case "$1" in
    -a|--auto-servernum)
      shift
      ;;
    --error-file=*|--server-args=*)
      shift
      ;;
    --error-file|--server-args)
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -*)
      shift
      ;;
    *)
      break
      ;;
  esac
done

"$@"
EOF

cat >"$runtime_fake_xauth" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF

chmod +x "$runtime_fake_designer" "$runtime_fake_ibcmd" "$runtime_fake_wsl_designer" "$runtime_fake_xvfb" "$runtime_fake_xauth"

jq \
  --arg binary_path "$runtime_fake_designer" \
  --arg ibcmd_path "$runtime_fake_ibcmd" \
  --arg data_dir "$tmpdir/runtime-ibcmd-data" \
  --arg database_path "$tmpdir/runtime-ibcmd-db" \
  '.platform.binaryPath = $binary_path
   | .platform.ibcmdPath = $ibcmd_path
   | .ibcmd.serverAccess.dataDir = $data_dir
   | .ibcmd.fileInfobase.databasePath = $database_path' \
  "$rendered_root/env/local.example.json" >"$rendered_root/env/local.json"

mkdir -p "$tmpdir/runtime-ibcmd-data"
assert_jq "$rendered_root/env/local.json" '.platform.binaryPath == $ARGS.positional[0]' "runtime-local-binary-path" --args "$runtime_fake_designer"
assert_jq "$rendered_root/env/local.json" '.platform.ibcmdPath == $ARGS.positional[0]' "runtime-local-ibcmd-path" --args "$runtime_fake_ibcmd"

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" ONEC_IBCMD_PASSWORD="copier-smoke-ibcmd-secret" ./scripts/diag/doctor.sh --profile env/local.json --run-root "$runtime_doctor_run" >/dev/null
)

assert_jq "$runtime_doctor_run/summary.json" '.status == "success"' "runtime-doctor-status"
assert_jq "$runtime_doctor_run/summary.json" '.capability_drivers["load-src"].driver == "ibcmd"' "runtime-doctor-load-driver"
assert_jq "$runtime_doctor_run/summary.json" '[.checks.derived_contours[] | select(.name == "load-diff-src" and .status == "present" and .driver == "ibcmd")] | length == 1' "runtime-doctor-load-diff-derived"
assert_jq "$runtime_doctor_run/summary.json" '[.checks.derived_contours[] | select(.name == "load-task-src" and .status == "present" and .driver == "ibcmd")] | length == 1' "runtime-doctor-load-task-derived"
assert_jq "$runtime_doctor_run/summary.json" '.capability_drivers["load-src"].context.runtime_mode == "file-infobase"' "runtime-doctor-runtime-mode"
assert_jq "$runtime_doctor_run/summary.json" '[.checks.required_env_refs[] | select(.name == "ONEC_IBCMD_PASSWORD" and .status == "set")] | length == 1' "runtime-doctor-env-ref"

printf '{"fixture":true}\n' >"$rendered_root/env/develop.json"
ignored_status="$(git -C "$rendered_root" status --short --ignored -- env/local.json env/develop.json env/wsl.json)"
if ! grep -Fq -- "!! env/local.json" <<<"$ignored_status"; then
  printf 'env/local.json must be ignored by git\n' >&2
  printf '%s\n' "$ignored_status" >&2
  exit 1
fi
if grep -Fq -- "!! env/develop.json" <<<"$ignored_status"; then
  printf 'non-canonical env/develop.json must not be ignored by git\n' >&2
  printf '%s\n' "$ignored_status" >&2
  exit 1
fi

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" ONEC_IBCMD_PASSWORD="copier-smoke-ibcmd-secret" ./scripts/diag/doctor.sh --profile env/local.json --run-root "$runtime_layout_warning_run" >/dev/null
)

assert_jq "$runtime_layout_warning_run/summary.json" '.status == "success"' "runtime-layout-warning-status"
assert_jq "$runtime_layout_warning_run/summary.json" '.warnings.runtime_profile_layout.status == "warning"' "runtime-layout-warning-state"
assert_jq "$runtime_layout_warning_run/summary.json" '.warnings.runtime_profile_layout.unexpected_root_profiles | index("env/develop.json") != null' "runtime-layout-warning-path"
assert_jq "$runtime_layout_warning_run/summary.json" '.warnings.runtime_profile_layout.recommended_sandbox == "env/.local/"' "runtime-layout-warning-sandbox"

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" ONEC_IBCMD_PASSWORD="copier-smoke-ibcmd-secret" ./scripts/platform/load-src.sh \
    --profile env/local.json \
    --run-root "$runtime_load_run" \
    --files "Catalogs/Items.xml,Forms/List.xml" >/dev/null
)

assert_jq "$runtime_load_run/summary.json" '.status == "success"' "runtime-load-status"
assert_jq "$runtime_load_run/summary.json" '.driver == "ibcmd"' "runtime-load-driver"
assert_jq "$runtime_load_run/summary.json" '.driver_context.partial_import == true' "runtime-load-partial"
assert_contains "$runtime_load_run/stdout.log" "config"
assert_contains "$runtime_load_run/stdout.log" "import"
assert_contains "$runtime_load_run/stdout.log" "files"
assert_contains "$runtime_load_run/stdout.log" "--database-path=$tmpdir/runtime-ibcmd-db"
assert_contains "$runtime_load_run/stdout.log" "--base-dir=$rendered_root/src/cf"
assert_contains "$runtime_load_run/stdout.log" "--partial"
assert_contains "$runtime_load_run/stdout.log" "Catalogs/Items.xml"
assert_contains "$runtime_load_run/stdout.log" "Forms/List.xml"

mkdir -p "$rendered_root/src/cf/EventSubscriptions"
printf '<config changed />\n' >"$rendered_root/src/cf/Configuration.xml"
printf '<subscription new />\n' >"$rendered_root/src/cf/EventSubscriptions/LoadDiff.xml"
runtime_load_diff_run="$tmpdir/runtime-load-diff-run"

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" ONEC_IBCMD_PASSWORD="copier-smoke-ibcmd-secret" ./scripts/platform/load-diff-src.sh \
    --profile env/local.json \
    --run-root "$runtime_load_diff_run" >/dev/null
)

assert_jq "$runtime_load_diff_run/summary.json" '.status == "success"' "runtime-load-diff-status"
assert_jq "$runtime_load_diff_run/summary.json" '.selection.selected_files | sort == ["Configuration.xml", "EventSubscriptions/LoadDiff.xml"]' "runtime-load-diff-selected"
assert_jq "$runtime_load_diff_run/summary.json" '.delegated.capability == "load-src"' "runtime-load-diff-delegated"
assert_jq "$runtime_load_diff_run/load-src/summary.json" '.driver_context.partial_import == true' "runtime-load-diff-partial"
assert_contains "$runtime_load_diff_run/load-src/stdout.log" "Configuration.xml"
assert_contains "$runtime_load_diff_run/load-src/stdout.log" "EventSubscriptions/LoadDiff.xml"

(
  cd "$rendered_root"
  git add src/cf/Configuration.xml src/cf/EventSubscriptions/LoadDiff.xml
  git commit -qm $'task-scoped runtime smoke\n\nBead: copier-runtime.1\nWork-Item: 93984'
)

runtime_load_task_run="$tmpdir/runtime-load-task-run"

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" ONEC_IBCMD_PASSWORD="copier-smoke-ibcmd-secret" ./scripts/platform/load-task-src.sh \
    --profile env/local.json \
    --run-root "$runtime_load_task_run" \
    --bead copier-runtime.1 >/dev/null
)

assert_jq "$runtime_load_task_run/summary.json" '.status == "success"' "runtime-load-task-status"
assert_jq "$runtime_load_task_run/summary.json" '.selection.selector.mode == "bead"' "runtime-load-task-selector-mode"
assert_jq "$runtime_load_task_run/summary.json" '.selection.selector.value == "copier-runtime.1"' "runtime-load-task-selector-value"
assert_jq "$runtime_load_task_run/summary.json" '.selection.selected_files | sort == ["Configuration.xml", "EventSubscriptions/LoadDiff.xml"]' "runtime-load-task-selected"
assert_jq "$runtime_load_task_run/summary.json" '.delegated.capability == "load-src"' "runtime-load-task-delegated"
assert_jq "$runtime_load_task_run/load-src/summary.json" '.driver_context.partial_import == true' "runtime-load-task-partial"
assert_contains "$runtime_load_task_run/load-src/stdout.log" "Configuration.xml"
assert_contains "$runtime_load_task_run/load-src/stdout.log" "EventSubscriptions/LoadDiff.xml"

jq \
  --arg binary_path "$runtime_fake_wsl_designer" \
  --arg wsl_libstdcpp_path "$(resolve_existing_path /usr/lib/libstdc++.so.6 /usr/lib/x86_64-linux-gnu/libstdc++.so.6)" \
  --arg wsl_libgcc_path "$(resolve_existing_path /usr/lib/libgcc_s.so.1 /lib/x86_64-linux-gnu/libgcc_s.so.1 /usr/lib/x86_64-linux-gnu/libgcc_s.so.1)" \
  '.platform.binaryPath = $binary_path
   | .platform.ldPreload.libraries = [$wsl_libstdcpp_path, $wsl_libgcc_path]' \
  "$rendered_root/env/wsl.example.json" >"$rendered_root/env/wsl.json"

wsl_libstdcpp_path="$(jq -r '.platform.ldPreload.libraries[0]' "$rendered_root/env/wsl.json")"
wsl_libgcc_path="$(jq -r '.platform.ldPreload.libraries[1]' "$rendered_root/env/wsl.json")"

ignored_status="$(git -C "$rendered_root" status --short --ignored -- env/wsl.json)"
if ! grep -Fq -- "!! env/wsl.json" <<<"$ignored_status"; then
  printf 'env/wsl.json must be ignored by git\n' >&2
  printf '%s\n' "$ignored_status" >&2
  exit 1
fi

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" ./scripts/diag/doctor.sh --profile env/wsl.json --run-root "$runtime_wsl_doctor_run" >/dev/null
)

assert_jq "$runtime_wsl_doctor_run/summary.json" '.status == "success"' "runtime-wsl-doctor-status"
assert_jq "$runtime_wsl_doctor_run/summary.json" '.adapter_context.wrapper == "xvfb-run"' "runtime-wsl-doctor-wrapper"
assert_jq "$runtime_wsl_doctor_run/summary.json" '.adapter_context.ld_preload.enabled == true' "runtime-wsl-doctor-ldpreload"
assert_jq "$runtime_wsl_doctor_run/summary.json" '.adapter_context.ld_preload.libraries == $ARGS.positional' "runtime-wsl-doctor-ldpreload-libraries" \
  --args "$wsl_libstdcpp_path" "$wsl_libgcc_path"
assert_jq "$runtime_wsl_doctor_run/summary.json" '[.checks.required_tools[] | select(.name == "xvfb-run" and .status == "present")] | length == 1' "runtime-wsl-doctor-xvfb"
assert_jq "$runtime_wsl_doctor_run/summary.json" '[.checks.required_tools[] | select(.name == "xauth" and .status == "present")] | length == 1' "runtime-wsl-doctor-xauth"

(
  cd "$rendered_root"
  PATH="$bindir:$PATH" ./scripts/platform/create-ib.sh --profile env/wsl.json --run-root "$runtime_wsl_create_run" >/dev/null
)

assert_jq "$runtime_wsl_create_run/summary.json" '.status == "success"' "runtime-wsl-create-status"
assert_jq "$runtime_wsl_create_run/summary.json" '.adapter_context.wrapper == "xvfb-run"' "runtime-wsl-create-wrapper"
assert_jq "$runtime_wsl_create_run/summary.json" '.adapter_context.ld_preload.enabled == true' "runtime-wsl-create-ldpreload"
assert_contains "$runtime_wsl_create_run/stdout.log" "fake-xvfb-run"
assert_contains "$runtime_wsl_create_run/stdout.log" "fake-wsl-1cv8"
assert_contains "$runtime_wsl_create_run/stdout.log" "ld-preload=$wsl_libstdcpp_path:$wsl_libgcc_path"
