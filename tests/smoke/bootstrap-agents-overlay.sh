#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

project_root="$tmpdir/project"
bindir="$tmpdir/bin"
bd_log="$tmpdir/bd.log"

mkdir -p "$project_root/scripts/bootstrap" "$project_root/scripts/lib" "$project_root/scripts/llm" "$project_root/scripts/template" "$bindir"
git init -q "$project_root" >/dev/null 2>&1

cp "$SOURCE_ROOT/scripts/bootstrap/agents-overlay.sh" "$project_root/scripts/bootstrap/agents-overlay.sh"
cp "$SOURCE_ROOT/scripts/bootstrap/copier-post-copy.sh" "$project_root/scripts/bootstrap/copier-post-copy.sh"
cp "$SOURCE_ROOT/scripts/bootstrap/generated-project-surface.sh" "$project_root/scripts/bootstrap/generated-project-surface.sh"
cp "$SOURCE_ROOT/scripts/lib/common.sh" "$project_root/scripts/lib/common.sh"
cp "$SOURCE_ROOT/scripts/llm/export-context.sh" "$project_root/scripts/llm/export-context.sh"
cp "$SOURCE_ROOT/scripts/template/lib-overlay.sh" "$project_root/scripts/template/lib-overlay.sh"

cat >"$bindir/openspec" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ] || [ "$1" != "init" ] || [ "$2" != "--tools" ]; then
  printf 'unexpected openspec args: %s\n' "$*" >&2
  exit 1
fi

if [ ! -f AGENTS.md ]; then
  cat >AGENTS.md <<'EOT'
<!-- OPENSPEC:START -->
# OpenSpec Instructions
<!-- OPENSPEC:END -->
EOT
fi
EOF

cat >"$bindir/bd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$BD_LOG"
EOF

chmod +x "$bindir/openspec" "$bindir/bd"

