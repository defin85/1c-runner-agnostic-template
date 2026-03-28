#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

copy_repo() {
  local target="$1"
  local manifest=""
  mkdir -p "$target"
  if git -C "$SOURCE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    (
      cd "$SOURCE_ROOT"
      manifest="$(mktemp)"
      while IFS= read -r -d '' relpath; do
        [ -e "$relpath" ] || continue
        printf '%s\0' "$relpath" >>"$manifest"
      done < <(git ls-files -z --cached --others --exclude-standard)
      tar --null -T "$manifest" -cf -
      rm -f "$manifest"
    ) | (
      cd "$target"
      tar xf -
    )
  else
    (
      cd "$SOURCE_ROOT"
      tar --exclude=.git -cf - .
    ) | (
      cd "$target"
      tar xf -
    )
  fi
}

assert_fails_with() {
  local root="$1"
  local expected="$2"
  local path_prefix="${3:-}"
  local stderr_file="$tmpdir/stderr.log"

  if (
    cd "$root"
    PATH="${path_prefix:+$path_prefix:}$PATH" ./scripts/qa/check-agent-docs.sh >/dev/null 2>"$stderr_file"
  ); then
    printf 'check-agent-docs.sh should fail in %s\n' "$root" >&2
    exit 1
  fi

  if ! grep -Fq -- "$expected" "$stderr_file"; then
    printf 'expected error not found: %s\n' "$expected" >&2
    cat "$stderr_file" >&2
    exit 1
  fi
}

refresh_source_context() {
  local root="$1"

  (
    cd "$root"
    ./scripts/llm/export-context.sh --write >/dev/null
  )
}

render_generated_repo() {
  local template_root="$1"
  local generated_root="$2"
  local bindir="$3"

  copy_repo "$template_root"
  mkdir -p "$bindir"

  cat >"$bindir/openspec" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

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

printf 'unexpected openspec args: %s\n' "$*" >&2
exit 1
EOF

  cat >"$bindir/bd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [ "$1" = "init" ]; then
  mkdir -p .beads
fi
EOF

  chmod +x "$bindir/openspec" "$bindir/bd"

  PATH="$bindir:$PATH" copier copy --trust --defaults \
    -d project_name="Docs Contract Project" \
    -d project_slug="docs-contract-project" \
    "$template_root" \
    "$generated_root" \
    >/dev/null
}

healthy_root="$tmpdir/healthy"
copy_repo "$healthy_root"
refresh_source_context "$healthy_root"
(
  cd "$healthy_root"
  ./scripts/qa/check-agent-docs.sh >/dev/null
)

tracked_source_root="$tmpdir/tracked-source"
copy_repo "$tracked_source_root"
(
  cd "$tracked_source_root"
  git init -q
  git config user.name "Smoke Test"
  git config user.email "smoke@example.com"
  git add -A
  git commit -qm "source snapshot"
  ./scripts/llm/export-context.sh --write >/dev/null
  printf 'ci noise\n' > docs/.ci-noise.tmp
  ./scripts/qa/check-agent-docs.sh >/dev/null
)

missing_link_root="$tmpdir/missing-link"
copy_repo "$missing_link_root"
refresh_source_context "$missing_link_root"
sed -i 's#\[docs/agent/architecture.md\](docs/agent/architecture.md)#docs/agent/architecture.md#' \
  "$missing_link_root/AGENTS.md"
assert_fails_with "$missing_link_root" "missing required markdown link in AGENTS.md: docs/agent/architecture.md"

broken_link_root="$tmpdir/broken-link"
copy_repo "$broken_link_root"
refresh_source_context "$broken_link_root"
sed -i 's#(../../openspec/project.md)#(../../openspec/missing-project.md)#' \
  "$broken_link_root/docs/agent/architecture.md"
assert_fails_with "$broken_link_root" "broken markdown link in docs/agent/architecture.md:"

source_placeholder_profile_root="$tmpdir/source-placeholder-profile"
copy_repo "$source_placeholder_profile_root"
refresh_source_context "$source_placeholder_profile_root"
python - <<'PY' "$source_placeholder_profile_root/env/ci.example.json"
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
data = json.loads(path.read_text())
data["capabilities"]["smoke"] = {"command": ["bash", "-lc", "echo TODO: placeholder smoke"]}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY
assert_fails_with "$source_placeholder_profile_root" \
  "placeholder verification command remains in example profile: env/ci.example.json"

