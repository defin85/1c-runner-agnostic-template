#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

assert_exists() {
  local path="$1"

  if [ ! -e "$path" ]; then
    printf 'path does not exist: %s\n' "$path" >&2
    exit 1
  fi
}

assert_not_exists() {
  local path="$1"

  if [ -e "$path" ]; then
    printf 'path should not exist: %s\n' "$path" >&2
    exit 1
  fi
}

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected text not found: %s\n' "$expected" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_exists "$SOURCE_ROOT/scripts/test/run-xunit-direct-platform.sh"
assert_exists "$SOURCE_ROOT/scripts/test/build-xunit-epf.sh"
assert_exists "$SOURCE_ROOT/scripts/test/tdd-xunit.sh"
assert_exists "$SOURCE_ROOT/docs/testing/xunit-direct-platform.md"
assert_exists "$SOURCE_ROOT/tests/xunit/smoke.quickstart.json"
assert_exists "$SOURCE_ROOT/src/epf/TemplateXUnitHarness/TemplateXUnitHarness.xml"
assert_exists "$SOURCE_ROOT/src/epf/TemplateXUnitHarness/TemplateXUnitHarness/Ext/ObjectModule.bsl"
assert_not_exists "$SOURCE_ROOT/src/epf/TemplateXUnitHarness/TemplateXUnitHarness/Forms"

assert_contains "$SOURCE_ROOT/src/epf/TemplateXUnitHarness/TemplateXUnitHarness.xml" "<DefaultForm/>"
assert_contains "$SOURCE_ROOT/src/epf/TemplateXUnitHarness/TemplateXUnitHarness/Ext/ObjectModule.bsl" "Template xUnit harness"
assert_contains "$SOURCE_ROOT/scripts/test/tdd-xunit.sh" "load-diff-src.sh"
assert_contains "$SOURCE_ROOT/scripts/test/tdd-xunit.sh" "update-db.sh"
assert_contains "$SOURCE_ROOT/scripts/test/tdd-xunit.sh" "run-xunit.sh"
assert_contains "$SOURCE_ROOT/scripts/test/tdd-xunit.sh" "use ./scripts/platform/load-src.sh -> ./scripts/platform/update-db.sh -> ./scripts/test/run-xunit.sh manually"
assert_contains "$SOURCE_ROOT/docs/testing/xunit-direct-platform.md" "./scripts/test/tdd-xunit.sh"
