#!/usr/bin/env bash
# Contract: project-owned extension points survive template-update and stay wired:
# Makefile.project / make.project.ps1, scripts/qa/agent-verify.d/, the project-owned
# block in .gitignore, .gitattributes and .contextignore, and the seed-once Python environment
# (pyproject.toml, uv.lock, requirements-dev.txt, pyrightconfig.json, ruff.toml): copier copy delivers it,
# template-update seeds only missing files and never overwrites project dependencies or roots.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

template_root="$tmpdir/template"
rendered_root="$tmpdir/rendered"
bindir="$tmpdir/bin"
command_log="$tmpdir/commands.log"
step_log="$tmpdir/project-steps.log"
block_begin="# >>> project-owned block: template-update keeps the lines up to the closing marker >>>"
block_end="# <<< project-owned block <<<"

mkdir -p "$template_root" "$bindir"

# copier post-copy commits in the rendered repo; do not depend on a global git identity.
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

# The line must sit strictly between the project-owned block markers.
assert_in_block() {
  local file="$1" expected="$2" begin line end
  begin="$(grep -nxF -- "$block_begin" "$file" | cut -d: -f1)"
  end="$(grep -nxF -- "$block_end" "$file" | cut -d: -f1)"
  line="$(grep -nxF -- "$expected" "$file" | head -n 1 | cut -d: -f1)"
  if [ -z "$begin" ] || [ -z "$end" ] || [ -z "$line" ] || [ "$line" -le "$begin" ] || [ "$line" -ge "$end" ]; then
    cat "$file" >&2
    fail "expected '$expected' inside the project-owned block of $file"
  fi
}

project_owned_paths=(
  Makefile.project
  make.project.ps1
  scripts/project/hello.ps1
  scripts/qa/agent-verify.d/README.md
  scripts/qa/agent-verify.d/10-project-step.sh
  scripts/qa/agent-verify.d/20-project-step.py
  scripts/qa/agent-verify.d/30-windows-step.ps1
  pyproject.toml
  uv.lock
  requirements-dev.txt
  pyrightconfig.json
  ruff.toml
  project_tools/greeting.py
)
python_seed_paths=(pyproject.toml uv.lock requirements-dev.txt pyrightconfig.json ruff.toml)