source_noop_profile_root="$tmpdir/source-noop-profile"
copy_repo "$source_noop_profile_root"
refresh_source_context "$source_noop_profile_root"
python - <<'PY' "$source_noop_profile_root/env/ci.example.json"
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
data = json.loads(path.read_text())
data["capabilities"]["smoke"] = {"command": ["true"]}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY
assert_fails_with "$source_noop_profile_root" \
  "checked-in verification contour must use unsupportedReason or a repo-owned entrypoint: env/ci.example.json (smoke)"

source_shell_wrapper_profile_root="$tmpdir/source-shell-wrapper-profile"
copy_repo "$source_shell_wrapper_profile_root"
refresh_source_context "$source_shell_wrapper_profile_root"
python - <<'PY' "$source_shell_wrapper_profile_root/env/ci.example.json"
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
data = json.loads(path.read_text())
data["capabilities"]["smoke"] = {
    "command": [
        "bash",
        "-lc",
        "./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/source-shell-wrapper-smoke || true",
    ]
}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY
assert_fails_with "$source_shell_wrapper_profile_root" \
  "checked-in verification contour must use unsupportedReason or a repo-owned entrypoint: env/ci.example.json (smoke)"

generated_template_root="$tmpdir/generated-template"
generated_root="$tmpdir/generated"
generated_bindir="$tmpdir/generated-bin"
render_generated_repo "$generated_template_root" "$generated_root" "$generated_bindir"
(
  cd "$generated_root"
  PATH="$generated_bindir:$PATH" ./scripts/qa/check-agent-docs.sh >/dev/null
)

generated_forbidden_src_cf_doc_root="$tmpdir/generated-forbidden-src-cf-doc"
cp -R "$generated_root" "$generated_forbidden_src_cf_doc_root"
cat >"$generated_forbidden_src_cf_doc_root/src/cf/AGENTS.md" <<'EOF'
# Forbidden local router
EOF
assert_fails_with "$generated_forbidden_src_cf_doc_root" \
  "forbidden non-1C markdown artifact inside deployable src/cf: src/cf/AGENTS.md" \
  "$generated_bindir"

generated_curated_project_map_root="$tmpdir/generated-curated-project-map"
cp -R "$generated_root" "$generated_curated_project_map_root"
python - <<'PY' "$generated_curated_project_map_root/automation/context/project-map.md"
from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = path.read_text().splitlines()
filtered = [
    line for line in lines
    if "docs/agent/review.md" not in line
    and "env/README.md" not in line
    and "docs/exec-plans/README.md" not in line
]
path.write_text("\n".join(filtered) + "\n")
PY
(
  cd "$generated_curated_project_map_root"
  PATH="$generated_bindir:$PATH" ./scripts/qa/check-agent-docs.sh >/dev/null
)

generated_stale_summary_root="$tmpdir/generated-stale-summary"
cp -R "$generated_root" "$generated_stale_summary_root"
printf '\n- drift\n' >>"$generated_stale_summary_root/automation/context/hotspots-summary.generated.md"
assert_fails_with "$generated_stale_summary_root" \
  "stale context file: $generated_stale_summary_root/automation/context/hotspots-summary.generated.md" \
  "$generated_bindir"

generated_stale_project_delta_root="$tmpdir/generated-stale-project-delta"
cp -R "$generated_root" "$generated_stale_project_delta_root"
printf '\n- drift\n' >>"$generated_stale_project_delta_root/automation/context/project-delta-hotspots.generated.md"
assert_fails_with "$generated_stale_project_delta_root" \
  "stale context file: $generated_stale_project_delta_root/automation/context/project-delta-hotspots.generated.md" \
  "$generated_bindir"

source_managed_work_items_root="$tmpdir/source-managed-work-items"
copy_repo "$source_managed_work_items_root"
refresh_source_context "$source_managed_work_items_root"
printf 'docs/work-items/README.md\n' >>"$source_managed_work_items_root/automation/context/template-managed-paths.txt"
assert_fails_with "$source_managed_work_items_root" \
  "project-owned work-item guide must not become template-managed: automation/context/template-managed-paths.txt"

generated_missing_runbook_root="$tmpdir/generated-missing-runbook"
cp -R "$generated_root" "$generated_missing_runbook_root"
sed -i 's/make template-check-update/template-check-update/' \
  "$generated_missing_runbook_root/docs/template-maintenance.md"
