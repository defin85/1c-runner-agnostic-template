#!/usr/bin/env bash
# Contract: check-skill-bindings fails on repository paths named in SKILL.md that do not exist,
# but tolerates paths of optional modules until the module is materialized.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

repo="$tmpdir/repo"
mkdir -p "$repo"
(
  cd "$SOURCE_ROOT"
  git ls-files -z --cached --others --exclude-standard -- scripts | tar --null -T - -cf -
) | (cd "$repo" && tar xf -)
git -C "$repo" init -q
printf 'env/local.json\n' >"$repo/.gitignore"

write_skill() {
  local name="$1"
  local body="$2"
  local dir
  for dir in .agents/skills .claude/skills; do
    mkdir -p "$repo/$dir/$name"
    printf '# Skills\n' >"$repo/$dir/README.md"
    printf -- '---\nname: %s\ndescription: Smoke skill\n---\n\n# %s\n\n%s\n' "$name" "$name" "$body" \
      >"$repo/$dir/$name/SKILL.md"
  done
}

remove_skill() {
  rm -rf "$repo/.agents/skills/$1" "$repo/.claude/skills/$1"
}

run_check() {
  local output="$1"
  set +e
  bash "$repo/scripts/qa/check-skill-bindings.sh" >"$output" 2>&1
  local rc=$?
  set -e
  return "$rc"
}

expect_pass() {
  local label="$1"
  local output="$tmpdir/$label.log"
  if ! run_check "$output"; then
    printf 'expected check-skill-bindings to pass (%s)\n' "$label" >&2
    cat "$output" >&2
    exit 1
  fi
}

expect_fail_with() {
  local label="$1"
  shift
  local output="$tmpdir/$label.log"
  if run_check "$output"; then
    printf 'expected check-skill-bindings to fail (%s)\n' "$label" >&2
    cat "$output" >&2
    exit 1
  fi
  local expected
  for expected in "$@"; do
    if ! grep -Fq -- "$expected" "$output"; then
      printf 'expected text not found (%s): %s\n' "$label" "$expected" >&2
      cat "$output" >&2
      exit 1
    fi
  done
}

# Baseline: existing repo script, glob and git-ignored operator-local profile are accepted.
write_skill smoke-ok 'Repo script: `./scripts/qa/check-skill-bindings.sh`

See `scripts/python/qa*.py` and pass `--profile env/local.json`.'
expect_pass baseline

# A missing repo script fails and names the skill and the path.
write_skill smoke-missing 'Repo script: `./scripts/diag/missing.sh`'
expect_fail_with missing-script "smoke-missing" "scripts/diag/missing.sh"
remove_skill smoke-missing

# A missing document referenced in the skill body fails too.
write_skill smoke-missing-doc 'Repo script: `./scripts/qa/check-skill-bindings.sh`

Read `docs/agent/missing-runbook.md` first.'
expect_fail_with missing-doc "smoke-missing-doc" "docs/agent/missing-runbook.md"
remove_skill smoke-missing-doc

# Paths of optional modules are not errors while the module is not materialized.
write_skill smoke-optional 'Repo script: `./scripts/qa/check-skill-bindings.sh`

If the module is enabled, use `migration/kd21/run-workbench.sh`, `infra/site/server/wrapper`
and `docs/infra/site/README.md`; test tooling lives in `src/cfe/YAxUnit/Configuration.xml`.'
expect_pass optional-not-materialized

# Once the module root exists, its paths are checked normally.
mkdir -p "$repo/migration/kd21"
expect_fail_with optional-materialized "smoke-optional" "migration/kd21/run-workbench.sh"
printf '#!/usr/bin/env bash\n' >"$repo/migration/kd21/run-workbench.sh"
expect_pass optional-materialized-complete

printf 'skill-bindings-paths smoke passed\n'
