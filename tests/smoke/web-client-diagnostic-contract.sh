#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

assert_jq() {
  local file="$1"
  local expr="$2"
  local label="$3"
  shift 3

  if ! jq -e "$expr" "$file" "$@" >/dev/null; then
    printf 'jq assertion failed (%s): %s\n' "$label" "$expr" >&2
    cat "$file" >&2
    exit 1
  fi
}

assert_not_contains() {
  local file="$1"
  local needle="$2"
  local label="$3"

  if grep -F "$needle" "$file" >/dev/null; then
    printf 'unexpected sensitive value in %s: %s\n' "$label" "$file" >&2
    exit 1
  fi
}

write_profile() {
  local target="$1"
  local capability_json="$2"
  local auth_json='{"mode":"os","user":null,"passwordEnv":null}'
  if [ "$#" -ge 3 ]; then
    auth_json="$3"
  fi

  cat >"$target" <<EOF
{
  "schemaVersion": 2,
  "profileName": "web-client-diagnostic-fixture",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "/tmp/fake-1cv8"
  },
  "infobase": {
    "mode": "client-server",
    "server": "fixture-server",
    "ref": "fixture",
    "auth": $auth_json
  },
  "capabilities": {
    "webClientDiagnostic": $capability_json
  }
}
EOF
}

source_root="$tmpdir/source"
mkdir -p "$source_root"
cat >"$source_root/summary.json" <<'EOF'
{
  "status": "failed",
  "exit_code": 42,
  "failure": {
    "classification": "feature execution failed"
  }
}
EOF

success_profile="$tmpdir/success-profile.json"
success_run="$tmpdir/success-run"
export WEB_DIAGNOSTIC_SECRET="super-secret-password"
write_profile "$success_profile" '{
  "webUrl": "http://agent:super-secret-password@example.test/fixture?token=super-secret-password&safe=1",
  "backend": "fixture",
  "sameInfobaseConfirmed": true,
  "route": "Fixture Route",
  "timeoutSeconds": 120,
  "postFailure": true
}' '{"mode":"user-password","user":"agent","passwordEnv":"WEB_DIAGNOSTIC_SECRET"}'

(
  cd "$SOURCE_ROOT"
  ONEC_WEB_CLIENT_DIAGNOSTIC_ALLOW_FIXTURE_BACKEND=1 \
    ./scripts/test/run-web-client-diagnostic.sh \
      --profile "$success_profile" \
      --run-root "$success_run" \
      --source-run-root "$source_root" \
      --source-stage run-bdd >/dev/null
)

assert_jq "$success_run/summary.json" '.schemaVersion == 1' "schema-version"
assert_jq "$success_run/summary.json" '.status == "success"' "success-status"
assert_jq "$success_run/summary.json" '.source.verdict.status == "failed"' "source-verdict"
assert_jq "$success_run/summary.json" '.target.publication.url | contains("__REDACTED")' "redacted-publication"
assert_jq "$success_run/summary.json" '.profileContract.publishHttpMaterialized == false' "publish-http-boundary"
assert_jq "$success_run/summary.json" '.verdictBoundary.diagnosticOnly == true and .verdictBoundary.sourceVerdictPreserved == true' "verdict-boundary"
assert_jq "$success_run/summary.json" '.evidence.extraction.status == "success"' "nested-extraction"
assert_not_contains "$success_run/summary.json" "super-secret-password" "summary"
assert_not_contains "$success_run/stdout.log" "super-secret-password" "stdout"
assert_not_contains "$success_run/stderr.log" "super-secret-password" "stderr"

fake_web_test_backend="$tmpdir/fake-browser.mjs"
cat >"$fake_web_test_backend" <<'EOF'
let loginVisible = true;
let loginClicked = false;
let navigatedSection = null;
let startupModalVisible = true;

const page = {
  locator(selector) {
    return {
      async isVisible() {
        return selector === '#authWindow_basic_login' ? loginVisible : true;
      },
      async fill(value) {
        if (selector === '#authWindow_basic_login' && value !== 'agent') {
          throw new Error('unexpected login user');
        }
        if (selector === '#authWindow_basic_password' && !value) {
          throw new Error('empty password');
        }
      },
      async click() {
        if (selector !== '#authWindow_basic_okButton') {
          throw new Error(`unexpected click selector: ${selector}`);
        }
        loginClicked = true;
        loginVisible = false;
      },
    };
  },
  async waitForSelector(selector) {
    if (selector !== '#themesCell_theme_0' || loginVisible) {
      throw new Error(`selector not available: ${selector}`);
    }
  },
  async waitForTimeout() {},
  url() {
    return loginVisible ? 'http://example.test/fixture/en/' : 'http://example.test/fixture/en_US/';
  },
  async title() {
    return loginVisible ? '1C:Enterprise' : 'Fixture 1C web client';
  },
  async evaluate() {
    return '<html><body>fixture</body></html>';
  },
  async screenshot() {
    return Buffer.from('fake screenshot');
  },
};

