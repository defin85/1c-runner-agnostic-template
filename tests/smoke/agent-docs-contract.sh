#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

copy_repo() {
  local target="$1"
  mkdir -p "$target"
  (
    cd "$SOURCE_ROOT"
    tar --exclude=.git -cf - .
  ) | (
    cd "$target"
    tar xf -
  )
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
  printf 'ci noise\n' > docs/.ci-noise.tmp
  ./scripts/qa/check-agent-docs.sh >/dev/null
)

missing_link_root="$tmpdir/missing-link"
copy_repo "$missing_link_root"
sed -i 's#\[docs/agent/architecture.md\](docs/agent/architecture.md)#docs/agent/architecture.md#' \
  "$missing_link_root/AGENTS.md"
assert_fails_with "$missing_link_root" "missing required markdown link in AGENTS.md: docs/agent/architecture.md"

broken_link_root="$tmpdir/broken-link"
copy_repo "$broken_link_root"
sed -i 's#(../../openspec/project.md)#(../../openspec/missing-project.md)#' \
  "$broken_link_root/docs/agent/architecture.md"
assert_fails_with "$broken_link_root" "broken markdown link in docs/agent/architecture.md:"

generated_template_root="$tmpdir/generated-template"
generated_root="$tmpdir/generated"
generated_bindir="$tmpdir/generated-bin"
render_generated_repo "$generated_template_root" "$generated_root" "$generated_bindir"
(
  cd "$generated_root"
  PATH="$generated_bindir:$PATH" ./scripts/qa/check-agent-docs.sh >/dev/null
)

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

generated_missing_overlay_version_root="$tmpdir/generated-missing-overlay-version"
cp -R "$generated_root" "$generated_missing_overlay_version_root"
rm -f "$generated_missing_overlay_version_root/.template-overlay-version"
assert_fails_with "$generated_missing_overlay_version_root" \
  "missing agent-facing path: .template-overlay-version" \
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

generated_local_private_leak_root="$tmpdir/generated-local-private-leak"
cp -R "$generated_root" "$generated_local_private_leak_root"
printf './env/local.json\n' >>"$generated_local_private_leak_root/automation/context/source-tree.generated.txt"
assert_fails_with "$generated_local_private_leak_root" \
  "local-private path leaked into generated context: env/local.json" \
  "$generated_bindir"

generated_empty_identity_root="$tmpdir/generated-empty-identity"
cp -R "$generated_root" "$generated_empty_identity_root"
mkdir -p "$generated_empty_identity_root/src/cf"
cat >"$generated_empty_identity_root/src/cf/Configuration.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject name="GeneratedCfg">
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
