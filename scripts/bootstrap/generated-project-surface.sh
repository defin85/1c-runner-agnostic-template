#!/usr/bin/env bash
set -euo pipefail

generated_readme_block_start="<!-- RUNNER_AGNOSTIC_PROJECT:START -->"
generated_readme_block_end="<!-- RUNNER_AGNOSTIC_PROJECT:END -->"

normalize_project_description() {
  local description="${1:-}"

  if [ -n "$description" ]; then
    printf '%s\n' "$description"
    return 0
  fi

  printf '%s\n' "1С-проект, созданный на шаблоне runner-agnostic monorepo."
}

ensure_parent_dir() {
  mkdir -p "$(dirname "$1")"
}

sync_template_nested_readmes() {
  local template_root="$1"
  local target_root="$2"
  local source_readme rel_path

  while IFS= read -r source_readme; do
    rel_path="${source_readme#$template_root/}"
    install -D -m 0644 "$source_readme" "$target_root/$rel_path"
  done < <(
    find "$template_root" -type f -name 'README.md' \
      ! -path "$template_root/README.md" \
      | LC_ALL=C sort
  )
}

remove_block_if_present() {
  local target_file="$1"
  local block_start="$2"
  local block_end="$3"
  local tmp_file

  tmp_file="$(mktemp)"

  awk -v block_start="$block_start" -v block_end="$block_end" '
    $0 == block_start {
      skip = 1
      next
    }
    skip && $0 == block_end {
      skip = 0
      next
    }
    !skip {
      print
    }
  ' "$target_file" >"$tmp_file"

  mv "$tmp_file" "$target_file"
}

strip_leading_blank_lines() {
  local target_file="$1"
  local tmp_file

  tmp_file="$(mktemp)"

  awk '
    started || $0 !~ /^[[:space:]]*$/ {
      started = 1
      print
    }
  ' "$target_file" >"$tmp_file"

  mv "$tmp_file" "$target_file"
}

readme_is_source_template_overview() {
  local target_file="$1"

  [ -f "$target_file" ] || return 1

  grep -Fq -- "# 1c-runner-agnostic-template" "$target_file" &&
    grep -Fq -- "docs/agent/index.md" "$target_file" &&
    ! grep -Fq -- "$generated_readme_block_start" "$target_file"
}

write_generated_readme_router() {
  cat <<'EOF'
<!-- RUNNER_AGNOSTIC_PROJECT:START -->
## Agent Entry Point

Этот репозиторий является generated 1С-проектом, созданным на шаблоне `1c-runner-agnostic-template`.

- Canonical onboarding router: [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md).
- Read-only first screen: `make codex-onboard`.
- Curated project truth: [automation/context/project-map.md](automation/context/project-map.md).
- Checked-in runtime support truth: [automation/context/runtime-support-matrix.md](automation/context/runtime-support-matrix.md), [automation/context/runtime-support-matrix.json](automation/context/runtime-support-matrix.json).
- Generated-derived search aids: [automation/context/hotspots-summary.generated.md](automation/context/hotspots-summary.generated.md), [automation/context/metadata-index.generated.json](automation/context/metadata-index.generated.json).
- Verification and runtime contracts: [docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md), [env/README.md](env/README.md), [automation/context/runtime-profile-policy.json](automation/context/runtime-profile-policy.json).
- Follow-up routers: [docs/agent/review.md](docs/agent/review.md), [.agents/skills/README.md](.agents/skills/README.md), [.codex/README.md](.codex/README.md), [docs/exec-plans/README.md](docs/exec-plans/README.md).
- Template maintenance path вынесен в [docs/template-maintenance.md](docs/template-maintenance.md) и не является primary feature-delivery workflow.
<!-- RUNNER_AGNOSTIC_PROJECT:END -->
EOF
}