assert_fails_with "$generated_missing_runbook_root" \
  "missing expected text in docs/template-maintenance.md: make template-check-update" \
  "$generated_bindir"

generated_missing_link_root="$tmpdir/generated-missing-link"
cp -R "$generated_root" "$generated_missing_link_root"
sed -i 's#\[docs/agent/generated-project-verification.md\](docs/agent/generated-project-verification.md)#docs/agent/generated-project-verification.md#' \
  "$generated_missing_link_root/README.md"
assert_fails_with "$generated_missing_link_root" \
  "missing required markdown link in README.md: docs/agent/generated-project-verification.md" \
  "$generated_bindir"

generated_missing_runtime_support_matrix_root="$tmpdir/generated-missing-runtime-support-matrix"
cp -R "$generated_root" "$generated_missing_runtime_support_matrix_root"
rm -f \
  "$generated_missing_runtime_support_matrix_root/automation/context/runtime-support-matrix.json" \
  "$generated_missing_runtime_support_matrix_root/automation/context/runtime-support-matrix.md"
assert_fails_with "$generated_missing_runtime_support_matrix_root" \
  "missing agent-facing path: automation/context/runtime-support-matrix.json" \
  "$generated_bindir"

generated_missing_architecture_map_root="$tmpdir/generated-missing-architecture-map"
cp -R "$generated_root" "$generated_missing_architecture_map_root"
rm -f "$generated_missing_architecture_map_root/docs/agent/architecture-map.md"
assert_fails_with "$generated_missing_architecture_map_root" \
  "missing agent-facing path: docs/agent/architecture-map.md" \
  "$generated_bindir"

generated_missing_runtime_quickstart_root="$tmpdir/generated-missing-runtime-quickstart"
cp -R "$generated_root" "$generated_missing_runtime_quickstart_root"
rm -f "$generated_missing_runtime_quickstart_root/docs/agent/runtime-quickstart.md"
assert_fails_with "$generated_missing_runtime_quickstart_root" \
  "missing agent-facing path: docs/agent/runtime-quickstart.md" \
  "$generated_bindir"

generated_missing_codex_workflows_root="$tmpdir/generated-missing-codex-workflows"
cp -R "$generated_root" "$generated_missing_codex_workflows_root"
rm -f "$generated_missing_codex_workflows_root/docs/agent/codex-workflows.md"
assert_fails_with "$generated_missing_codex_workflows_root" \
  "missing agent-facing path: docs/agent/codex-workflows.md" \
  "$generated_bindir"

generated_missing_operator_local_runbook_root="$tmpdir/generated-missing-operator-local-runbook"
cp -R "$generated_root" "$generated_missing_operator_local_runbook_root"
rm -f "$generated_missing_operator_local_runbook_root/docs/agent/operator-local-runbook.md"
assert_fails_with "$generated_missing_operator_local_runbook_root" \
  "missing agent-facing path: docs/agent/operator-local-runbook.md" \
  "$generated_bindir"

generated_missing_work_items_readme_root="$tmpdir/generated-missing-work-items-readme"
cp -R "$generated_root" "$generated_missing_work_items_readme_root"
rm -f "$generated_missing_work_items_readme_root/docs/work-items/README.md"
assert_fails_with "$generated_missing_work_items_readme_root" \
  "missing agent-facing path: docs/work-items/README.md" \
  "$generated_bindir"

generated_missing_work_items_template_root="$tmpdir/generated-missing-work-items-template"
cp -R "$generated_root" "$generated_missing_work_items_template_root"
rm -f "$generated_missing_work_items_template_root/docs/work-items/TEMPLATE.md"
assert_fails_with "$generated_missing_work_items_template_root" \
  "missing agent-facing path: docs/work-items/TEMPLATE.md" \
  "$generated_bindir"

generated_missing_project_delta_hints_root="$tmpdir/generated-missing-project-delta-hints"
cp -R "$generated_root" "$generated_missing_project_delta_hints_root"
rm -f "$generated_missing_project_delta_hints_root/automation/context/project-delta-hints.json"
assert_fails_with "$generated_missing_project_delta_hints_root" \
  "missing agent-facing path: automation/context/project-delta-hints.json" \
  "$generated_bindir"

generated_missing_project_delta_hotspots_root="$tmpdir/generated-missing-project-delta-hotspots"
cp -R "$generated_root" "$generated_missing_project_delta_hotspots_root"
rm -f "$generated_missing_project_delta_hotspots_root/automation/context/project-delta-hotspots.generated.md"
assert_fails_with "$generated_missing_project_delta_hotspots_root" \
  "missing agent-facing path: automation/context/project-delta-hotspots.generated.md" \
  "$generated_bindir"

