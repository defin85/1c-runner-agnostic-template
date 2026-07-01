#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# shellcheck source=../../scripts/lib/runtime-profile.sh
source "$PROJECT_ROOT/scripts/lib/runtime-profile.sh"

COMMAND="${1:-}"
PROFILE_INPUT="${GOLDEN_BASELINE_PROFILE:-${ONEC_PROFILE:-}}"
TARGET_INPUT="${GOLDEN_BASELINE_TARGET:-}"
SNAPSHOT_INPUT="${GOLDEN_BASELINE_SNAPSHOT:-}"

usage() {
  cat <<'EOF'
Usage:
  tests/golden/create.sh --profile <file> [--target <id>] [--snapshot <file>]
  tests/golden/restore.sh --profile <file> [--target <id>] [--snapshot <file>]

Creates/restores a PostgreSQL golden snapshot for the profile infobase.
Default snapshot: .artifacts/golden/<target>.dump
EOF
}

valid_pg_identifier() {
  case "$1" in
    [A-Za-z_][A-Za-z0-9_]*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

pg_conninfo_server() {
  local server="$1"
  local first_word="${server%% *}"

  case "$first_word" in
    *=*)
      printf '%s\n' "$server"
      ;;
    *)
      printf 'host=%s\n' "$server"
      ;;
  esac
}

parse_args() {
  [ -n "$COMMAND" ] || {
    usage
    exit 2
  }
  shift || true

  case "$COMMAND" in
    create|restore)
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unsupported golden command: $COMMAND"
      ;;
  esac

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --profile)
        [ "$#" -ge 2 ] || die "--profile requires a value"
        PROFILE_INPUT="$2"
        shift 2
        ;;
      --target)
        [ "$#" -ge 2 ] || die "--target requires a value"
        TARGET_INPUT="$2"
        shift 2
        ;;
      --snapshot)
        [ "$#" -ge 2 ] || die "--snapshot requires a value"
        SNAPSHOT_INPUT="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
  done
}

parse_args "$@"
require_command jq
require_command pg_dump
require_command pg_restore
require_command psql

PROFILE_PATH="$(resolve_runtime_profile_path "$PROFILE_INPUT" "$PROJECT_ROOT")"
[ -n "$PROFILE_PATH" ] || die "golden-baseline requires --profile <file>, ONEC_PROFILE, or env/local.json"
load_runtime_profile "$PROFILE_PATH"
require_runtime_profile_loaded

PROFILE_TARGET="$(profile_string '.target.id // empty')"
if [ -z "$TARGET_INPUT" ]; then
  TARGET_INPUT="$PROFILE_TARGET"
fi
[ -n "$TARGET_INPUT" ] || die "golden-baseline requires --target <id> or profile target.id"
[ -z "$PROFILE_TARGET" ] || [ "$PROFILE_TARGET" = "$TARGET_INPUT" ] || die "profile target.id '$PROFILE_TARGET' does not match --target '$TARGET_INPUT'"

KIND="$(require_profile_string '.ibcmd.dbmsInfobase.kind // empty' 'ibcmd.dbmsInfobase.kind')"
[ "$KIND" = "PostgreSQL" ] || die "golden-baseline supports only PostgreSQL dbmsInfobase, got: $KIND"

DB_SERVER="$(require_profile_string '.ibcmd.dbmsInfobase.server // empty' 'ibcmd.dbmsInfobase.server')"
DB_NAME="$(require_profile_string '.ibcmd.dbmsInfobase.name // empty' 'ibcmd.dbmsInfobase.name')"
DB_USER="$(require_profile_string '.ibcmd.dbmsInfobase.user // empty' 'ibcmd.dbmsInfobase.user')"
DB_PASSWORD_ENV="$(require_profile_string '.ibcmd.dbmsInfobase.passwordEnv // empty' 'ibcmd.dbmsInfobase.passwordEnv')"
require_env "$DB_PASSWORD_ENV"

valid_pg_identifier "$DB_NAME" || die "unsafe PostgreSQL database name for golden restore: $DB_NAME"
valid_pg_identifier "$DB_USER" || die "unsafe PostgreSQL user name for golden restore: $DB_USER"

if [ -z "$SNAPSHOT_INPUT" ]; then
  SNAPSHOT_INPUT="$PROJECT_ROOT/.artifacts/golden/$TARGET_INPUT.dump"
fi
SNAPSHOT_PATH="$(canonical_path "$SNAPSHOT_INPUT")"
ensure_dir "$(dirname -- "$SNAPSHOT_PATH")"

export PGPASSWORD="${!DB_PASSWORD_ENV}"
DB_SERVER_CONNINFO="$(pg_conninfo_server "$DB_SERVER")"
DB_CONNINFO="$DB_SERVER_CONNINFO dbname=$DB_NAME user=$DB_USER"
ADMIN_CONNINFO="$DB_SERVER_CONNINFO dbname=postgres user=$DB_USER"

case "$COMMAND" in
  create)
    pg_dump --format=custom --file="$SNAPSHOT_PATH" "$DB_CONNINFO"
    printf 'golden snapshot created: %s\n' "$SNAPSHOT_PATH"
    ;;
  restore)
    [ -f "$SNAPSHOT_PATH" ] || die "golden snapshot not found: $SNAPSHOT_PATH"
    psql "$ADMIN_CONNINFO" -v ON_ERROR_STOP=1 \
      -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" \
      -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" \
      -c "CREATE DATABASE \"$DB_NAME\" WITH OWNER \"$DB_USER\" TEMPLATE template0;"
    pg_restore --no-owner --dbname="$DB_CONNINFO" "$SNAPSHOT_PATH"
    printf 'golden snapshot restored: %s -> %s\n' "$SNAPSHOT_PATH" "$DB_NAME"
    ;;
esac