write_generated_readme_starter() {
  local target_file="$1"
  local project_name="$2"
  local project_slug="$3"
  local project_description="$4"

  project_description="$(normalize_project_description "$project_description")"
  ensure_parent_dir "$target_file"

  {
    write_generated_readme_router
    printf '\n# %s\n\n' "$project_name"
    printf '%s\n\n' "$project_description"
    cat <<EOF
## Что это за репозиторий

- generated 1С-проект с deployable source tree в \`src/\`;
- reusable runtime/test/QA contract поставляется template-managed scripts и docs;
- project-specific truth должна жить в project-owned артефактах, а не в template maintenance docs.

## Главные каталоги

- \`src/\` — основная конфигурация, расширения, обработки и отчеты;
- \`scripts/\` — канонические entrypoint-скрипты для запуска, тестов и QA;
- \`automation/context/project-map.md\` — project-owned карта системы;
- \`automation/context/runtime-support-matrix.md\` и \`automation/context/runtime-support-matrix.json\` — checked-in runtime support truth;
- \`automation/context/hotspots-summary.generated.md\` — compact summary-first карта hot paths;
- \`automation/context/metadata-index.generated.json\` — raw generated-derived inventory для deeper narrowing search;
- \`automation/context/runtime-profile-policy.json\` — policy для sanctioned checked-in runtime profiles;
- \`openspec/\` — contract-first workspace для требований и изменений;
- \`tests/\` и \`features/\` — automated checks разных слоёв.

## Безопасные указатели

- Read-only first screen: \`make codex-onboard\`.
- Safe-local baseline: \`make agent-verify\`, затем \`make export-context-check\`.
- Canonical onboarding route: [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md).
- Curated project truth: [automation/context/project-map.md](automation/context/project-map.md).
- Checked-in runtime truth: [automation/context/runtime-support-matrix.md](automation/context/runtime-support-matrix.md), [automation/context/runtime-support-matrix.json](automation/context/runtime-support-matrix.json).
- Runtime profile contract и sanctioned checked-in presets: [env/README.md](env/README.md), [automation/context/runtime-profile-policy.json](automation/context/runtime-profile-policy.json).
- Template maintenance path вынесен в [docs/template-maintenance.md](docs/template-maintenance.md) и не является primary feature-delivery workflow.

## Ownership Classes

- \`template-managed\`: \`scripts/\`, template docs, shared skills, CI contours, managed blocks, \`.template-overlay-version\`.
- \`seed-once / project-owned\`: \`README.md\`, \`openspec/project.md\`, \`automation/context/project-map.md\`, \`automation/context/runtime-profile-policy.json\`, \`automation/context/runtime-support-matrix.md\`, \`automation/context/runtime-support-matrix.json\`.
- \`generated-derived\`: \`automation/context/source-tree.generated.txt\`, \`automation/context/metadata-index.generated.json\`, \`automation/context/hotspots-summary.generated.md\`.
- \`local-private\`: \`env/local.json\`, \`env/wsl.json\`, \`env/.local/*.json\`, machine-specific MCP/Codex overrides.

## Closeout Semantics

- \`local-only\`: если writable remote нет или handoff остаётся локальным, сдавайте diff и verification state без выдуманного push-only шага.
- \`remote-backed\`: если проект работает через remote, sync/push делаются только после зелёного локального verification set.

## Repository Identity

- Имя проекта: \`$project_name\`
- Slug: \`$project_slug\`
EOF
  } >"$target_file"
}

refresh_generated_readme_router() {
  local target_file="$1"
  local project_name="$2"
  local project_slug="$3"
  local project_description="$4"
  local tmp_file

  if [ ! -s "$target_file" ] || readme_is_source_template_overview "$target_file"; then
    write_generated_readme_starter "$target_file" "$project_name" "$project_slug" "$project_description"
    return 0
  fi

  remove_block_if_present "$target_file" "$generated_readme_block_start" "$generated_readme_block_end"
  strip_leading_blank_lines "$target_file"

  tmp_file="$(mktemp)"
  {
    write_generated_readme_router
    printf '\n'
    cat "$target_file"
  } >"$tmp_file"

  mv "$tmp_file" "$target_file"
}

write_project_map_starter() {
  local target_file="$1"
  local project_name="$2"
  local project_slug="$3"
  local project_description="$4"

  project_description="$(normalize_project_description "$project_description")"
  ensure_parent_dir "$target_file"

  cat >"$target_file" <<EOF
# Project Map

## Repository Identity

- name: \`$project_name\`
- slug: \`$project_slug\`
- description: $project_description
- role: generated 1С-проект на шаблоне runner-agnostic monorepo

## Known Source Roots

- \`src/cf\` — исходники основной конфигурации
- \`src/cfe\` — исходники расширений
- \`src/epf\` — внешние обработки
- \`src/erf\` — внешние отчеты

## Ownership Model

- \`template-managed\`: shared runtime/test/QA contract, template docs, shared skills, managed blocks
- \`seed-once / project-owned\`: этот файл, \`README.md\`, \`openspec/project.md\`
- \`project-owned policy\`: \`automation/context/runtime-profile-policy.json\`
- \`generated-derived\`: \`automation/context/source-tree.generated.txt\`, \`automation/context/metadata-index.generated.json\`, \`automation/context/hotspots-summary.generated.md\`
- \`local-private\`: \`env/local.json\`, \`env/wsl.json\`, \`env/.local/*.json\`, machine-specific Codex/MCP config

## Canonical Entrypoints

- read-only onboarding: \`make codex-onboard\`
- baseline verify: \`make agent-verify\`
- runtime support truth: \`automation/context/runtime-support-matrix.md\`, \`automation/context/runtime-support-matrix.json\`
- project-owned sanctioned profile policy: \`automation/context/runtime-profile-policy.json\`
- context refresh: \`./scripts/llm/export-context.sh --write\`

## Runtime Support Truth

- checked-in runtime support truth: \`automation/context/runtime-support-matrix.md\`, \`automation/context/runtime-support-matrix.json\`
- project-owned sanctioned profile policy: \`automation/context/runtime-profile-policy.json\`
- local-private runtime profiles не должны становиться единственным durable shared source of truth вне runtime support matrix

## Immediate Routers

- onboarding: \`docs/agent/generated-project-index.md\`
- review: \`docs/agent/review.md\`
- env contract: \`env/README.md\`
- repeatable workflows: \`.agents/skills/README.md\`, \`.codex/README.md\`
- long-running plans: \`docs/exec-plans/README.md\`

## Next Enrichment Steps

- Зафиксируйте реальные bounded contexts, бизнес-термины и ключевые metadata entrypoint-ы.
- Дополните секции HTTP services, scheduled jobs, forms и extensions по фактическому проекту.
- Держите этот файл как curated project-owned truth, а generated-derived inventory refresh-ите отдельной командой.
EOF
}

write_runtime_profile_policy_starter() {
  local target_file="$1"

  ensure_parent_dir "$target_file"
  cat >"$target_file" <<'EOF'
{
  "rootEnvProfiles": {
    "canonicalExamples": [
      "env/local.example.json",
      "env/wsl.example.json",
      "env/ci.example.json",
      "env/windows-executor.example.json"
    ],
    "canonicalLocalPrivate": [
      "env/local.json",
      "env/wsl.json",
      "env/ci.json",
      "env/windows-executor.json"
    ],
    "sanctionedAdditionalProfiles": [],
    "localSandbox": "env/.local/"
  },
  "notes": [
    "Declare only checked-in team-shared presets here.",
    "Do not list local-private profiles from env/.local/ or ignored local.json/wsl.json files.",
    "Sanctioned checked-in profiles must not keep smoke/xunit/bdd as success-on-placeholder contours."
  ]
}
EOF
}

write_runtime_support_matrix_json_starter() {
  local target_file="$1"

  ensure_parent_dir "$target_file"
  cat >"$target_file" <<'EOF'
{
  "matrixRole": "project-owned-runtime-support-matrix",
  "statuses": [
    "supported",
    "unsupported",
    "operator-local",
    "provisioned"
  ],
  "contours": [
    {
      "id": "codex-onboard",
      "layer": "safe-local",
      "status": "supported",
      "entrypoint": "make codex-onboard",
      "profileProvenance": "none",
      "runbookPath": "docs/agent/generated-project-index.md",
      "summary": "Read-only onboarding snapshot for a new Codex session."
    },
    {
      "id": "agent-verify",
      "layer": "safe-local",
      "status": "supported",
      "entrypoint": "make agent-verify",
      "profileProvenance": "none",
      "runbookPath": "docs/agent/generated-project-verification.md",
      "summary": "No-1C baseline verification for docs, OpenSpec, skills, and context."
    },
    {
      "id": "export-context-check",
      "layer": "safe-local",
      "status": "supported",
      "entrypoint": "make export-context-check",
      "profileProvenance": "none",
      "runbookPath": "docs/agent/generated-project-verification.md",
      "summary": "Read-only freshness check for generated-derived context artifacts."
    },
    {
      "id": "doctor",
      "layer": "profile-required",
      "status": "operator-local",
      "entrypoint": "./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run",
      "profileProvenance": "operator-local env/local.json or explicit --profile",
      "runbookPath": "env/README.md",
      "summary": "Runtime readiness check depends on an operator-owned local profile."
    },
    {
      "id": "xunit",
      "layer": "profile-required",
      "status": "unsupported",
      "entrypoint": "./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run",
      "profileProvenance": "future sanctioned preset or operator-local repo-owned contour",
      "runbookPath": "docs/agent/generated-project-verification.md",
      "summary": "Keep fail-closed until the project wires a real repo-owned xUnit contour."
    },
    {
      "id": "bdd",
      "layer": "profile-required",
      "status": "unsupported",
      "entrypoint": "./scripts/test/run-bdd.sh --profile env/local.json --run-root /tmp/bdd-run",
      "profileProvenance": "future sanctioned preset or operator-local repo-owned contour",
      "runbookPath": "docs/agent/generated-project-verification.md",
      "summary": "Keep fail-closed until the project wires a real repo-owned BDD contour."
    },
    {
      "id": "smoke",
      "layer": "profile-required",
      "status": "unsupported",
      "entrypoint": "./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/smoke-run",
      "profileProvenance": "future sanctioned preset or operator-local repo-owned contour",
      "runbookPath": "docs/agent/generated-project-verification.md",
      "summary": "Keep fail-closed until the project wires a real repo-owned smoke contour."
    },
    {
      "id": "publish-http",
      "layer": "profile-required",
      "status": "unsupported",
      "entrypoint": "./scripts/platform/publish-http.sh --profile env/local.json --run-root /tmp/publish-http-run",
      "profileProvenance": "future sanctioned preset or operator-local repo-owned contour",
      "runbookPath": "docs/agent/generated-project-verification.md",
      "summary": "Keep fail-closed until the project wires a real repo-owned publish-http contour."
    }
  ]
}
EOF
}

write_runtime_support_matrix_markdown_starter() {
  local target_file="$1"

  ensure_parent_dir "$target_file"
  cat >"$target_file" <<'EOF'
# Runtime Support Matrix

Этот файл является project-owned checked-in truth для runtime contour-ов generated repo.

Статусы:

- `supported` — runnable по checked-in baseline или safe-local contract.
- `unsupported` — контур пока должен завершаться fail-closed и не считается baseline-ready.
- `operator-local` — runnable только через ignored local-private profile или operator-owned local setup.
- `provisioned` — требует provisioned/self-hosted runtime contour и выходит за safe-local baseline.

## Safe Local

| Contour | Status | Profile provenance | Canonical entrypoint | Runbook |
| --- | --- | --- | --- | --- |
| `codex-onboard` | `supported` | `none` | `make codex-onboard` | `docs/agent/generated-project-index.md` |
| `agent-verify` | `supported` | `none` | `make agent-verify` | `docs/agent/generated-project-verification.md` |
| `export-context-check` | `supported` | `none` | `make export-context-check` | `docs/agent/generated-project-verification.md` |

## Runtime Contours

| Contour | Status | Profile provenance | Canonical entrypoint | Runbook |
| --- | --- | --- | --- | --- |
| `doctor` | `operator-local` | `env/local.json` или явный `--profile` | `./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run` | `env/README.md` |
| `xunit` | `unsupported` | project decides later | `./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run` | `docs/agent/generated-project-verification.md` |
| `bdd` | `unsupported` | project decides later | `./scripts/test/run-bdd.sh --profile env/local.json --run-root /tmp/bdd-run` | `docs/agent/generated-project-verification.md` |
| `smoke` | `unsupported` | project decides later | `./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/smoke-run` | `docs/agent/generated-project-verification.md` |
| `publish-http` | `unsupported` | project decides later | `./scripts/platform/publish-http.sh --profile env/local.json --run-root /tmp/publish-http-run` | `docs/agent/generated-project-verification.md` |

## Rules

- Если durable docs ссылаются на contour, который живёт только через ignored local-private profile, отмечайте его здесь как `operator-local`.
- `automation/context/project-map.md` и onboarding docs должны ссылаться на этот matrix вместо того, чтобы делать `env/local.json` shared source of truth.
- Меняйте этот файл синхронно с `automation/context/runtime-profile-policy.json`, `docs/agent/generated-project-index.md` и `docs/agent/generated-project-verification.md`.
EOF
}

openspec_project_is_bootstrap_stub() {
  local target_file="$1"

  [ -f "$target_file" ] || return 1

  awk '
    /^[[:space:]]*$/ {
      next
    }
    {
      count++
      if ($0 != "# OpenSpec Project") {
        mismatch = 1
      }
    }
    END {
      exit !(!mismatch && count == 1)
    }
  ' "$target_file"
}

write_openspec_project_starter() {
  local target_file="$1"
  local project_name="$2"
  local project_slug="$3"
  local project_description="$4"

  project_description="$(normalize_project_description "$project_description")"
  ensure_parent_dir "$target_file"

  cat >"$target_file" <<EOF
# Project Context

## Purpose
\`$project_name\` это generated 1С-проект, созданный на шаблоне runner-agnostic monorepo.

Начальное описание проекта:

- $project_description

Project-specific business context, bounded contexts и metadata entrypoint-ы команда проекта должна уточнить и поддерживать в этом файле и в \`automation/context/project-map.md\`.

## Tech Stack

- 1С source tree в \`src/\`
- Bash launcher/test/QA scripts из шаблона
- OpenSpec для spec-driven development
- Beads (\`bd\`) для code-change tracking, если контур включён
- Markdown docs и machine-readable context в \`automation/context/\`

## Project Conventions

### Ownership Model

- \`template-managed\`: reusable scripts, shared skills, template docs, CI contours, managed blocks
- \`seed-once / project-owned\`: \`README.md\`, этот файл, \`automation/context/project-map.md\`, \`automation/context/runtime-support-matrix.md\`, \`automation/context/runtime-support-matrix.json\`
- \`generated-derived\`: \`automation/context/source-tree.generated.txt\`, \`automation/context/metadata-index.generated.json\`, \`automation/context/hotspots-summary.generated.md\`
- \`local-private\`: local runtime profiles, local MCP/Codex config, secrets

### Architecture Patterns

- Deployable source tree живёт в \`src/\`.
- Intent и изменения фиксируются в \`openspec/\`.
- Runtime/test/QA contract задаётся repo-owned scripts.
- Template maintenance path изолирован от feature-delivery workflow и документирован отдельно в \`docs/template-maintenance.md\`.

### Testing Strategy

- First-pass no-1C verification path: \`make codex-onboard\`, затем \`make agent-verify\`.
- Shared runtime support truth должна жить в \`automation/context/runtime-support-matrix.md\` и \`automation/context/runtime-support-matrix.json\`.
- Operator-local contour может использовать \`env/local.json\`, но не должен становиться единственным durable shared source of truth.
- Provisioned/self-hosted 1C contours запускаются только там, где есть нужный runtime и операторские credentials.

## Important Constraints

- Имя проекта: \`$project_name\`
- Slug проекта: \`$project_slug\`
- Project-owned truth не должна перетираться template overlay applies вне managed blocks.
- Generated-derived inventories нужно refresh-ить через explicit repo-owned commands.
EOF
}

seed_generated_project_surface_on_copy() {
  local root="$1"
  local project_name="$2"
  local project_slug="$3"
  local project_description="$4"

  write_generated_readme_starter "$root/README.md" "$project_name" "$project_slug" "$project_description"
  write_project_map_starter "$root/automation/context/project-map.md" "$project_name" "$project_slug" "$project_description"
  write_runtime_profile_policy_starter "$root/automation/context/runtime-profile-policy.json"
  write_runtime_support_matrix_json_starter "$root/automation/context/runtime-support-matrix.json"
  write_runtime_support_matrix_markdown_starter "$root/automation/context/runtime-support-matrix.md"
  write_openspec_project_starter "$root/openspec/project.md" "$project_name" "$project_slug" "$project_description"
}

refresh_generated_project_surface_on_update() {
  local root="$1"
  local project_name="$2"
  local project_slug="$3"
  local project_description="$4"

  refresh_generated_readme_router "$root/README.md" "$project_name" "$project_slug" "$project_description"

  if [ ! -f "$root/automation/context/project-map.md" ]; then
    write_project_map_starter "$root/automation/context/project-map.md" "$project_name" "$project_slug" "$project_description"
  fi

  if [ ! -f "$root/automation/context/runtime-profile-policy.json" ]; then
    write_runtime_profile_policy_starter "$root/automation/context/runtime-profile-policy.json"
  fi

  if [ ! -f "$root/automation/context/runtime-support-matrix.json" ]; then
    write_runtime_support_matrix_json_starter "$root/automation/context/runtime-support-matrix.json"
  fi

  if [ ! -f "$root/automation/context/runtime-support-matrix.md" ]; then
    write_runtime_support_matrix_markdown_starter "$root/automation/context/runtime-support-matrix.md"
  fi

  if [ ! -f "$root/openspec/project.md" ] || openspec_project_is_bootstrap_stub "$root/openspec/project.md"; then
    write_openspec_project_starter "$root/openspec/project.md" "$project_name" "$project_slug" "$project_description"
  fi
}