generated_missing_overlay_version_root="$tmpdir/generated-missing-overlay-version"
cp -R "$generated_root" "$generated_missing_overlay_version_root"
rm -f "$generated_missing_overlay_version_root/.template-overlay-version"
assert_fails_with "$generated_missing_overlay_version_root" \
  "missing agent-facing path: .template-overlay-version" \
  "$generated_bindir"

generated_local_private_truth_root="$tmpdir/generated-local-private-truth"
cp -R "$generated_root" "$generated_local_private_truth_root"
printf '\n- runtime doctor: `./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run`\n' \
  >>"$generated_local_private_truth_root/automation/context/project-map.md"
assert_fails_with "$generated_local_private_truth_root" \
  "local-private runtime profile must not be advertised as shared truth outside runtime support matrix: automation/context/project-map.md" \
  "$generated_bindir"

generated_placeholder_root="$tmpdir/generated-placeholder"
cp -R "$generated_root" "$generated_placeholder_root"
printf '\n<context-entry>\n' >>"$generated_placeholder_root/automation/context/project-map.md"
assert_fails_with "$generated_placeholder_root" \
  "unexpected placeholder or template note in automation/context/project-map.md: <[[:alnum:]_][^>]*>" \
  "$generated_bindir"

generated_source_centric_docs_root="$tmpdir/generated-source-centric-docs"
cp -R "$generated_root" "$generated_source_centric_docs_root"
cat >"$generated_source_centric_docs_root/docs/README.md" <<'EOF'
# Документация

Если вы новый агент в этом репозитории, начните с [docs/agent/index.md](agent/index.md).
EOF
assert_fails_with "$generated_source_centric_docs_root" \
  "missing expected text in docs/README.md: docs/agent/generated-project-index.md" \
  "$generated_bindir"

generated_missing_representative_path_root="$tmpdir/generated-missing-representative-path"
cp -R "$generated_root" "$generated_missing_representative_path_root"
python - <<'PY' "$generated_missing_representative_path_root/docs/agent/architecture-map.md"
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
old = "src/cf"
new = "src/cf/MissingRepresentativePath"
if old not in text:
    raise SystemExit("expected representative path not found")
path.write_text(text.replace(old, new, 1))
PY
assert_fails_with "$generated_missing_representative_path_root" \
  "representative path is missing: docs/agent/architecture-map.md -> src/cf/MissingRepresentativePath" \
  "$generated_bindir"

generated_missing_project_map_path_root="$tmpdir/generated-missing-project-map-path"
cp -R "$generated_root" "$generated_missing_project_map_path_root"
python - <<'PY' "$generated_missing_project_map_path_root/automation/context/project-map.md"
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
old = "src/cf"
new = "src/cf/MissingProjectMapPath"
if old not in text:
    raise SystemExit("expected representative path not found")
path.write_text(text.replace(old, new, 1))
PY
assert_fails_with "$generated_missing_project_map_path_root" \
  "representative path is missing: automation/context/project-map.md -> src/cf/MissingProjectMapPath" \
  "$generated_bindir"

generated_local_private_leak_root="$tmpdir/generated-local-private-leak"
cp -R "$generated_root" "$generated_local_private_leak_root"
printf './env/local.json\n' >>"$generated_local_private_leak_root/automation/context/source-tree.generated.txt"
assert_fails_with "$generated_local_private_leak_root" \
  "local-private path leaked into generated context: env/local.json" \
  "$generated_bindir"

generated_unsanctioned_profile_root="$tmpdir/generated-unsanctioned-profile"
cp -R "$generated_root" "$generated_unsanctioned_profile_root"
cat >"$generated_unsanctioned_profile_root/env/develop.json" <<'EOF'
{
  "profileName": "develop"
}
EOF
assert_fails_with "$generated_unsanctioned_profile_root" \
  "generated runtime profile policy leaves unsanctioned checked-in root profiles: env/develop.json" \
  "$generated_bindir"

