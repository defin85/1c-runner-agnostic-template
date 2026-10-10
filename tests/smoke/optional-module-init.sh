#!/usr/bin/env bash
# Contract: `make optional-module-init MODULE=<name>` materializes an optional module blueprint
# (automation/optional/<module>/files/) into project-owned paths of a generated project:
# - a failure in the middle of the copy leaves no copied path and no preserve-list change;
# - the first run copies the blueprint and registers the targets in template-update-preserve-paths.txt;
# - a repeated run fails without changes;
# - template-update refreshes the blueprint but leaves the materialized paths byte-identical,
#   even when the release ships files at those paths by mistake.
# The module content here is a neutral fixture: the real blueprints are filled by their own tasks.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

template_root="$tmpdir/template"
rendered_root="$tmpdir/rendered"
bindir="$tmpdir/bin"
command_log="$tmpdir/commands.log"
module="customer-site-operations"
blueprint_rel="automation/optional/$module"
preserve_rel="automation/context/template-update-preserve-paths.txt"
materialized=(infra/site/ docs/infra/site/ .agents/skills/site-smoke/ .claude/skills/site-smoke/)

mkdir -p "$template_root" "$bindir"

export GIT_AUTHOR_NAME="Smoke Test" GIT_AUTHOR_EMAIL="smoke@example.com"
export GIT_COMMITTER_NAME="Smoke Test" GIT_COMMITTER_EMAIL="smoke@example.com"

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

copy_template_repo() {
  (
    cd "$SOURCE_ROOT"
    git ls-files -z --cached --others --exclude-standard \
      | while IFS= read -r -d '' relpath; do
          [ -e "$relpath" ] && printf '%s\0' "$relpath"
        done \
      | tar --null -T - -cf -
  ) | (cd "$template_root" && tar xf -)
}

init_git_repo() {
  git -C "$1" init -q
  git -C "$1" config user.name "Smoke Test"
  git -C "$1" config user.email "smoke@example.com"
  git -C "$1" -c core.safecrlf=false add -A
  git -C "$1" commit -qm "$2"
}

assert_contains() {
  grep -Fq -- "$2" "$1" || { cat "$1" >&2; fail "expected text not found in $1: $2"; }
}

assert_not_exists() {
  [ ! -e "$1" ] || fail "path should not exist: $1"
}

# Output of `git status --porcelain` in the rendered project must equal the expected text.
assert_status() {
  local expected="$1" label="$2" actual
  actual="$(git -C "$rendered_root" status --porcelain --untracked-files=all)"
  [ "$actual" = "$expected" ] || { printf 'expected:\n%s\nactual:\n%s\n' "$expected" "$actual" >&2; fail "$label"; }
}

run_init() {
  (cd "$rendered_root" && make -s optional-module-init MODULE="$1")
}

checksum_materialized() {
  (
    cd "$rendered_root"
    find infra/site docs/infra/site .agents/skills/site-smoke .claude/skills/site-smoke -type f -print0 \
      | LC_ALL=C sort -z \
      | xargs -0 sha256sum
  )
}

write_blueprint() {
  local files="$template_root/$blueprint_rel/files"
  rm -rf "${template_root:?}/$blueprint_rel"
  mkdir -p "$files/infra/site/server" "$files/docs/infra/site" "$files/.agents/skills/site-smoke"
  printf 'Blueprint notes are not copied.\n' >"$template_root/$blueprint_rel/README.md"
  printf '# Site profiles v1\n' >"$files/infra/site/README.md"
  printf 'print("server wrapper v1")\n' >"$files/infra/site/server/wrapper.py"
  printf '# Site runbook v1\n' >"$files/docs/infra/site/README.md"
  printf -- '---\nname: site-smoke\ndescription: Smoke fixture skill.\n---\n\nRepo script: `./infra/site/server/wrapper.py`\n' \
    >"$files/.agents/skills/site-smoke/SKILL.md"
  # The fixture replaces the shipped blueprint, so its manifest entries replace the shipped ones too.
  local manifest="$template_root/automation/context/template-managed-paths.txt"
  grep -v -F -- "$blueprint_rel/" "$manifest" >"$manifest.tmp" || true
  (cd "$template_root" && find "$blueprint_rel" -type f | LC_ALL=C sort) >>"$manifest.tmp"
  mv "$manifest.tmp" "$manifest"
}

cat >"$bindir/openspec" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'openspec %s\n' "$*" >>"$COMMAND_LOG"
if [ "$1" = "init" ] && [ "$#" -eq 3 ] && [ "$2" = "--tools" ]; then
  mkdir -p openspec/changes openspec/specs
  printf '# OpenSpec Project\n' >openspec/project.md
  exit 0
fi
if [ "$1" = "validate" ] && [ "$2" = "--all" ]; then
  exit 0
fi
printf 'unexpected openspec args: %s\n' "$*" >&2
exit 1
EOF
chmod +x "$bindir/openspec"

