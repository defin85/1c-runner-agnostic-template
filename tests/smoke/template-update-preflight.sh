#!/usr/bin/env bash
# Contract (R22): template-update checks the project target matrix before it leaves project files changed,
# and the release creates missing seed-once files. The first update from v0.3.36 runs the previous
# update-template.sh of the project (frozen in tests/fixtures/legacy-update-template), which applies the
# overlay itself and only then calls overlay-post-apply.sh of the release:
# - a matrix extension without src/cfe/<name> stops that update and the project work tree stays clean;
# - with the matrix fixed the same update passes and creates ruff.toml with the extend line;
# - the current update-template.sh refuses a broken matrix before it applies the overlay.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

template_root="$tmpdir/template"
project_root="$tmpdir/project"
bindir="$tmpdir/bin"
command_log="$tmpdir/commands.log"
legacy_dir="$SOURCE_ROOT/tests/fixtures/legacy-update-template"
missing_name="NeutralExtension"

mkdir -p "$template_root" "$bindir"

export GIT_AUTHOR_NAME="Smoke Test" GIT_AUTHOR_EMAIL="smoke@example.com"
export GIT_COMMITTER_NAME="Smoke Test" GIT_COMMITTER_EMAIL="smoke@example.com"

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

assert_contains() {
  grep -Fq -- "$2" "$1" || { cat "$1" >&2; fail "expected text not found in $1: $2"; }
}

assert_clean() {
  local status
  status="$(git -C "$project_root" status --porcelain)"
  [ -z "$status" ] || { printf '%s\n' "$status" >&2; fail "project work tree is not clean: $1"; }
}

commit_project() {
  git -C "$project_root" add -A
  git -C "$project_root" commit -qm "$1"
}

release_template() {
  printf '# template %s\n' "$1" >>"$template_root/Makefile"
  git -C "$template_root" add -A
  git -C "$template_root" commit -qm "template $1"
  git -C "$template_root" tag "$1"
}

write_matrix() {
  local names="$1"
  cat >"$project_root/automation/context/target-matrix.json" <<EOF
{
  "schemaVersion": 1,
  "targets": [{"id": "main", "sourcePath": "src/cf/main"}],
  "extensionMatrix": {"main": [$names]}
}
EOF
}

cat >"$bindir/openspec" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'openspec %s\n' "$*" >>"$COMMAND_LOG"
if [ "$1" = "init" ]; then
  mkdir -p openspec/changes openspec/specs
  printf '# OpenSpec Project\n' >openspec/project.md
fi
exit 0
EOF
chmod +x "$bindir/openspec"
export PATH="$bindir:$PATH" COMMAND_LOG="$command_log"

(
  cd "$SOURCE_ROOT"
  git ls-files -z --cached --others --exclude-standard \
    | while IFS= read -r -d '' relpath; do
        [ -e "$relpath" ] && printf '%s\0' "$relpath"
      done \
    | tar --null -T - -cf -
) | (cd "$template_root" && tar xf -)
git -C "$template_root" init -q
git -C "$template_root" -c core.safecrlf=false add -A
git -C "$template_root" commit -qm "template v0.1.0"
git -C "$template_root" tag v0.1.0

copier copy --trust --defaults -d project_name="Preflight Project" -d project_slug="preflight-project" \
  "$template_root" "$project_root" >"$tmpdir/copier.log" 2>&1 || { tail -n 40 "$tmpdir/copier.log" >&2; fail "copier copy failed"; }

# The project looks like one at v0.3.36: the previous update scripts, no ruff.toml, a matrix whose
# extension lives outside src/cfe/.
cp "$legacy_dir/update-template.sh" "$project_root/scripts/template/update-template.sh"
cp "$legacy_dir/lib-overlay.sh" "$project_root/scripts/template/lib-overlay.sh"
rm -f "$project_root/ruff.toml"
mkdir -p "$project_root/src/cf/main" "$project_root/src/cfe/_templates/$missing_name"
printf '<MetaDataObject/>\n' >"$project_root/src/cf/main/Configuration.xml"
printf '<MetaDataObject/>\n' >"$project_root/src/cfe/_templates/$missing_name/Configuration.xml"
write_matrix "\"$missing_name\""
commit_project "project at the previous release"
release_template v0.2.0

# 1. The previous script applies the overlay; the release post-apply step stops and restores HEAD.
legacy_output="$tmpdir/legacy-broken.txt"
if (cd "$project_root" && ./scripts/template/update-template.sh --vcs-ref v0.2.0 >"$legacy_output" 2>&1); then
  cat "$legacy_output" >&2
  fail "update with a missing matrix extension must fail"
fi
assert_contains "$legacy_output" "target matrix extension not found under src/cfe: $missing_name"
assert_contains "$legacy_output" "restored to HEAD"
assert_contains "$legacy_output" "docs/migrations/project-toolkit-update.md"
assert_contains "$legacy_output" "step 6"
assert_clean "after the refused legacy update"
[ "$(cat "$project_root/.template-overlay-version")" = "v0.1.0" ] || fail "overlay version changed after refusal"
[ ! -e "$project_root/ruff.toml" ] || fail "ruff.toml must not appear after refusal"
cmp -s "$legacy_dir/update-template.sh" "$project_root/scripts/template/update-template.sh" \
  || fail "the previous update-template.sh must stay after refusal"

# 2. With the extension in src/cfe/ the same previous script finishes and the release seeds ruff.toml.
mkdir -p "$project_root/src/cfe/$missing_name"
cp "$project_root/src/cfe/_templates/$missing_name/Configuration.xml" "$project_root/src/cfe/$missing_name/"
commit_project "move the extension into src/cfe"
fixed_output="$tmpdir/legacy-fixed.txt"
(cd "$project_root" && ./scripts/template/update-template.sh --vcs-ref v0.2.0 >"$fixed_output" 2>&1) \
  || { cat "$fixed_output" >&2; fail "update with a fixed matrix failed"; }
assert_contains "$project_root/ruff.toml" 'extend = "scripts/qa/ruff-base.toml"'
[ "$(cat "$project_root/.template-overlay-version")" = "v0.2.0" ] || fail "overlay version was not updated"
assert_contains "$project_root/Makefile" "# template v0.2.0"
cmp -s "$SOURCE_ROOT/scripts/template/update-template.sh" "$project_root/scripts/template/update-template.sh" \
  || fail "the update must deliver the current update-template.sh"
commit_project "template v0.2.0"

# 3. The current script refuses a broken matrix before the overlay: nothing to restore.
write_matrix "\"$missing_name\", \"OtherMissingExtension\""
commit_project "matrix names a missing extension"
release_template v0.3.0
current_output="$tmpdir/current-broken.txt"
if (cd "$project_root" && ./scripts/template/update-template.sh --vcs-ref v0.3.0 >"$current_output" 2>&1); then
  cat "$current_output" >&2
  fail "the current update-template.sh must refuse a missing matrix extension"
fi
assert_contains "$current_output" "target matrix extension not found under src/cfe: OtherMissingExtension"
assert_contains "$current_output" "step 6"
if grep -Fq "restored to HEAD" "$current_output"; then
  fail "the current update-template.sh must stop before it applies the overlay"
fi
assert_clean "after the refused current update"
[ "$(cat "$project_root/.template-overlay-version")" = "v0.2.0" ] || fail "overlay version changed after refusal"

printf 'template-update-preflight smoke passed\n'