run_bootstrap() {
  (
    cd "$project_root"
    PATH="$bindir:$PATH" BD_LOG="$bd_log" bash ./scripts/bootstrap/copier-post-copy.sh \
      "$SOURCE_ROOT" \
      "Sample Project" \
      "sample-project" \
      "Тестовый generated проект" \
      "direct-platform" \
      "none" \
      "no" \
      "yes" \
      "sample-project" \
      >/dev/null
  )
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

assert_count() {
  local file="$1"
  local pattern="$2"
  local expected_count="$3"
  local actual_count

  actual_count="$(grep -Fc -- "$pattern" "$file" || true)"
  if [ "$actual_count" != "$expected_count" ]; then
    printf 'unexpected count for %s: expected %s, got %s\n' "$pattern" "$expected_count" "$actual_count" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_next_line() {
  local file="$1"
  local expected_current="$2"
  local expected_next="$3"

  if ! awk -v expected_current="$expected_current" -v expected_next="$expected_next" '
    $0 == expected_current {
      found = 1
      if (getline next_line <= 0) {
        exit 2
      }
      if (next_line != expected_next) {
        exit 1
      }
      exit 0
    }
    END {
      if (!found) {
        exit 3
      }
    }
  ' "$file"; then
    printf 'expected "%s" to be followed immediately by "%s"\n' "$expected_current" "$expected_next" >&2
    cat "$file" >&2
    exit 1
  fi
}

run_bootstrap
run_bootstrap

agents_file="$project_root/AGENTS.md"
readme_file="$project_root/README.md"
project_map_file="$project_root/automation/context/project-map.md"
metadata_index_file="$project_root/automation/context/metadata-index.generated.json"
source_tree_file="$project_root/automation/context/source-tree.generated.txt"
openspec_project_file="$project_root/openspec/project.md"
overlay_version_file="$project_root/.template-overlay-version"
manifest_file="$project_root/automation/context/template-managed-paths.txt"
docs_agents_file="$project_root/docs/AGENTS.md"
src_agents_file="$project_root/src/AGENTS.md"

assert_contains "$agents_file" "We operate in a cycle: **OpenSpec (What) -> Beads (How) -> Code (Implementation)**."
assert_contains "$agents_file" 'This repository is a generated 1С-project created from `1c-runner-agnostic-template`.'
assert_contains "$agents_file" 'Start with [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md) for the generated-project-first onboarding path.'
assert_contains "$agents_file" 'Use [automation/context/project-map.md](automation/context/project-map.md) as the project-owned repo map.'
assert_contains "$agents_file" 'Use [docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md) and `make agent-verify` as the first no-1C verification path.'
assert_contains "$agents_file" 'Use [docs/template-maintenance.md](docs/template-maintenance.md) only for template refresh and maintenance work.'
assert_contains "$agents_file" 'Use [docs/agent/review.md](docs/agent/review.md), [env/README.md](env/README.md), [.agents/skills/README.md](.agents/skills/README.md), [.codex/README.md](.codex/README.md), and [docs/exec-plans/README.md](docs/exec-plans/README.md) as the main follow-up routers.'
assert_contains "$agents_file" 'Do not move to production code for new or major changes without explicit approval. Canonical signal: `Go!`.'
assert_contains "$agents_file" 'Use `bd` as the source of truth for code-change tracking.'
assert_contains "$agents_file" 'Final delivery must include explicit `Requirement -> Code -> Test` evidence with concrete file paths.'
assert_contains "$agents_file" '1. `mcp__claude-context__search_code`, if available in the current environment'
assert_contains "$agents_file" 'For remote-backed repos with a writable Git remote, a code-change session is not complete until the verified branch state is pushed.'
assert_contains "$agents_file" 'For local-only repos or repos without a writable remote, do not invent a push-only closeout path.'
assert_count "$agents_file" "<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->" "1"
assert_next_line "$agents_file" "<!-- OPENSPEC:END -->" "<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->"

assert_contains "$readme_file" "<!-- RUNNER_AGNOSTIC_PROJECT:START -->"
assert_contains "$readme_file" "generated 1С-проект"
assert_contains "$readme_file" "[automation/context/project-map.md](automation/context/project-map.md)"
assert_contains "$readme_file" "[automation/context/metadata-index.generated.json](automation/context/metadata-index.generated.json)"
assert_contains "$readme_file" "[docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md)"
assert_contains "$readme_file" "[docs/agent/review.md](docs/agent/review.md)"
assert_contains "$readme_file" "[env/README.md](env/README.md)"
assert_contains "$readme_file" "[.agents/skills/README.md](.agents/skills/README.md)"
assert_contains "$readme_file" "[.codex/README.md](.codex/README.md)"
assert_contains "$readme_file" "[docs/exec-plans/README.md](docs/exec-plans/README.md)"
assert_contains "$readme_file" "[docs/template-maintenance.md](docs/template-maintenance.md)"
assert_contains "$readme_file" "local-only"
assert_contains "$readme_file" "remote-backed"
assert_contains "$project_map_file" "Ownership Model"
assert_contains "$project_map_file" "generated-derived"
assert_contains "$openspec_project_file" "generated 1С-проект"
assert_contains "$metadata_index_file" "\"inventoryRole\": \"generated-derived\""
assert_contains "$source_tree_file" "# Generated Project Tree"
assert_contains "$overlay_version_file" "$(git -C "$SOURCE_ROOT" describe --tags --always)"
assert_contains "$manifest_file" "scripts/template/update-template.sh"
assert_contains "$manifest_file" "docs/AGENTS.md"
assert_contains "$manifest_file" "src/AGENTS.md"
assert_contains "$docs_agents_file" "[docs/agent/generated-project-index.md](agent/generated-project-index.md)"
assert_contains "$docs_agents_file" "[docs/agent/index.md](agent/index.md)"
assert_contains "$src_agents_file" "[docs/agent/generated-project-index.md](../docs/agent/generated-project-index.md)"
assert_contains "$src_agents_file" "automation/context/project-map.md"
assert_contains "$src_agents_file" "automation/context/metadata-index.generated.json"

mkdir -p \
  "$project_root/src/cf/HTTPServices/Orders" \
  "$project_root/src/cf/WebServices/LegacySync" \
  "$project_root/src/cf/ScheduledJobs/SyncCatalog" \
  "$project_root/src/cf/CommonModules/Shared" \
  "$project_root/src/cf/Subsystems/Backoffice" \
  "$project_root/src/cfe/MainExtension" \
  "$project_root/src/epf/ImportWizard" \
  "$project_root/src/erf/RevenueReport" \
  "$project_root/env/.local" \
  "$project_root/.codex"

cat >"$project_root/src/cf/Configuration.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Configuration uuid="11111111-1111-1111-1111-111111111111">
    <Properties>
      <Name>SmokeConfiguration</Name>
    </Properties>
  </Configuration>
</MetaDataObject>
EOF

printf '{ "profileName": "local" }\n' >"$project_root/env/local.json"
printf '{ "profileName": "private" }\n' >"$project_root/env/.local/dev.json"
printf 'mcp = true\n' >"$project_root/.codex/local.override.toml"

(
  cd "$project_root"
  bash ./scripts/llm/export-context.sh --write >/dev/null
)

assert_contains "$metadata_index_file" '"name": "SmokeConfiguration"'
assert_contains "$metadata_index_file" '"uuid": "11111111-1111-1111-1111-111111111111"'
assert_contains "$metadata_index_file" '"entrypointInventory"'
assert_contains "$metadata_index_file" '"configurationRoots": ["src/cf", "src/cfe", "src/epf", "src/erf"]'
assert_contains "$metadata_index_file" '"httpServices": ["src/cf/HTTPServices/Orders"]'
assert_contains "$metadata_index_file" '"webServices": ["src/cf/WebServices/LegacySync"]'
assert_contains "$metadata_index_file" '"scheduledJobs": ["src/cf/ScheduledJobs/SyncCatalog"]'
assert_contains "$metadata_index_file" '"commonModules": ["src/cf/CommonModules/Shared"]'
assert_contains "$metadata_index_file" '"subsystems": ["src/cf/Subsystems/Backoffice"]'
assert_contains "$metadata_index_file" '"extensions": ["src/cfe/MainExtension"]'
assert_contains "$metadata_index_file" '"externalProcessors": ["src/epf/ImportWizard"]'
assert_contains "$metadata_index_file" '"reports": ["src/erf/RevenueReport"]'

if grep -Fq -- './env/local.json' "$source_tree_file"; then
  printf 'generated source tree leaked env/local.json\n' >&2
  exit 1
fi

if grep -Fq -- './env/.local/dev.json' "$source_tree_file"; then
  printf 'generated source tree leaked env/.local/dev.json\n' >&2
  exit 1
fi

if grep -Fq -- './.codex/local.override.toml' "$source_tree_file"; then
  printf 'generated source tree leaked .codex/local.override.toml\n' >&2
  exit 1
fi