export async function connect(_url, options = {}) {
  if (process.env.WEB_DIAGNOSTIC_EXPECT_HEADLESS && String(options.headless) !== process.env.WEB_DIAGNOSTIC_EXPECT_HEADLESS) {
    throw new Error(`unexpected headless mode: ${options.headless}`);
  }
  return { activeSection: null, sections: [], tabs: [] };
}

export function getPage() {
  return page;
}

export async function closeStartupModals() {
  if (!loginClicked) {
    throw new Error('closeStartupModals before login');
  }
  startupModalVisible = false;
}

export async function navigateSection(name) {
  if (loginVisible || !loginClicked) {
    throw new Error(`navigateSection before login: ${name}`);
  }
  if (startupModalVisible) {
    return {
      sections: [{ name, active: false }],
      commands: [],
    };
  }
  navigatedSection = name;
  return {
    sections: [{ name, active: true }],
    commands: [{ name: 'Fixture Route' }],
  };
}

export async function openCommand(name) {
  if (loginVisible || !loginClicked) {
    throw new Error(`openCommand before login: ${name}`);
  }
  if (navigatedSection !== 'FixtureSection') {
    throw new Error(`openCommand before FixtureSection navigation: ${name}`);
  }
  return {
    activeTab: name,
    table: { present: true, columns: ['Номер'], rowCount: 1 },
    tables: [{ name: 'РаспоряженияНаДоставку', columns: ['Номер'], rowCount: 1 }],
  };
}

export async function readTable() {
  return { columns: ['Номер'], rows: [{ 'Номер': 'DL-001' }], total: 1, selectedRowIndex: 0 };
}

export async function screenshot() {
  return Buffer.from('fake screenshot');
}

export async function disconnect() {}
EOF

web_test_login_profile="$tmpdir/web-test-login-profile.json"
web_test_login_run="$tmpdir/web-test-login-run"
write_profile "$web_test_login_profile" '{
  "webUrl": "http://example.test/fixture",
  "backend": "web-test",
  "sameInfobaseConfirmed": true,
  "section": "FixtureSection",
  "route": "Fixture Route",
  "timeoutSeconds": 120,
  "postFailure": true
}' '{"mode":"user-password","user":"agent","passwordEnv":"WEB_DIAGNOSTIC_SECRET"}'
(
  cd "$SOURCE_ROOT"
  WEB_DIAGNOSTIC_EXPECT_HEADLESS=true \
  ONEC_WEB_CLIENT_DIAGNOSTIC_WEB_TEST_BACKEND_PATH="$fake_web_test_backend" \
    ./scripts/test/run-web-client-diagnostic.sh \
      --profile "$web_test_login_profile" \
      --run-root "$web_test_login_run" \
      --source-run-root "$source_root" >/dev/null
)
assert_jq "$web_test_login_run/summary.json" '.status == "success"' "web-test-login-status"
assert_jq "$web_test_login_run/summary.json" '.browser.display.mode == "headless" and .browser.display.headless == true' "web-test-login-headless-default"
assert_jq "$web_test_login_run/summary.json" '.browser.auth.loginPageDetected == true and .browser.auth.loginAttempted == true and .browser.auth.status == "success"' "web-test-login-auth"
assert_jq "$web_test_login_run/summary.json" '.evidence.section == "FixtureSection" and .evidence.navigation.requestedSection == "FixtureSection"' "web-test-login-navigation"
assert_jq "$web_test_login_run/summary.json" '.evidence.extraction.status == "success"' "web-test-login-extraction"
assert_not_contains "$web_test_login_run/summary.json" "super-secret-password" "web-test-login-summary"
assert_not_contains "$web_test_login_run/stdout.log" "super-secret-password" "web-test-login-stdout"
assert_not_contains "$web_test_login_run/stderr.log" "super-secret-password" "web-test-login-stderr"

web_test_visible_run="$tmpdir/web-test-visible-run"
(
  cd "$SOURCE_ROOT"
  WEB_DIAGNOSTIC_EXPECT_HEADLESS=false \
  ONEC_WEB_CLIENT_DIAGNOSTIC_WEB_TEST_BACKEND_PATH="$fake_web_test_backend" \
    ./scripts/test/run-web-client-diagnostic.sh \
      --profile "$web_test_login_profile" \
      --run-root "$web_test_visible_run" \
      --source-run-root "$source_root" \
      --browser-mode visible >/dev/null
)
assert_jq "$web_test_visible_run/summary.json" '.status == "success"' "web-test-visible-status"
assert_jq "$web_test_visible_run/summary.json" '.browser.display.mode == "visible" and .browser.display.headless == false and .browser.display.source == "cli"' "web-test-visible-mode"

