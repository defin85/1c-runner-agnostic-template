#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
LEGACY_REF="v0.3.37"
CURRENT_REF="v999.0.0"

tmpdir="$(mktemp -d)"
case "$tmpdir" in /tmp/tmp.*) ;; *) exit 2 ;; esac
trap 'rm -rf -- "$tmpdir"' EXIT

template_root="$tmpdir/template"
project_root="$tmpdir/project"

git clone -q --shared "$SOURCE_ROOT" "$template_root"
git -C "$template_root" checkout -q -b rollback-fixture "$LEGACY_REF"
git -C "$SOURCE_ROOT" diff --binary "$LEGACY_REF" -- . | git -C "$template_root" apply --index
git -C "$template_root" config user.name "Smoke Test"
git -C "$template_root" config user.email "smoke@example.com"
git -C "$template_root" commit -qm "current runtime fixture"
git -C "$template_root" tag "$CURRENT_REF"

copier copy --trust --defaults --vcs-ref "$LEGACY_REF" \
  -d project_name="Rollback Project" \
  -d project_slug="rollback-project" \
  -d init_git_repository=true \
  "$template_root" "$project_root" >"$tmpdir/copier.log" 2>&1

git -C "$project_root" config user.name "Smoke Test"
git -C "$project_root" config user.email "smoke@example.com"
git -C "$project_root" add -A
git -C "$project_root" commit -qm "generated from $LEGACY_REF"

cp "$project_root/env/local.example.json" "$project_root/env/.local/previous-profile.json"
previous_digest="$(sha256sum "$project_root/env/.local/previous-profile.json" | cut -d' ' -f1)"

(
  cd "$project_root"
  ./scripts/template/update-template.sh --vcs-ref "$CURRENT_REF" >"$tmpdir/update.log"
  ./scripts/template/migrate-runtime-profile-v3.sh --profile-only \
    env/.local/previous-profile.json >env/.local/migrated-profile.json
  ONEC_IBCMD_PASSWORD=fixture ./scripts/diag/doctor.sh --dry-run \
    --profile env/.local/migrated-profile.json \
    --run-root .artifacts/rollback-current-doctor >/dev/null
)

[ "$(tr -d '\r\n' < "$project_root/.template-overlay-version")" = "$CURRENT_REF" ]
[ "$(jq -r .schemaVersion "$project_root/env/local.example.json")" = "3" ]
[ "$(jq -r .schemaVersion "$project_root/env/.local/migrated-profile.json")" = "3" ]
[ "$previous_digest" = "$(sha256sum "$project_root/env/.local/previous-profile.json" | cut -d' ' -f1)" ]

git -C "$project_root" add -A
git -C "$project_root" commit -qm "updated to $CURRENT_REF"

(
  cd "$project_root"
  ./scripts/template/update-template.sh --vcs-ref "$LEGACY_REF" >"$tmpdir/rollback.log"
  ONEC_IBCMD_PASSWORD=fixture ./scripts/diag/doctor.sh --dry-run \
    --profile env/.local/previous-profile.json \
    --run-root .artifacts/rollback-previous-doctor >/dev/null
)

[ "$(tr -d '\r\n' < "$project_root/.template-overlay-version")" = "$LEGACY_REF" ]
[ "$(jq -r .schemaVersion "$project_root/env/.local/previous-profile.json")" = "2" ]
[ "$previous_digest" = "$(sha256sum "$project_root/env/.local/previous-profile.json" | cut -d' ' -f1)" ]