copy_template_repo
write_blueprint
init_git_repo "$template_root" "template v0.1.0"
git -C "$template_root" tag v0.1.0

copier_log="$tmpdir/copier-copy.log"
PATH="$bindir:$PATH" COMMAND_LOG="$command_log" copier copy --trust --defaults \
  -d project_name="Optional Module Project" \
  -d project_slug="optional-module-project" \
  "$template_root" "$rendered_root" >"$copier_log" 2>&1 || { tail -n 40 "$copier_log" >&2; fail "copier copy failed"; }
git -C "$rendered_root" add -A
git -C "$rendered_root" diff --cached --quiet || git -C "$rendered_root" commit -qm "post-copy state"

# copier copy delivers the blueprint but does not materialize the module.
[ -f "$rendered_root/$blueprint_rel/files/infra/site/README.md" ] || fail "copier copy did not deliver the blueprint"
for target in "${materialized[@]}"; do
  assert_not_exists "$rendered_root/${target%/}"
done
cp "$rendered_root/$preserve_rel" "$tmpdir/preserve.before"

# Unknown module: clear error, no changes.
if run_init no-such-module >"$tmpdir/unknown.txt" 2>&1; then
  fail "unknown module must fail"
fi
assert_contains "$tmpdir/unknown.txt" "unknown optional module: no-such-module"
assert_status "" "unknown module must not change the project"

# A copy error in the middle (docs/infra is a file, so docs/infra/site cannot be created after
# infra/site/ is already in place) removes everything copied in this run.
printf 'project file\n' >"$rendered_root/docs/infra"
if run_init "$module" >"$tmpdir/mid-failure.txt" 2>&1; then
  fail "initialization must fail when a target cannot be created"
fi
assert_status "?? docs/infra" "failed initialization must leave only the pre-existing project file"
for target in "${materialized[@]}"; do
  assert_not_exists "$rendered_root/${target%/}"
done
cmp -s "$tmpdir/preserve.before" "$rendered_root/$preserve_rel" || fail "failed initialization changed the preserve list"
rm -f "$rendered_root/docs/infra"

# First initialization.
run_init "$module" >"$tmpdir/first.txt"
assert_contains "$tmpdir/first.txt" "materialized $module"
assert_contains "$rendered_root/infra/site/server/wrapper.py" 'server wrapper v1'
assert_contains "$rendered_root/docs/infra/site/README.md" '# Site runbook v1'
cmp -s "$rendered_root/.agents/skills/site-smoke/SKILL.md" "$rendered_root/.claude/skills/site-smoke/SKILL.md" \
  || fail "skill mirror differs from the materialized skill"
for target in "${materialized[@]}"; do
  grep -Fqx -- "$target" "$rendered_root/$preserve_rel" || fail "$target is not registered in $preserve_rel"
done
[ -z "$(find "$rendered_root" -maxdepth 1 -name '.optional-module-init.*')" ] || fail "staging directory left behind"
git -C "$rendered_root" add -A
git -C "$rendered_root" commit -qm "materialize $module"

# The project adapts its copy.
printf 'project-specific profile\n' >>"$rendered_root/infra/site/README.md"
git -C "$rendered_root" commit -qam "adapt site profiles"
checksum_materialized >"$tmpdir/materialized.before"

# Repeated initialization fails without changes.
if run_init "$module" >"$tmpdir/repeat.txt" 2>&1; then
  fail "repeated initialization must fail"
fi
assert_contains "$tmpdir/repeat.txt" "target paths already exist"
assert_status "" "repeated initialization must not change the project"

# Template v0.2.0 changes the blueprint and, by mistake, ships files at materialized paths.
printf '# Site profiles v2\n' >"$template_root/$blueprint_rel/files/infra/site/README.md"
mkdir -p "$template_root/infra/site" "$template_root/.agents/skills/site-smoke"
printf 'template-release-must-not-win\n' >"$template_root/infra/site/README.md"
printf 'template-release-must-not-win\n' >"$template_root/.agents/skills/site-smoke/SKILL.md"
printf '%s\n' infra/site/README.md .agents/skills/site-smoke/SKILL.md \
  >>"$template_root/automation/context/template-managed-paths.txt"
git -C "$template_root" add -A
git -C "$template_root" commit -qm "template v0.2.0"
git -C "$template_root" tag v0.2.0

update_output="$tmpdir/template-update.txt"
(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make template-update >"$update_output" 2>&1
) || { tail -n 40 "$update_output" >&2; fail "template-update failed"; }
assert_contains "$update_output" "Target overlay release: v0.2.0"

checksum_materialized >"$tmpdir/materialized.after"
if ! cmp -s "$tmpdir/materialized.before" "$tmpdir/materialized.after"; then
  diff "$tmpdir/materialized.before" "$tmpdir/materialized.after" >&2 || true
  fail "template-update changed materialized module paths"
fi
assert_contains "$rendered_root/$blueprint_rel/files/infra/site/README.md" '# Site profiles v2'

printf 'optional-module-init smoke passed\n'
