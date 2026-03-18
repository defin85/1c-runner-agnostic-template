#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fake_designer="$tmpdir/fake-1cv8"
fake_ibcmd="$tmpdir/fake-ibcmd"

cat >"$fake_designer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'designer-invoked\n'
EOF

cat >"$fake_ibcmd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'ibcmd-invoked\n'
EOF

chmod +x "$fake_designer" "$fake_ibcmd"
export ONEC_IBCMD_PASSWORD="ibcmd-validation-secret"

assert_stderr_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "$expected" "$file"; then
    printf 'expected stderr text not found: %s\n' "$expected" >&2
    cat "$file" >&2
    exit 1
  fi
}

run_expect_failure() {
  local profile_path="$1"
  local stderr_path="$2"
  shift 2

  set +e
  (
    cd "$SOURCE_ROOT"
    "$@"
  ) >/dev/null 2>"$stderr_path"
  status=$?
  set -e

  if [ "$status" -eq 0 ]; then
    printf 'command unexpectedly succeeded\n' >&2
    cat "$stderr_path" >&2
    exit 1
  fi
}

profile_driver_and_command="$tmpdir/profile-driver-and-command.json"
cat >"$profile_driver_and_command" <<EOF
{
  "schemaVersion": 2,
  "profileName": "driver-and-command",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/driver-and-command",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "$tmpdir/standalone",
    "databasePath": "$tmpdir/standalone/db-data",
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "dumpSrc": {
      "driver": "ibcmd",
      "command": ["bash", "-lc", "printf 'bad-mix\\\\n'"]
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_driver_and_command="$tmpdir/driver-and-command.stderr"
run_expect_failure \
  "$profile_driver_and_command" \
  "$stderr_driver_and_command" \
  ./scripts/platform/dump-src.sh --profile "$profile_driver_and_command"
assert_stderr_contains "$stderr_driver_and_command" "must not define both driver and command"

profile_remote_adapter="$tmpdir/profile-remote-adapter.json"
cat >"$profile_remote_adapter" <<EOF
{
  "schemaVersion": 2,
  "profileName": "remote-adapter",
  "runnerAdapter": "remote-windows",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/remote-adapter",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "$tmpdir/standalone",
    "databasePath": "$tmpdir/standalone/db-data",
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "dumpSrc": {
      "driver": "ibcmd"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_remote_adapter="$tmpdir/remote-adapter.stderr"
run_expect_failure \
  "$profile_remote_adapter" \
  "$stderr_remote_adapter" \
  ./scripts/platform/dump-src.sh --profile "$profile_remote_adapter"
assert_stderr_contains "$stderr_remote_adapter" "ibcmd driver is supported only with runnerAdapter=direct-platform in phase 1"

profile_designer_partial="$tmpdir/profile-designer-partial.json"
cat >"$profile_designer_partial" <<EOF
{
  "schemaVersion": 2,
  "profileName": "designer-partial",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/designer-partial",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "capabilities": {
    "loadSrc": {
      "driver": "designer",
      "sourceDir": "./src/cf"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_designer_partial="$tmpdir/designer-partial.stderr"
run_expect_failure \
  "$profile_designer_partial" \
  "$stderr_designer_partial" \
  ./scripts/platform/load-src.sh --profile "$profile_designer_partial" --files "Catalogs/Items.xml"
assert_stderr_contains "$stderr_designer_partial" "partial load-src is supported only for ibcmd driver in phase 1"

profile_missing_ibcmd_path="$tmpdir/profile-missing-ibcmd-path.json"
cat >"$profile_missing_ibcmd_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "missing-ibcmd-path",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/missing-ibcmd-path",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "$tmpdir/standalone",
    "databasePath": "$tmpdir/standalone/db-data",
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "dumpSrc": {
      "driver": "ibcmd"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_missing_ibcmd_path="$tmpdir/missing-ibcmd-path.stderr"
run_expect_failure \
  "$profile_missing_ibcmd_path" \
  "$stderr_missing_ibcmd_path" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_ibcmd_path"
assert_stderr_contains "$stderr_missing_ibcmd_path" "platform.ibcmdPath"

profile_missing_ibcmd_data_dir="$tmpdir/profile-missing-ibcmd-data-dir.json"
cat >"$profile_missing_ibcmd_data_dir" <<EOF
{
  "schemaVersion": 2,
  "profileName": "missing-ibcmd-data-dir",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/missing-ibcmd-data-dir",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "databasePath": "$tmpdir/standalone/db-data",
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "dumpSrc": {
      "driver": "ibcmd"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_missing_ibcmd_data_dir="$tmpdir/missing-ibcmd-data-dir.stderr"
run_expect_failure \
  "$profile_missing_ibcmd_data_dir" \
  "$stderr_missing_ibcmd_data_dir" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_ibcmd_data_dir"
assert_stderr_contains "$stderr_missing_ibcmd_data_dir" "ibcmd.dataDir"

profile_missing_ibcmd_auth_user="$tmpdir/profile-missing-ibcmd-auth-user.json"
cat >"$profile_missing_ibcmd_auth_user" <<EOF
{
  "schemaVersion": 2,
  "profileName": "missing-ibcmd-auth-user",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/missing-ibcmd-auth-user",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "$tmpdir/standalone",
    "databasePath": "$tmpdir/standalone/db-data",
    "auth": {
      "user": null,
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "dumpSrc": {
      "driver": "ibcmd"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_missing_ibcmd_auth_user="$tmpdir/missing-ibcmd-auth-user.stderr"
run_expect_failure \
  "$profile_missing_ibcmd_auth_user" \
  "$stderr_missing_ibcmd_auth_user" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_ibcmd_auth_user"
assert_stderr_contains "$stderr_missing_ibcmd_auth_user" "ibcmd.auth.user"

profile_missing_ibcmd_auth_password_env="$tmpdir/profile-missing-ibcmd-auth-password-env.json"
cat >"$profile_missing_ibcmd_auth_password_env" <<EOF
{
  "schemaVersion": 2,
  "profileName": "missing-ibcmd-auth-password-env",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/missing-ibcmd-auth-password-env",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "$tmpdir/standalone",
    "databasePath": "$tmpdir/standalone/db-data",
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": null
    }
  },
  "capabilities": {
    "dumpSrc": {
      "driver": "ibcmd"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_missing_ibcmd_auth_password_env="$tmpdir/missing-ibcmd-auth-password-env.stderr"
run_expect_failure \
  "$profile_missing_ibcmd_auth_password_env" \
  "$stderr_missing_ibcmd_auth_password_env" \
  ./scripts/platform/dump-src.sh --profile "$profile_missing_ibcmd_auth_password_env"
assert_stderr_contains "$stderr_missing_ibcmd_auth_password_env" "ibcmd.auth.passwordEnv"

profile_bad_connection_mode="$tmpdir/profile-bad-connection-mode.json"
cat >"$profile_bad_connection_mode" <<EOF
{
  "schemaVersion": 2,
  "profileName": "bad-connection-mode",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/bad-connection-mode",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "remote",
    "dataDir": "$tmpdir/standalone",
    "databasePath": "$tmpdir/standalone/db-data",
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "dumpSrc": {
      "driver": "ibcmd"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_bad_connection_mode="$tmpdir/bad-connection-mode.stderr"
run_expect_failure \
  "$profile_bad_connection_mode" \
  "$stderr_bad_connection_mode" \
  ./scripts/platform/dump-src.sh --profile "$profile_bad_connection_mode"
assert_stderr_contains "$stderr_bad_connection_mode" "ibcmd.connectionMode=remote is not supported in phase 1; use data-dir"

profile_vrunner_adapter="$tmpdir/profile-vrunner-adapter.json"
cat >"$profile_vrunner_adapter" <<EOF
{
  "schemaVersion": 2,
  "profileName": "vrunner-adapter",
  "runnerAdapter": "vrunner",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/vrunner-adapter",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "$tmpdir/standalone",
    "databasePath": "$tmpdir/standalone/db-data",
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "dumpSrc": {
      "driver": "ibcmd"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_vrunner_adapter="$tmpdir/vrunner-adapter.stderr"
run_expect_failure \
  "$profile_vrunner_adapter" \
  "$stderr_vrunner_adapter" \
  ./scripts/platform/dump-src.sh --profile "$profile_vrunner_adapter"
assert_stderr_contains "$stderr_vrunner_adapter" "ibcmd driver is supported only with runnerAdapter=direct-platform in phase 1"

profile_ibcmd_partial="$tmpdir/profile-ibcmd-partial.json"
cat >"$profile_ibcmd_partial" <<EOF
{
  "schemaVersion": 2,
  "profileName": "ibcmd-partial",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/ibcmd-partial",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "$tmpdir/standalone",
    "databasePath": "$tmpdir/standalone/db-data",
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "loadSrc": {
      "driver": "ibcmd",
      "sourceDir": "./src/cf"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_path_escape="$tmpdir/path-escape.stderr"
run_expect_failure \
  "$profile_ibcmd_partial" \
  "$stderr_path_escape" \
  ./scripts/platform/load-src.sh --profile "$profile_ibcmd_partial" --files "../Catalogs/Items.xml"
assert_stderr_contains "$stderr_path_escape" "must stay within the configured source tree"

profile_missing_ibcmd_database_path="$tmpdir/profile-missing-ibcmd-database-path.json"
cat >"$profile_missing_ibcmd_database_path" <<EOF
{
  "schemaVersion": 2,
  "profileName": "missing-ibcmd-database-path",
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "$fake_designer",
    "ibcmdPath": "$fake_ibcmd"
  },
  "infobase": {
    "mode": "file",
    "filePath": "/var/tmp/missing-ibcmd-database-path",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "ibcmd": {
    "connectionMode": "data-dir",
    "dataDir": "$tmpdir/standalone",
    "auth": {
      "user": "ibcmd-user",
      "passwordEnv": "ONEC_IBCMD_PASSWORD"
    }
  },
  "capabilities": {
    "createIb": {
      "driver": "ibcmd"
    },
    "xunit": {
      "command": ["bash", "-lc", "printf 'xunit-ok\\\\n'"]
    },
    "bdd": {
      "command": ["bash", "-lc", "printf 'bdd-ok\\\\n'"]
    },
    "smoke": {
      "command": ["bash", "-lc", "printf 'smoke-ok\\\\n'"]
    }
  }
}
EOF

stderr_missing_ibcmd_database_path="$tmpdir/missing-ibcmd-database-path.stderr"
run_expect_failure \
  "$profile_missing_ibcmd_database_path" \
  "$stderr_missing_ibcmd_database_path" \
  ./scripts/platform/create-ib.sh --profile "$profile_missing_ibcmd_database_path"
assert_stderr_contains "$stderr_missing_ibcmd_database_path" "ibcmd.databasePath"