checksum_project_owned() {
  (cd "$rendered_root" && sha256sum "${project_owned_paths[@]}")
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
init_git_repo "$template_root" "template v0.1.0"
git -C "$template_root" tag v0.1.0

copier_log="$tmpdir/copier-copy.log"
PATH="$bindir:$PATH" COMMAND_LOG="$command_log" copier copy --trust --defaults \
  -d project_name="Extension Points Project" \
  -d project_slug="extension-points-project" \
  "$template_root" "$rendered_root" >"$copier_log" 2>&1 || { tail -n 40 "$copier_log" >&2; fail "copier copy failed"; }

# The template ships the empty block and none of the project-owned files.
for file in .gitignore .gitattributes .contextignore; do
  assert_contains "$rendered_root/$file" "$block_begin"
  assert_contains "$rendered_root/$file" "$block_end"
done
assert_not_exists "$rendered_root/Makefile.project"
assert_not_exists "$rendered_root/make.project.ps1"
assert_not_exists "$rendered_root/scripts/qa/agent-verify.d"
assert_contains "$rendered_root/automation/context/template-update-preserve-paths.txt" "Makefile.project"
assert_contains "$rendered_root/automation/context/template-update-preserve-paths.txt" "scripts/qa/agent-verify.d/"
# The seed-once Python environment arrives with copier copy and is project-owned, not overlay-managed.
for relpath in "${python_seed_paths[@]}"; do
  [ -f "$rendered_root/$relpath" ] || fail "copier copy did not deliver $relpath"
  grep -Fqx -- "$relpath" "$rendered_root/automation/context/template-update-preserve-paths.txt" \
    || fail "$relpath must be listed in template-update-preserve-paths.txt"
  if grep -Fqx -- "$relpath" "$rendered_root/automation/context/template-managed-paths.txt"; then
    fail "$relpath must not be template-managed"
  fi
done
assert_contains "$rendered_root/pyrightconfig.json" '"extends": "scripts/qa/pyright-base.json"'
assert_contains "$rendered_root/ruff.toml" 'extend = "scripts/qa/ruff-base.toml"'

# Fill the extension points the way a generated project would.
cat >"$rendered_root/Makefile.project" <<'EOF'
.PHONY: project-hello

project-hello:
	@printf 'project target ok\n'
EOF
cat >"$rendered_root/make.project.ps1" <<'EOF'
$projectTargets["project-hello"] = @((Join-Path $root "scripts\project\hello.ps1"))
$projectHelp += "  ./make.ps1 project-hello"
EOF
mkdir -p "$rendered_root/scripts/project" "$rendered_root/scripts/qa/agent-verify.d"
cat >"$rendered_root/scripts/project/hello.ps1" <<'EOF'
Write-Output "project target ok"
EOF
cat >"$rendered_root/scripts/qa/agent-verify.d/README.md" <<'EOF'
Project-owned agent-verify steps.
EOF
cat >"$rendered_root/scripts/qa/agent-verify.d/10-project-step.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'sh step\n' >>"$PROJECT_STEP_LOG"
EOF
cat >"$rendered_root/scripts/qa/agent-verify.d/20-project-step.py" <<'EOF'
import os

with open(os.environ["PROJECT_STEP_LOG"], "a", encoding="utf-8") as stream:
    stream.write("py step\n")
EOF
cat >"$rendered_root/scripts/qa/agent-verify.d/30-windows-step.ps1" <<'EOF'
Add-Content -Path $env:PROJECT_STEP_LOG -Value "ps1 step"
EOF

add_to_block() {
  local file="$1" line="$2"
  python3 - "$file" "$line" "$block_end" <<'PY'
import sys
from pathlib import Path

path, line, end = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
text = path.read_text(encoding="utf-8")
if text.count(end + "\n") != 1:
    raise SystemExit(f"closing marker not found in {path}")
path.write_text(text.replace(end + "\n", f"{line}\n{end}\n"), encoding="utf-8")
PY
}
add_to_block "$rendered_root/.gitignore" "project-local-cache/"
add_to_block "$rendered_root/.gitattributes" "*.project-bin binary"
add_to_block "$rendered_root/.contextignore" "project-dump/**"

# The project adds its own dependency (already in the uv cache, so no network is needed) and its own
# type-check root, then refreshes the derived requirements export.
(
  cd "$rendered_root"
  uv add --dev --offline --no-sync "pyyaml>=6" >/dev/null 2>&1 || uv add --dev --no-sync "pyyaml>=6" >/dev/null
  uv export --locked --format requirements-txt --no-hashes --no-emit-project --no-annotate \
    --output-file requirements-dev.txt >/dev/null
)
assert_contains "$rendered_root/pyproject.toml" '"pyyaml>=6"'
mkdir -p "$rendered_root/project_tools"
printf 'def greeting(name: str) -> str:\n    return f"hello {name}"\n' >"$rendered_root/project_tools/greeting.py"
python3 - "$rendered_root/pyrightconfig.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
config = json.loads(path.read_text(encoding="utf-8"))
config["include"].append("project_tools")
path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
printf 'extend-exclude = ["project_tools/generated"]\n' >>"$rendered_root/ruff.toml"

git -C "$rendered_root" add -A
git -C "$rendered_root" commit -qm "fill project-owned extension points"
checksum_project_owned >"$tmpdir/project-owned.before"

# Template v0.2.0 changes the template part of the files and, by mistake, ships project-owned paths.
sed -i '1i template-v2-cache/' "$template_root/.gitignore"
sed -i '1i *.template-v2 text eol=lf' "$template_root/.gitattributes"
printf '# template v0.2.0\n' >>"$template_root/Makefile"
printf 'template-release-must-not-win:\n\t@false\n' >"$template_root/Makefile.project"
mkdir -p "$template_root/scripts/qa/agent-verify.d"
printf '#!/usr/bin/env bash\nexit 99\n' >"$template_root/scripts/qa/agent-verify.d/10-project-step.sh"
# The release also changes its own seed-once Python files and lists them as managed by mistake.
printf '# template v0.2.0\n' >>"$template_root/pyproject.toml"
printf '# template v0.2.0\n' >>"$template_root/uv.lock"
printf '# template v0.2.0\n' >>"$template_root/requirements-dev.txt"
printf '# template v0.2.0\n' >>"$template_root/ruff.toml"
python3 - "$template_root/pyrightconfig.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
config = json.loads(path.read_text(encoding="utf-8"))
config["include"] = ["scripts"]
path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
printf '%s\n' Makefile.project scripts/qa/agent-verify.d/10-project-step.sh "${python_seed_paths[@]}" \
  >>"$template_root/automation/context/template-managed-paths.txt"
git -C "$template_root" add -A
git -C "$template_root" commit -qm "template v0.2.0"
git -C "$template_root" tag v0.2.0

update_output="$tmpdir/template-update.txt"
(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" make template-update >"$update_output"
)
assert_contains "$update_output" "Target overlay release: v0.2.0"

checksum_project_owned >"$tmpdir/project-owned.after"
if ! cmp -s "$tmpdir/project-owned.before" "$tmpdir/project-owned.after"; then
  diff "$tmpdir/project-owned.before" "$tmpdir/project-owned.after" >&2 || true
  fail "template-update changed project-owned extension files"
fi
assert_contains "$rendered_root/Makefile" "# template v0.2.0"
assert_contains "$rendered_root/pyproject.toml" '"pyyaml>=6"'
assert_contains "$rendered_root/pyrightconfig.json" '"project_tools"'
assert_contains "$rendered_root/ruff.toml" 'project_tools/generated'
assert_contains "$rendered_root/.gitignore" "template-v2-cache/"
assert_contains "$rendered_root/.gitattributes" "*.template-v2 text eol=lf"
assert_in_block "$rendered_root/.gitignore" "project-local-cache/"
assert_in_block "$rendered_root/.gitattributes" "*.project-bin binary"
assert_in_block "$rendered_root/.contextignore" "project-dump/**"

# The project target is reachable through the template Makefile.
hello_output="$tmpdir/project-hello.txt"
(cd "$rendered_root" && make -s project-hello >"$hello_output")
assert_contains "$hello_output" "project target ok"
(cd "$rendered_root" && make -s help >"$tmpdir/help.txt")
assert_contains "$tmpdir/help.txt" "Makefile.project"

if command -v pwsh >/dev/null 2>&1; then
  (cd "$rendered_root" && pwsh -NoProfile -File ./make.ps1 project-hello >"$tmpdir/pwsh-hello.txt")
  assert_contains "$tmpdir/pwsh-hello.txt" "project target ok"
else
  printf 'pwsh not found; skipping make.ps1 project target check\n'
fi

# agent-verify runs the project steps after the baseline; .sh and .py run on POSIX, .ps1 is skipped.
verify_output="$tmpdir/agent-verify.txt"
(
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" PROJECT_STEP_LOG="$step_log" make agent-verify >"$verify_output" 2>&1
) || { cat "$verify_output" >&2; fail "agent-verify failed in the generated project"; }
printf 'sh step\npy step\n' >"$tmpdir/expected-steps.log"
cmp -s "$tmpdir/expected-steps.log" "$step_log" || { cat "$step_log" >&2; fail "unexpected project step log"; }
assert_contains "$verify_output" "Skip project agent-verify step for another platform: scripts/qa/agent-verify.d/30-windows-step.ps1"

# A failing project step fails agent-verify and names the step.
printf 'raise SystemExit(3)\n' >"$rendered_root/scripts/qa/agent-verify.d/40-failing-step.py"
(cd "$rendered_root" && make -s export-context-write >/dev/null)
failing_output="$tmpdir/agent-verify-failing.txt"
if (
  cd "$rendered_root"
  PATH="$bindir:$PATH" COMMAND_LOG="$command_log" PROJECT_STEP_LOG="$step_log" make agent-verify >"$failing_output" 2>&1
); then
  fail "agent-verify must fail when a project step fails"
fi
assert_contains "$failing_output" "project agent-verify step failed with exit code 3: scripts/qa/agent-verify.d/40-failing-step.py"
rm -f "$rendered_root/scripts/qa/agent-verify.d/40-failing-step.py"

# The Python overlay sync (Windows template-update path) follows the same contract.
python_fixture="$tmpdir/python-sync"
mkdir -p "$python_fixture/source/scripts/qa/agent-verify.d" "$python_fixture/target"
printf 'template-line\n%s\n%s\n' "$block_begin" "$block_end" >"$python_fixture/source/.gitignore"
printf 'template\n' >"$python_fixture/source/Makefile.project"
printf 'template\n' >"$python_fixture/source/scripts/qa/agent-verify.d/10-step.py"
printf '.gitignore\nMakefile.project\nscripts/qa/agent-verify.d/10-step.py\n' >"$python_fixture/next.txt"
printf 'Makefile.project\nscripts/qa/agent-verify.d/\n' >"$python_fixture/preserve.txt"
printf 'old-template-line\n%s\nproject-line\n%s\n' "$block_begin" "$block_end" >"$python_fixture/target/.gitignore"
printf 'project\n' >"$python_fixture/target/Makefile.project"
(
  cd "$SOURCE_ROOT"
  python3 - "$python_fixture" <<'PY'
import sys
from pathlib import Path

from scripts.python.template_tools import sync_overlay_manifests

root = Path(sys.argv[1])
sync_overlay_manifests(root / "source", root / "target", root / "missing.txt", root / "next.txt", root / "preserve.txt")
PY
)
assert_contains "$python_fixture/target/.gitignore" "template-line"
assert_in_block "$python_fixture/target/.gitignore" "project-line"
assert_contains "$python_fixture/target/Makefile.project" "project"
assert_not_exists "$python_fixture/target/scripts/qa/agent-verify.d/10-step.py"

# Projects created before the seed-once Python environment existed receive the missing files on
# template-update; files the project already has are never replaced. Both update paths are checked.
for flavour in shell python; do
  seed_fixture="$tmpdir/seed-$flavour"
  mkdir -p "$seed_fixture/source" "$seed_fixture/target"
  for relpath in "${python_seed_paths[@]}"; do
    printf 'template %s\n' "$relpath" >"$seed_fixture/source/$relpath"
  done
  printf 'project pyproject\n' >"$seed_fixture/target/pyproject.toml"
  if [ "$flavour" = "shell" ]; then
    (
      # shellcheck source=../../scripts/template/lib-overlay.sh
      source "$SOURCE_ROOT/scripts/template/lib-overlay.sh"
      seed_missing_project_files "$seed_fixture/source" "$seed_fixture/target"
    )
  else
    (
      cd "$SOURCE_ROOT"
      python3 - "$seed_fixture" <<'PY'
import sys
from pathlib import Path

from scripts.python.project_extensions import seed_missing_project_files

root = Path(sys.argv[1])
seeded = seed_missing_project_files(root / "source", root / "target")
assert seeded == ["uv.lock", "requirements-dev.txt", "pyrightconfig.json", "ruff.toml"], seeded
PY
    )
  fi
  assert_contains "$seed_fixture/target/pyproject.toml" "project pyproject"
  for relpath in uv.lock requirements-dev.txt pyrightconfig.json ruff.toml; do
    assert_contains "$seed_fixture/target/$relpath" "template $relpath"
  done
done

printf 'project-extension-points smoke passed\n'