generated_sanctioned_placeholder_root="$tmpdir/generated-sanctioned-placeholder"
cp -R "$generated_root" "$generated_sanctioned_placeholder_root"
cat >"$generated_sanctioned_placeholder_root/env/develop.json" <<'EOF'
{
  "profileName": "develop",
  "capabilities": {
    "smoke": {
      "unsupportedReason": "Contour is not wired yet"
    },
    "xunit": {
      "unsupportedReason": "Contour is not wired yet"
    },
    "bdd": {
      "unsupportedReason": "Contour is not wired yet"
    }
  }
}
EOF
cat >"$generated_sanctioned_placeholder_root/automation/context/runtime-profile-policy.json" <<'EOF'
{
  "rootEnvProfiles": {
    "canonicalExamples": [
      "env/local.example.json",
      "env/wsl.example.json",
      "env/ci.example.json",
      "env/windows-executor.example.json"
    ],
    "canonicalLocalPrivate": [
      "env/local.json",
      "env/wsl.json",
      "env/ci.json",
      "env/windows-executor.json"
    ],
    "sanctionedAdditionalProfiles": [
      "env/develop.json"
    ],
    "localSandbox": "env/.local/"
  }
}
EOF
refresh_source_context "$generated_sanctioned_placeholder_root"
(
  cd "$generated_sanctioned_placeholder_root"
  PATH="$generated_bindir:$PATH" ./scripts/qa/check-agent-docs.sh >/dev/null
)

generated_sanctioned_noop_root="$tmpdir/generated-sanctioned-noop"
cp -R "$generated_root" "$generated_sanctioned_noop_root"
cat >"$generated_sanctioned_noop_root/env/develop.json" <<'EOF'
{
  "profileName": "develop",
  "capabilities": {
    "smoke": {
      "command": ["true"]
    }
  }
}
EOF
cat >"$generated_sanctioned_noop_root/automation/context/runtime-profile-policy.json" <<'EOF'
{
  "rootEnvProfiles": {
    "canonicalExamples": [
      "env/local.example.json",
      "env/wsl.example.json",
      "env/ci.example.json",
      "env/windows-executor.example.json"
    ],
    "canonicalLocalPrivate": [
      "env/local.json",
      "env/wsl.json",
      "env/ci.json",
      "env/windows-executor.json"
    ],
    "sanctionedAdditionalProfiles": [
      "env/develop.json"
    ],
    "localSandbox": "env/.local/"
  }
}
EOF
refresh_source_context "$generated_sanctioned_noop_root"
assert_fails_with "$generated_sanctioned_noop_root" \
  "checked-in verification contour must use unsupportedReason or a repo-owned entrypoint: env/develop.json (smoke)" \
  "$generated_bindir"

generated_sanctioned_shell_wrapper_root="$tmpdir/generated-sanctioned-shell-wrapper"
cp -R "$generated_root" "$generated_sanctioned_shell_wrapper_root"
cat >"$generated_sanctioned_shell_wrapper_root/env/develop.json" <<'EOF'
{
  "profileName": "develop",
  "capabilities": {
    "smoke": {
      "command": ["bash", "-lc", "./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/generated-shell-wrapper-smoke || true"]
    }
  }
}
EOF
cat >"$generated_sanctioned_shell_wrapper_root/automation/context/runtime-profile-policy.json" <<'EOF'
{
  "rootEnvProfiles": {
    "canonicalExamples": [
      "env/local.example.json",
      "env/wsl.example.json",
      "env/ci.example.json",
      "env/windows-executor.example.json"
    ],
    "canonicalLocalPrivate": [
      "env/local.json",
      "env/wsl.json",
      "env/ci.json",
      "env/windows-executor.json"
    ],
    "sanctionedAdditionalProfiles": [
      "env/develop.json"
    ],
    "localSandbox": "env/.local/"
  }
}
EOF
refresh_source_context "$generated_sanctioned_shell_wrapper_root"
assert_fails_with "$generated_sanctioned_shell_wrapper_root" \
  "checked-in verification contour must use unsupportedReason or a repo-owned entrypoint: env/develop.json (smoke)" \
  "$generated_bindir"

