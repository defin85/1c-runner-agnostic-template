#!/usr/bin/env bash
# Contract: the `customer-site-operations` blueprint and its template-managed operator code carry no
# data of a concrete customer (design D3):
# - no IPv4 addresses or CIDRs except 127.0.0.1 and 0.0.0.0;
# - no UUIDs except the pinned placeholders 00000000-0000-4000-8000-00000000000[0-2];
# - no absolute paths of a developer workstation (`/home/...`, `/run/media/...`);
# - no e-mail addresses outside the reserved `example` domains;
# - no project terms from `SITE_DEIDENTIFY_DENYLIST` (separated by `|`). The template ships no customer names,
#   not even encoded, so the project passes its own names: customer, servers, bases, accounts.
# Before the real scan the checker is run on planted fixtures: each kind of finding must fail it.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

checker="$tmpdir/deidentify_check.py"
cat >"$checker" <<'PY'
import os
import re
import sys
from pathlib import Path

terms = [t for t in os.environ.get("SITE_DEIDENTIFY_DENYLIST", "").split("|") if t.strip()]
# A term matches only as a whole token: no letter (Latin or Cyrillic) directly before or after it.
LETTER = "A-Za-zЀ-ӿ"
DENY = re.compile(
    "|".join("(?<![%s])%s(?![%s])" % (LETTER, re.escape(t.strip()), LETTER) for t in terms), re.IGNORECASE
)
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\w.]*\d)")
IPV4_ALLOWED = {"127.0.0.1", "0.0.0.0"}
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
UUID_ALLOWED = {"00000000-0000-4000-8000-00000000000%d" % i for i in range(3)}
WORKSTATION = re.compile(r"/home/|/run/media/")
EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
EMAIL_ALLOWED = re.compile(r"(?:^|\.)example(?:\.(?:com|org|net))?$", re.IGNORECASE)


def files(paths):
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file() and "__pycache__" not in item.parts:
                    yield item
        elif path.is_file():
            yield path
        else:
            sys.exit("missing scan path: %s" % raw)


findings = 0
for path in files(sys.argv[1:]):
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_bytes().decode("latin-1")
    for number, line in enumerate(text.splitlines(), 1):
        found = []
        found += ["denylist term" for _ in DENY.finditer(line)] if terms else []
        found += ["IPv4 " + m.group(0) for m in IPV4.finditer(line) if m.group(0).split("/")[0] not in IPV4_ALLOWED]
        found += ["UUID" for m in UUID.finditer(line) if m.group(0).lower() not in UUID_ALLOWED]
        found += ["workstation path" for _ in WORKSTATION.finditer(line)]
        found += ["e-mail" for m in EMAIL.finditer(line) if not EMAIL_ALLOWED.search(m.group(1))]
        for kind in found:
            # Denylist matches are not echoed: the report must not spread the names it guards against.
            print("%s:%d: %s" % (path, number, kind))
            findings += 1
print("deidentify_findings=%d" % findings)
sys.exit(1 if findings else 0)
PY

scan() {
  python3 -I "$checker" "$@"
}

# Self-test: a clean fixture passes, every planted finding fails the checker.
fixtures="$tmpdir/fixtures"
mkdir -p "$fixtures"
cat >"$fixtures/clean.txt" <<'EOF'
host site-app-01.example, localhost 127.0.0.1, platform 8.3.27.0000, ring 0.0.0+0
cluster 00000000-0000-4000-8000-000000000000, owner admin@site.example, attribute control_url
EOF
scan "$fixtures/clean.txt" >/dev/null || { echo "self-test: clean fixture rejected" >&2; exit 1; }

planted=(
  "server 10.20.30.40"
  "network 192.168.0.0/24"
  "cluster 3f2504e0-4f89-41d3-9a0c-0305e82c3301"
  "path /home/someone/project"
  "path /run/media/someone/disk"
  "mail person@customer.ru"
  "dir infra/acme-site/server"
  "base PROJECT_SECRET_NAME"
)
for index in "${!planted[@]}"; do
  printf '%s\n' "${planted[$index]}" >"$fixtures/planted-$index.txt"
  if SITE_DEIDENTIFY_DENYLIST="project_secret_name|acme-site" scan "$fixtures/planted-$index.txt" >/dev/null; then
    echo "self-test: planted finding #$index was not detected" >&2
    exit 1
  fi
done

cd "$ROOT"
scan_paths=(
  automation/optional/customer-site-operations
  scripts/site
  scripts/python/site_operator.py
  tests/python/test_customer_site_server.py
  tests/python/test_customer_site_operator.py
)
if ! scan "${scan_paths[@]}"; then
  echo "customer-site-deidentified: findings above must be replaced with invented values" >&2
  exit 1
fi
echo "customer-site-deidentified: ok"
