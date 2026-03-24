#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
source "$SCRIPT_DIR/../lib/common.sh"
# shellcheck source=../template/lib-overlay.sh
source "$SCRIPT_DIR/../template/lib-overlay.sh"

template_src_path="${1:-}"
project_name="${2:-}"
project_slug="${3:-}"
project_description="${4:-}"
init_beads="${5:-yes}"

root="$(project_root)"
cd "$root"

[ -n "$template_src_path" ] || die "template source path is empty"

sync_overlay_manifests \
  "$template_src_path" \
  "$root" \
  "$(overlay_manifest_file "$root")" \
  "$(overlay_manifest_file "$template_src_path")"
bash "$root/scripts/bootstrap/overlay-post-apply.sh" \
  "$template_src_path" \
  "$project_name" \
  "$project_slug" \
  "$project_description" \
  "$init_beads"
write_overlay_version "$root" "$(bootstrap_template_ref_or_fallback "$root" "$template_src_path")"