missing_publication_profile="$tmpdir/missing-publication-profile.json"
missing_publication_run="$tmpdir/missing-publication-run"
write_profile "$missing_publication_profile" '{"backend":"fixture","sameInfobaseConfirmed":true}'
(
  cd "$SOURCE_ROOT"
  ./scripts/test/run-web-client-diagnostic.sh \
    --profile "$missing_publication_profile" \
    --run-root "$missing_publication_run" \
    --source-run-root "$source_root" >/dev/null
)
assert_jq "$missing_publication_run/summary.json" '.status == "unavailable" and .statusReason.class == "publication"' "missing-publication"

missing_auth_profile="$tmpdir/missing-auth-profile.json"
missing_auth_run="$tmpdir/missing-auth-run"
write_profile "$missing_auth_profile" '{
  "webUrl": "http://example.test/fixture",
  "backend": "fixture",
  "sameInfobaseConfirmed": true
}' '{"mode":"user-password","user":"agent","passwordEnv":"WEB_DIAGNOSTIC_MISSING_SECRET"}'
(
  cd "$SOURCE_ROOT"
  ./scripts/test/run-web-client-diagnostic.sh \
    --profile "$missing_auth_profile" \
    --run-root "$missing_auth_run" \
    --source-run-root "$source_root" >/dev/null
)
assert_jq "$missing_auth_run/summary.json" '.status == "unavailable" and .statusReason.class == "auth"' "missing-auth"

missing_backend_profile="$tmpdir/missing-backend-profile.json"
missing_backend_run="$tmpdir/missing-backend-run"
write_profile "$missing_backend_profile" '{
  "webUrl": "http://example.test/fixture",
  "backend": "unsupported-backend",
  "sameInfobaseConfirmed": true
}'
(
  cd "$SOURCE_ROOT"
  ./scripts/test/run-web-client-diagnostic.sh \
    --profile "$missing_backend_profile" \
    --run-root "$missing_backend_run" \
    --source-run-root "$source_root" >/dev/null
)
assert_jq "$missing_backend_run/summary.json" '.status == "unavailable" and .statusReason.class == "browser-automation"' "missing-backend"

timeout_profile="$tmpdir/timeout-profile.json"
timeout_run="$tmpdir/timeout-run"
write_profile "$timeout_profile" '{
  "webUrl": "http://example.test/fixture",
  "backend": "fixture",
  "sameInfobaseConfirmed": true
}'
set +e
(
  cd "$SOURCE_ROOT"
  ONEC_WEB_CLIENT_DIAGNOSTIC_ALLOW_FIXTURE_BACKEND=1 \
  ONEC_WEB_CLIENT_DIAGNOSTIC_FIXTURE_DELAY_MS=1500 \
    ./scripts/test/run-web-client-diagnostic.sh \
      --profile "$timeout_profile" \
      --run-root "$timeout_run" \
      --source-run-root "$source_root" \
      --timeout-seconds 1 >/dev/null
)
timeout_status=$?
set -e
if [ "$timeout_status" -ne 124 ]; then
  printf 'unexpected timeout exit code: %s\n' "$timeout_status" >&2
  exit 1
fi
assert_jq "$timeout_run/summary.json" '.status == "timeout" and .budget.timeoutSeconds == 1 and .budget.override.used == true' "timeout-status"
assert_jq "$timeout_run/summary.json" '.source.verdict.status == "failed"' "timeout-source-preserved"

mutating_run="$tmpdir/mutating-run"
set +e
(
  cd "$SOURCE_ROOT"
  ONEC_WEB_CLIENT_DIAGNOSTIC_ALLOW_FIXTURE_BACKEND=1 \
    ./scripts/test/run-web-client-diagnostic.sh \
      --profile "$timeout_profile" \
      --run-root "$mutating_run" \
      --source-run-root "$source_root" \
      --mode replay >/dev/null
)
mutating_status=$?
set -e
if [ "$mutating_status" -eq 0 ]; then
  printf 'mutating mode unexpectedly succeeded\n' >&2
  exit 1
fi
assert_jq "$mutating_run/summary.json" '.status == "failed" and .statusReason.class == "inspect-only"' "mutating-fail-closed"
assert_jq "$mutating_run/summary.json" '.evidence.extraction.status == "unsupported"' "mutating-extraction"