generated_sanctioned_direct_entrypoint_root="$tmpdir/generated-sanctioned-direct-entrypoint"
cp -R "$generated_root" "$generated_sanctioned_direct_entrypoint_root"
cat >"$generated_sanctioned_direct_entrypoint_root/env/develop.json" <<'EOF'
{
  "profileName": "develop",
  "capabilities": {
    "smoke": {
      "command": ["./scripts/test/run-smoke.sh", "--profile", "env/local.json", "--run-root", "/tmp/generated-direct-entrypoint-smoke"]
    }
  }
}
EOF
cat >"$generated_sanctioned_direct_entrypoint_root/automation/context/runtime-profile-policy.json" <<'EOF'
{
  "rootEnvProfiles": {
    "canonicalExamples": [
      "env/local.example.json",
      "env/wsl.example.json",
      "env/ci.example.json",
      "env/windows-executor.example.json"
    ],
    "canonicalLocalPrivate": [
      "env/local.json",
      "env/wsl.json",
      "env/ci.json",
      "env/windows-executor.json"
    ],
    "sanctionedAdditionalProfiles": [
      "env/develop.json"
    ],
    "localSandbox": "env/.local/"
  }
}
EOF
refresh_source_context "$generated_sanctioned_direct_entrypoint_root"
(
  cd "$generated_sanctioned_direct_entrypoint_root"
  PATH="$generated_bindir:$PATH" ./scripts/qa/check-agent-docs.sh >/dev/null
)

generated_runtime_quickstart_drift_root="$tmpdir/generated-runtime-quickstart-drift"
cp -R "$generated_root" "$generated_runtime_quickstart_drift_root"
python - <<'PY' "$generated_runtime_quickstart_drift_root/docs/agent/runtime-quickstart.md"
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
old = "| `agent-verify` | `supported` | `make agent-verify` | `shell-only` | `docs/agent/generated-project-verification.md` |"
new = "| `agent-verify` | `unsupported` | `make agent-verify` | `shell-only` | `docs/agent/generated-project-verification.md` |"
if old not in text:
    raise SystemExit("expected runtime quickstart row not found")
path.write_text(text.replace(old, new, 1))
PY
assert_fails_with "$generated_runtime_quickstart_drift_root" \
  "runtime quick reference drifts from runtime support matrix: docs/agent/runtime-quickstart.md (agent-verify)" \
  "$generated_bindir"

generated_project_baseline_extension_missing_target_root="$tmpdir/generated-project-baseline-extension-missing-target"
cp -R "$generated_root" "$generated_project_baseline_extension_missing_target_root"
python - <<'PY' "$generated_project_baseline_extension_missing_target_root/automation/context/runtime-support-matrix.json"
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
data = json.loads(path.read_text())
data["projectSpecificBaselineExtension"] = {
    "id": "project-agent-surface-contract",
    "entrypoint": "tests/smoke/project-agent-surface-contract.sh",
    "runbookPath": "docs/agent/runtime-quickstart.md",
    "summary": "Project-owned no-1C smoke for agent/runtime truth."
}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY
assert_fails_with "$generated_project_baseline_extension_missing_target_root" \
  "project-specific baseline extension entrypoint is missing: tests/smoke/project-agent-surface-contract.sh" \
  "$generated_bindir"

generated_empty_identity_root="$tmpdir/generated-empty-identity"
cp -R "$generated_root" "$generated_empty_identity_root"
mkdir -p "$generated_empty_identity_root/src/cf"
cat >"$generated_empty_identity_root/src/cf/Configuration.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Configuration uuid="22222222-2222-2222-2222-222222222222">
    <Properties>
      <Name>GeneratedCfg</Name>
    </Properties>
  </Configuration>
</MetaDataObject>
EOF
python - <<'PY' "$generated_empty_identity_root/automation/context/metadata-index.generated.json"
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
text = text.replace('"name": ""', '"name": ""', 1)
if '"name": "GeneratedCfg"' in text:
    text = text.replace('"name": "GeneratedCfg"', '"name": ""', 1)
path.write_text(text)
PY
assert_fails_with "$generated_empty_identity_root" \
  "generated metadata leaves configuration.name empty despite src/cf/Configuration.xml" \
  "$generated_bindir"

generated_bad_closeout_root="$tmpdir/generated-bad-closeout"
cp -R "$generated_root" "$generated_bad_closeout_root"
python - <<'PY' "$generated_bad_closeout_root/AGENTS.md"
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
text = text.replace(
    "For remote-backed repos with a writable Git remote, a code-change session is not complete until the verified branch state is pushed.\n- For local-only repos or repos without a writable remote, do not invent a push-only closeout path.\n",
    "A session with code changes is not complete until `git push` succeeds.\n",
    1,
)
path.write_text(text)
PY
assert_fails_with "$generated_bad_closeout_root" \
  "generated closeout guidance must distinguish local-only and remote-backed repos: AGENTS.md" \
  "$generated_bindir"
