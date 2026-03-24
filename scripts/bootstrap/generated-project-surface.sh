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

- Начните с [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md).
- Карта проекта и project-owned truth лежат в [automation/context/project-map.md](automation/context/project-map.md).
- Матрица проверок лежит в [docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md).
- Template maintenance path вынесен в [docs/template-maintenance.md](docs/template-maintenance.md) и не является primary feature-delivery workflow.
- Ownership model и граница `template-managed / project-owned / generated-derived / local-private` описаны в [docs/agent/source-vs-generated.md](docs/agent/source-vs-generated.md).
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
- \`openspec/\` — contract-first workspace для требований и изменений;
- \`tests/\` и \`features/\` — automated checks разных слоёв.

## Безопасный старт

1. Прочитайте [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md).
2. Сверьтесь с [automation/context/project-map.md](automation/context/project-map.md).
3. Запустите \`make agent-verify\`.
4. Если нужен template maintenance path, отдельно откройте [docs/template-maintenance.md](docs/template-maintenance.md).

## Ownership Classes

- \`template-managed\`: \`scripts/\`, template docs, shared skills, CI contours, managed blocks.
- \`seed-once / project-owned\`: \`README.md\`, \`openspec/project.md\`, \`automation/context/project-map.md\`.
- \`generated-derived\`: \`automation/context/source-tree.generated.txt\`, \`automation/context/metadata-index.generated.json\`.
- \`local-private\`: \`env/local.json\`, \`env/wsl.json\`, \`env/.local/*.json\`, machine-specific MCP/Codex overrides.

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
- \`generated-derived\`: \`automation/context/source-tree.generated.txt\`, \`automation/context/metadata-index.generated.json\`
- \`local-private\`: \`env/local.json\`, \`env/wsl.json\`, \`env/.local/*.json\`, machine-specific Codex/MCP config

## Canonical Entrypoints

- baseline verify: \`make agent-verify\`
- runtime doctor: \`./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run\`
- xUnit: \`./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run\`
- BDD: \`./scripts/test/run-bdd.sh --profile env/local.json --run-root /tmp/bdd-run\`
- smoke: \`./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/smoke-run\`
- context refresh: \`./scripts/llm/export-context.sh --write\`

## Next Enrichment Steps

- Зафиксируйте реальные bounded contexts, бизнес-термины и ключевые metadata entrypoint-ы.
- Дополните секции HTTP services, scheduled jobs, forms и extensions по фактическому проекту.
- Держите этот файл как curated project-owned truth, а generated-derived inventory refresh-ите отдельной командой.
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
        exit 1
      }
    }
    END {
      exit !(count == 1)
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
- \`seed-once / project-owned\`: \`README.md\`, этот файл, \`automation/context/project-map.md\`
- \`generated-derived\`: \`automation/context/source-tree.generated.txt\`, \`automation/context/metadata-index.generated.json\`
- \`local-private\`: local runtime profiles, local MCP/Codex config, secrets

### Architecture Patterns

- Deployable source tree живёт в \`src/\`.
- Intent и изменения фиксируются в \`openspec/\`.
- Runtime/test/QA contract задаётся repo-owned scripts.
- Template maintenance path изолирован от feature-delivery workflow и документирован отдельно в \`docs/template-maintenance.md\`.

### Testing Strategy

- First-pass no-1C verification path: \`make agent-verify\`.
- Profile-required runtime contours используют, например, \`--profile env/local.json --run-root /tmp/doctor-run\`.
- Provisioned/self-hosted 1C contours запускаются только там, где есть нужный runtime и операторские credentials.

## Important Constraints

- Имя проекта: \`$project_name\`
- Slug проекта: \`$project_slug\`
- Project-owned truth не должна перетираться template updates вне managed blocks.
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

  if [ ! -f "$root/openspec/project.md" ] || openspec_project_is_bootstrap_stub "$root/openspec/project.md"; then
    write_openspec_project_starter "$root/openspec/project.md" "$project_name" "$project_slug" "$project_description"
  fi
}
