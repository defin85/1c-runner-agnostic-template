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

ensure_generated_source_roots() {
  local root="$1"

  mkdir -p \
    "$root/src/cf" \
    "$root/src/cfe" \
    "$root/src/epf" \
    "$root/src/erf"
}

generated_configuration_name() {
  local root="$1"
  local config_xml="$root/src/cf/Configuration.xml"
  local attr_name=""

  if [ ! -f "$config_xml" ]; then
    return 0
  fi

  attr_name="$(sed -n 's/.*name="\([^"]*\)".*/\1/p' "$config_xml" | head -n 1)"
  if [ -n "$attr_name" ]; then
    printf '%s' "$attr_name"
    return 0
  fi

  sed -n 's/.*<Name>\([^<]*\)<\/Name>.*/\1/p' "$config_xml" | head -n 1
}

count_top_level_entries() {
  local root="$1"
  local rel="$2"

  if [ ! -d "$root/$rel" ]; then
    printf '0'
    return 0
  fi

  find "$root/$rel" -mindepth 1 -maxdepth 1 \( -type d -o -type f \) | wc -l | tr -d ' '
}

count_named_dirs() {
  local root="$1"
  local rel="$2"
  local dir_name="$3"

  if [ ! -d "$root/$rel" ]; then
    printf '0'
    return 0
  fi

  find "$root/$rel" -type d -name "$dir_name" | wc -l | tr -d ' '
}

repo_shape_snapshot_block() {
  local root="$1"
  local config_xml_state="missing"
  local config_name=""
  local extensions_count=""
  local epf_count=""
  local erf_count=""
  local subsystems_count=""
  local forms_count=""
  local services_count=""
  local scheduled_jobs_count=""
  local common_modules_count=""

  if [ -f "$root/src/cf/Configuration.xml" ]; then
    config_xml_state="present"
  fi

  config_name="$(generated_configuration_name "$root")"
  extensions_count="$(count_top_level_entries "$root" "src/cfe")"
  epf_count="$(count_top_level_entries "$root" "src/epf")"
  erf_count="$(count_top_level_entries "$root" "src/erf")"
  subsystems_count="$(count_top_level_entries "$root" "src/cf/Subsystems")"
  forms_count="$(count_named_dirs "$root" "src" "Forms")"
  services_count="$(( $(count_top_level_entries "$root" "src/cf/HTTPServices") + $(count_top_level_entries "$root" "src/cf/WebServices") ))"
  scheduled_jobs_count="$(count_top_level_entries "$root" "src/cf/ScheduledJobs")"
  common_modules_count="$(count_top_level_entries "$root" "src/cf/CommonModules")"

  printf '## Repo-Derived Snapshot\n\n'
  printf -- '- configuration xml: `%s`\n' "$config_xml_state"
  if [ -n "$config_name" ]; then
    printf -- '- configuration name: `%s`\n' "$config_name"
  fi
  printf -- '- subsystems: `%s`\n' "$subsystems_count"
  printf -- '- forms roots: `%s`\n' "$forms_count"
  printf -- '- extensions: `%s`\n' "$extensions_count"
  printf -- '- external processors: `%s`\n' "$epf_count"
  printf -- '- reports: `%s`\n' "$erf_count"
  printf -- '- service edges: `%s`\n' "$services_count"
  printf -- '- scheduled jobs: `%s`\n' "$scheduled_jobs_count"
  printf -- '- common modules: `%s`\n' "$common_modules_count"
}

remove_retired_source_root_docs() {
  local root="$1"

  rm -f \
    "$root/src/cf/AGENTS.md" \
    "$root/src/cf/README.md"
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
- Project-owned code map: [docs/agent/architecture-map.md](docs/agent/architecture-map.md).
- Canonical Codex workflow guide: [docs/agent/codex-workflows.md](docs/agent/codex-workflows.md).
- Operator-local runtime bridge: [docs/agent/operator-local-runbook.md](docs/agent/operator-local-runbook.md).
- Project-specific runtime digest: [docs/agent/runtime-quickstart.md](docs/agent/runtime-quickstart.md).
- Checked-in runtime support truth: [automation/context/runtime-support-matrix.md](automation/context/runtime-support-matrix.md), [automation/context/runtime-support-matrix.json](automation/context/runtime-support-matrix.json).
- AI-ready skill routing: [automation/context/recommended-skills.generated.md](automation/context/recommended-skills.generated.md), `make imported-skills-readiness`.
- Long-running companion workspace: [docs/work-items/README.md](docs/work-items/README.md).
- Project-specific delta bridge: [automation/context/project-delta-hotspots.generated.md](automation/context/project-delta-hotspots.generated.md).
- Generated-derived search aids: [automation/context/hotspots-summary.generated.md](automation/context/hotspots-summary.generated.md), [automation/context/metadata-index.generated.json](automation/context/metadata-index.generated.json).
- Verification and runtime contracts: [docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md), [env/README.md](env/README.md), [automation/context/runtime-profile-policy.json](automation/context/runtime-profile-policy.json).
- Follow-up routers: [docs/agent/review.md](docs/agent/review.md), [.agents/skills/README.md](.agents/skills/README.md), [.codex/README.md](.codex/README.md), [docs/exec-plans/README.md](docs/exec-plans/README.md), [docs/work-items/README.md](docs/work-items/README.md).
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
    cat <<'EOF'
## Что это за репозиторий

- generated 1С-проект с deployable source tree в `src/`;
- reusable runtime/test/QA contract поставляется template-managed scripts и docs;
- project-specific truth должна жить в project-owned артефактах, а не в template maintenance docs.

## Главные каталоги

- `src/` — основная конфигурация, расширения, обработки и отчеты;
- `scripts/` — канонические entrypoint-скрипты для запуска, тестов и QA;
- `automation/context/project-map.md` — project-owned карта системы;
- `docs/agent/architecture-map.md` — project-owned прикладная карта для typical change scenarios;
- `docs/agent/codex-workflows.md` — canonical Codex workflow guide для generated repo;
- `docs/agent/operator-local-runbook.md` — project-owned bridge для operator-local contour-ов;
- `docs/agent/runtime-quickstart.md` — project-owned короткий digest по runnable contour-ам и prerequisites;
- `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json` — checked-in runtime support truth;
- `automation/context/recommended-skills.generated.md` — compact project-aware first-hour routing поверх полного skills catalog;
- `docs/work-items/` — project-owned workspace для bulky supporting artifacts длинных задач;
- `automation/context/project-delta-hints.json` — project-owned selectors для project-specific customization layer;
- `automation/context/project-delta-hotspots.generated.md` — generated-derived bridge к project-specific hotspots;
- `automation/context/hotspots-summary.generated.md` — compact summary-first карта hot paths;
- `automation/context/metadata-index.generated.json` — raw generated-derived inventory для deeper narrowing search;
- `automation/context/runtime-profile-policy.json` — policy для sanctioned checked-in runtime profiles;
- `openspec/` — contract-first workspace для требований и изменений;
- `tests/` и `features/` — automated checks разных слоёв.

## Безопасные указатели

- Read-only first screen: `make codex-onboard`.
- Safe-local baseline: `make agent-verify`, затем `make export-context-check`.
- Operator-local xUnit TDD loop для fresh `src/cf` diff: `make tdd-xunit`.
- Canonical onboarding route: [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md).
- Curated project truth: [automation/context/project-map.md](automation/context/project-map.md).
- Project-owned code map: [docs/agent/architecture-map.md](docs/agent/architecture-map.md).
- Codex workflow guide: [docs/agent/codex-workflows.md](docs/agent/codex-workflows.md).
- Operator-local runtime bridge: [docs/agent/operator-local-runbook.md](docs/agent/operator-local-runbook.md).
- Project-specific runtime digest: [docs/agent/runtime-quickstart.md](docs/agent/runtime-quickstart.md).
- Checked-in runtime truth: [automation/context/runtime-support-matrix.md](automation/context/runtime-support-matrix.md), [automation/context/runtime-support-matrix.json](automation/context/runtime-support-matrix.json).
- Work-item workspace for bulky long-running artifacts: [docs/work-items/README.md](docs/work-items/README.md).
- Project-aware first-hour skill routing: [automation/context/recommended-skills.generated.md](automation/context/recommended-skills.generated.md), `make imported-skills-readiness`.
- Project-specific delta bridge: [automation/context/project-delta-hotspots.generated.md](automation/context/project-delta-hotspots.generated.md).
- Runtime profile contract и sanctioned checked-in presets: [env/README.md](env/README.md), [automation/context/runtime-profile-policy.json](automation/context/runtime-profile-policy.json).
- Template maintenance path вынесен в [docs/template-maintenance.md](docs/template-maintenance.md) и не является primary feature-delivery workflow.

## Ownership Classes

- `template-managed`: `scripts/`, template docs, shared skills, CI contours, managed blocks, `.template-overlay-version`.
- `seed-once / project-owned`: `README.md`, `openspec/project.md`, `.codex/config.toml`, `automation/context/project-map.md`, `docs/agent/architecture-map.md`, `docs/agent/operator-local-runbook.md`, `docs/agent/runtime-quickstart.md`, `docs/work-items/README.md`, `docs/work-items/TEMPLATE.md`, `automation/context/project-delta-hints.json`, `automation/context/runtime-profile-policy.json`, `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`.
- `generated-derived`: `automation/context/source-tree.generated.txt`, `automation/context/metadata-index.generated.json`, `automation/context/recommended-skills.generated.md`, `automation/context/hotspots-summary.generated.md`, `automation/context/project-delta-hotspots.generated.md`.
- `local-private`: `env/local.json`, `env/wsl.json`, `env/.local/*.json`, host-specific MCP/Codex overrides вне checked-in `.codex/config.toml`.

## Closeout Semantics

- `local-only`: если writable remote нет или handoff остаётся локальным, сдавайте diff и verification state без выдуманного push-only шага.
- `remote-backed`: если проект работает через remote, sync/push делаются только после зелёного локального verification set.

## Repository Identity

EOF
    printf -- '- Имя проекта: `%s`\n' "$project_name"
    printf -- '- Slug: `%s`\n' "$project_slug"
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
  local repo_root=""

  project_description="$(normalize_project_description "$project_description")"
  ensure_parent_dir "$target_file"
  repo_root="$(cd -- "$(dirname -- "$target_file")/../.." && pwd)"

  {
    cat <<'EOF'
# Project Map

## Repository Identity

EOF
    printf -- '- name: `%s`\n' "$project_name"
    printf -- '- slug: `%s`\n' "$project_slug"
    printf -- '- description: %s\n' "$project_description"
    cat <<'EOF'
- role: generated 1С-проект на шаблоне runner-agnostic monorepo

EOF
    repo_shape_snapshot_block "$repo_root"
    cat <<'EOF'

## Known Source Roots

- `src/cf` — исходники основной конфигурации
- `src/cfe` — исходники расширений
- `src/epf` — внешние обработки
- `src/erf` — внешние отчеты

## Ownership Model

- `template-managed`: shared runtime/test/QA contract, template docs, shared skills, managed blocks
- `seed-once / project-owned`: этот файл, `README.md`, `openspec/project.md`, `docs/work-items/README.md`, `docs/work-items/TEMPLATE.md`
- `project-owned policy`: `automation/context/runtime-profile-policy.json`
- `project-owned hints`: `automation/context/project-delta-hints.json`
- `generated-derived`: `automation/context/source-tree.generated.txt`, `automation/context/metadata-index.generated.json`, `automation/context/recommended-skills.generated.md`, `automation/context/hotspots-summary.generated.md`, `automation/context/project-delta-hotspots.generated.md`
- `local-private`: `env/local.json`, `env/wsl.json`, `env/.local/*.json`, host-specific Codex/MCP overrides вне checked-in `.codex/config.toml`

## Canonical Entrypoints

- read-only onboarding: `make codex-onboard`
- baseline verify: `make agent-verify`
- runtime support truth: `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`
- project-owned sanctioned profile policy: `automation/context/runtime-profile-policy.json`
- project-delta refresh inputs: `automation/context/project-delta-hints.json`
- context refresh: `./scripts/llm/export-context.sh --write`
- imported skill readiness: `make imported-skills-readiness`

## Runtime Support Truth

- checked-in runtime support truth: `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`
- project-owned sanctioned profile policy: `automation/context/runtime-profile-policy.json`
- local-private runtime profiles не должны становиться единственным durable shared source of truth вне runtime support matrix

## Project-Owned Digests

- code navigation bridge: `docs/agent/architecture-map.md`
- Codex workflow guide: `docs/agent/codex-workflows.md`
- operator-local runtime bridge: `docs/agent/operator-local-runbook.md`
- runtime quick answers: `docs/agent/runtime-quickstart.md`
- project-aware first-hour skill routing: `automation/context/recommended-skills.generated.md`
- long-running work-item workspace: `docs/work-items/README.md`
- project-specific delta selectors: `automation/context/project-delta-hints.json`
- generated delta bridge: `automation/context/project-delta-hotspots.generated.md`
- эти файлы должны оставаться согласованными с `automation/context/project-map.md`, runtime support matrix и generated-derived refresh path

## Immediate Routers

- onboarding: `docs/agent/generated-project-index.md`
- Codex workflow guide: `docs/agent/codex-workflows.md`
- code architecture: `docs/agent/architecture-map.md`
- operator-local runtime: `docs/agent/operator-local-runbook.md`
- runtime quick reference: `docs/agent/runtime-quickstart.md`
- project-aware skills: `automation/context/recommended-skills.generated.md`
- work-item workspace: `docs/work-items/README.md`
- project-delta bridge: `automation/context/project-delta-hotspots.generated.md`
- review: `docs/agent/review.md`
- env contract: `env/README.md`
- repeatable workflows: `.agents/skills/README.md`, `.codex/README.md`
- long-running plans: `docs/exec-plans/README.md`

## Next Enrichment Steps

- Зафиксируйте реальные bounded contexts, бизнес-термины и ключевые metadata entrypoint-ы.
- Перенесите первые ответы “где менять X?” в `docs/agent/architecture-map.md`.
- Держите `docs/agent/runtime-quickstart.md` и `docs/agent/operator-local-runbook.md` согласованными с `automation/context/runtime-support-matrix.md` и `.json`.
- Держите `automation/context/recommended-skills.generated.md` коротким generated-derived router поверх полного skills catalog и обновляйте его через `./scripts/llm/export-context.sh --write`.
- Держите `docs/work-items/` для bulky supporting artifacts, а progress и handoff оставляйте в `docs/exec-plans/`.
- Заполните `automation/context/project-delta-hints.json`, когда появятся стабильные project-specific prefixes, и refresh-ите `automation/context/project-delta-hotspots.generated.md`.
- Дополните секции HTTP services, scheduled jobs, forms и extensions по фактическому проекту.
- Держите этот файл как curated project-owned truth, а generated-derived inventory refresh-ите отдельной командой.
EOF
  } >"$target_file"
}

write_architecture_map_starter() {
  local target_file="$1"
  local repo_root=""

  ensure_parent_dir "$target_file"
  repo_root="$(cd -- "$(dirname -- "$target_file")/../.." && pwd)"
  {
    cat <<'EOF'
# Architecture Map

Этот файл является project-owned прикладной картой кода generated repo.
Держите его короче raw inventory и обновляйте тогда, когда команда уже знает реальные hot zones и representative scenarios.

## How To Use

1. Сначала подтвердите bounded context в `automation/context/project-map.md`.
2. Здесь сузьте поиск до 1-2 вероятных зон.
3. Если проект использует stable customization selectors, сначала откройте `automation/context/project-delta-hotspots.generated.md`.
4. Для deeper narrowing только после этого открывайте `automation/context/hotspots-summary.generated.md` и `automation/context/metadata-index.generated.json`.

EOF
    repo_shape_snapshot_block "$repo_root"
    cat <<'EOF'

## Representative Change Scenarios

| Scenario | Likely paths | Metadata objects / signals | Runbooks / tests |
| --- | --- | --- | --- |
| Изменение основной конфигурации | `src/cf`, nearby `src/cfe` roots | configuration tree, extensions | `automation/context/project-delta-hotspots.generated.md`, `docs/agent/runtime-quickstart.md`, `docs/agent/generated-project-verification.md` |
| Изменение verification or test contour | `scripts/test`, `tests/`, `automation/context/runtime-support-matrix.md` | test entrypoints, runtime matrix | `docs/agent/generated-project-verification.md`, `docs/agent/operator-local-runbook.md`, `env/README.md` |
| Изменение service or runtime edge | `scripts/platform`, `scripts/diag`, `src/cf` | platform entrypoints, runtime scripts, configuration tree | `docs/agent/operator-local-runbook.md`, `docs/agent/runtime-quickstart.md`, `env/README.md` |
| Изменение external processor/report surface | `src/epf`, `src/erf`, `src/cf` | external processors, reports, configuration tree | `automation/context/project-delta-hotspots.generated.md`, `docs/agent/review.md`, `tests/` |
| Изменение extension-owned behavior | `src/cfe`, nearby `src/cf` roots | extensions, extension touch points | `automation/context/project-map.md`, `automation/context/project-delta-hotspots.generated.md`, `automation/context/metadata-index.generated.json` |

## Hot Zones

- `src/cf` — основной configuration tree; дальше сужайте поиск через project-delta и generated summaries.
- `src/cfe` — extension-owned behavior и overlay points.
- `src/epf`, `src/erf` — внешние processors/reports и связанная tooling surface.
- `tests/` — verification contours, smoke contracts и repo-owned checks.
- `scripts/` — runtime, platform и QA entrypoints, которые определяют executable surface.

## Related Truth

- curated repo map: `automation/context/project-map.md`
- project-aware first-hour skills: `automation/context/recommended-skills.generated.md`
- project-delta selectors: `automation/context/project-delta-hints.json`
- project-delta bridge: `automation/context/project-delta-hotspots.generated.md`
- long-running work-item workspace: `docs/work-items/README.md`
- runtime quick answers: `docs/agent/runtime-quickstart.md`
- summary-first generated map: `automation/context/hotspots-summary.generated.md`
- raw generated inventory: `automation/context/metadata-index.generated.json`
- review expectations: `docs/agent/review.md`
EOF
  } >"$target_file"
}

write_operator_local_runbook_starter() {
  local target_file="$1"

  ensure_parent_dir "$target_file"
  cat >"$target_file" <<'EOF'
# Operator-Local Runbook

Этот файл является project-owned bridge для contour-ов, которые зависят от ignored local-private profile, operator-owned setup или provisioned runtime.

## When To Use

1. `automation/context/runtime-support-matrix.md` или `.json` помечает contour как `operator-local` или `provisioned`.
2. Нужно ответить на вопрос “реально ли я могу запустить contour здесь и чего не хватает?”.
3. Нужен preflight перед `doctor`, project-owned xUnit/smoke contour-ом или другим local-only runtime шагом.

## Preflight Checklist

- Подтвердите status и canonical entrypoint по `automation/context/runtime-support-matrix.md` и `.json`.
- Уточните profile provenance, обязательные env vars и ожидаемый `--run-root`.
- Проверьте, что run-root указывает во временный каталог, а не в checked-in путь.
- Заранее фиксируйте expected fail-closed состояние, чтобы contour не интерпретировался как baseline-ready.

## Contours

| Contour | Status | Canonical entrypoint | Profile / env vars | Expected fail-closed state | Related docs |
| --- | --- | --- | --- | --- | --- |
| `doctor` | `operator-local` | `./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run` | `env/local.json` или явный `--profile`; runtime binaries по `env/README.md` | non-zero + summary/stderr, если profile или runtime не готовы | `env/README.md`, `docs/agent/generated-project-verification.md` |
| `load-diff-src` | `operator-local` | `./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run` | `env/local.json` или явный `--profile`; prepared infobase + git worktree | non-zero + summary/stderr, если diff selection пустой или runtime не ready | `env/README.md`, `docs/agent/generated-project-index.md` |
| `load-task-src` | `operator-local` | `./scripts/platform/load-task-src.sh --profile env/local.json --bead task.1 --run-root /tmp/load-task-src-run` | `env/local.json` или явный `--profile`; prepared infobase + git history with task markers or explicit revset | non-zero + summary/stderr, если task selection пустой или runtime не ready | `env/README.md`, `docs/agent/generated-project-index.md` |
| `xunit` | `operator-local` | `./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run` | `direct-platform profile с wired addRoot + local 1C runtime`; для fresh `src/cf` diff используйте `./scripts/test/tdd-xunit.sh` | non-zero + summary/stderr, если profile не wired или delete/rename delta требует manual full sync | `docs/testing/xunit-direct-platform.md`, `env/README.md` |

## Project Extensions

- Если проект wires дополнительные operator-local `smoke`, `bdd` или другие contour-ы сверх template-shipped `xunit`, добавляйте сюда отдельную строку и синхронно обновляйте `automation/context/runtime-support-matrix.md`, `.json` и `docs/agent/runtime-quickstart.md`.
- Если contour перестал быть operator-local и стал checked-in baseline-ready, переносите truth обратно в runtime support matrix и baseline docs.

## Related Truth

- checked-in runtime truth: `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`
- runtime digest: `docs/agent/runtime-quickstart.md`
- xUnit contour details: `docs/testing/xunit-direct-platform.md`
- long-running companion workspace: `docs/work-items/README.md`
- general runtime contract: `env/README.md`
- verification semantics: `docs/agent/generated-project-verification.md`
EOF
}

write_runtime_quickstart_starter() {
  local target_file="$1"
  local repo_root=""

  ensure_parent_dir "$target_file"
  repo_root="$(cd -- "$(dirname -- "$target_file")/../.." && pwd)"
  {
    cat <<'EOF'
# Runtime Quickstart

Этот файл является project-owned коротким digest по runnable contour-ам generated repo.
Если нужен полный runtime contract, переходите в `env/README.md`; если нужен checked-in status truth, сначала смотрите `automation/context/runtime-support-matrix.md` и `.json`.
Если нужен ответ именно по local-private/operator-owned contour-ам, используйте `docs/agent/operator-local-runbook.md` как короткий bridge.

## Safe Local First Pass

1. `make codex-onboard`
2. `make agent-verify`
3. `make export-context-check`
4. `make imported-skills-readiness`

## AI-Ready First Pass

- Compact recommended workflows: `automation/context/recommended-skills.generated.md`
- Imported executable skill readiness: `make imported-skills-readiness`
- Full skill catalog after the first pass: `.agents/skills/README.md`

EOF
    repo_shape_snapshot_block "$repo_root"
    cat <<'EOF'

## Contour Quick Reference

| Contour | Status | Canonical command | Prerequisites | Runbook |
| --- | --- | --- | --- | --- |
| `codex-onboard` | `supported` | `make codex-onboard` | `shell-only` | `docs/agent/generated-project-index.md` |
| `agent-verify` | `supported` | `make agent-verify` | `shell-only` | `docs/agent/generated-project-verification.md` |
| `export-context-check` | `supported` | `make export-context-check` | `shell-only` | `docs/agent/generated-project-verification.md` |
| `doctor` | `operator-local` | `./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run` | `1C runtime + operator-owned profile` | `docs/agent/operator-local-runbook.md` |
| `load-diff-src` | `operator-local` | `./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run` | `ibcmd-ready operator-owned profile + prepared infobase + git worktree` | `docs/agent/operator-local-runbook.md` |
| `load-task-src` | `operator-local` | `./scripts/platform/load-task-src.sh --profile env/local.json --bead task.1 --run-root /tmp/load-task-src-run` | `ibcmd-ready operator-owned profile + prepared infobase + task markers or explicit revset` | `docs/agent/operator-local-runbook.md` |
| `xunit` | `operator-local` | `./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run` | `direct-platform profile with wired addRoot + local 1C runtime` | `docs/testing/xunit-direct-platform.md` |
| `bdd` | `unsupported` | `./scripts/test/run-bdd.sh --profile env/local.json --run-root /tmp/bdd-run` | `future project-owned contour or sanctioned preset` | `docs/agent/generated-project-verification.md` |
| `smoke` | `unsupported` | `./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/smoke-run` | `future project-owned contour or sanctioned preset` | `docs/agent/generated-project-verification.md` |
| `publish-http` | `unsupported` | `./scripts/platform/publish-http.sh --profile env/local.json --run-root /tmp/publish-http-run` | `future project-owned contour or sanctioned preset` | `docs/agent/generated-project-verification.md` |

## Optional Project-Specific Baseline Extension

- По умолчанию `projectSpecificBaselineExtension` в `automation/context/runtime-support-matrix.json` не объявлен.
- Если проект добавляет extra no-1C smoke, описывайте его там как project-specific extension, а не как template baseline.
- Здесь повторяйте extension только после того, как matrix и runbook уже согласованы.

## Related Truth Sources

- checked-in runtime truth: `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`
- sanctioned checked-in profile policy: `automation/context/runtime-profile-policy.json`
- project-aware first-hour skills: `automation/context/recommended-skills.generated.md`
- operator-local bridge: `docs/agent/operator-local-runbook.md`
- long-running companion workspace: `docs/work-items/README.md`
- generated verification guide: `docs/agent/generated-project-verification.md`
- general runtime contract: `env/README.md`
- code routing companion: `docs/agent/architecture-map.md`
EOF
  } >"$target_file"
}

write_work_items_readme_starter() {
  local target_file="$1"

  ensure_parent_dir "$target_file"
  cat >"$target_file" <<'EOF'
# Work Items

`docs/work-items/` является project-owned workspace для supporting artifacts длинных задач.
Используйте его, когда одного change contract в `OpenSpec` и одного living progress файла в `docs/exec-plans/` уже недостаточно.

## Role Separation

- `OpenSpec` — change contract, requirements, acceptance.
- `bd` — executable tracking и live status.
- `docs/exec-plans/active/<task-id>.md` — living progress, handoff и session restart.
- `docs/work-items/<task-id>/` — extracted notes, attachment summaries, bulky inputs, task-local evidence и supporting materials.

## When To Create A Work-Item Folder

1. У задачи есть дополнительные материалы, которые не должны жить в `src/`.
2. Нужны extracted summaries для raw attachments, писем или operator notes.
3. Нужны task-local evidence links, integration notes или bulky references рядом с exec-plan.

## What Not To Put Here

- не используйте `docs/work-items/` как замену `bd`;
- не дублируйте здесь progress, который уже должен жить в `docs/exec-plans/`;
- не переносите сюда code payload из `src/`.

## Suggested Layout

- `docs/work-items/<task-id>/index.md` — task-local landing page;
- `docs/work-items/<task-id>/notes.md` — extracted notes и summaries;
- `docs/work-items/<task-id>/attachments/` — raw supporting files, если их правда нужно version-control-ить;
- `docs/exec-plans/active/<task-id>.md` — companion living plan с progress и handoff.

## Starter Workflow

1. Если change новый или неоднозначный, начните с `OpenSpec`.
2. После approval переведите execution tracking в `bd`.
3. Скопируйте `docs/exec-plans/TEMPLATE.md` в `docs/exec-plans/active/<task-id>.md`.
4. Если нужны bulky supporting artifacts, скопируйте `docs/work-items/TEMPLATE.md` в `docs/work-items/<task-id>/index.md`.

## Related Truth

- planning guide: `docs/agent/codex-workflows.md`
- onboarding router: `docs/agent/generated-project-index.md`
- execution plans contract: `docs/exec-plans/README.md`
- work-item starter: `docs/work-items/TEMPLATE.md`
EOF
}

write_work_items_template_starter() {
  local target_file="$1"

  ensure_parent_dir "$target_file"
  cat >"$target_file" <<'EOF'
# Work Item Template

Скопируйте этот файл в `docs/work-items/<task-id>/index.md`, когда длинной задаче нужны supporting artifacts рядом с exec-plan.

## Identity

- Task / change id:
- Exec plan: `docs/exec-plans/active/<task-id>.md`
- OpenSpec change / spec:
- Related code paths:

## Inputs

- source materials:
- linked runbooks:
- linked tests / checks:

## Extracted Notes

-

## Decisions

-

## Evidence

-

## Attachments

- raw files, если они нужны:
- markdown summaries:

## Handoff Notes

- what the next session should read first:
- what stays in exec-plan vs what stays here:
EOF
}

write_project_delta_hints_starter() {
  local target_file="$1"

  ensure_parent_dir "$target_file"
  cat >"$target_file" <<'EOF'
{
  "hintsRole": "project-owned-project-delta-hints",
  "selectors": {
    "pathPrefixes": [],
    "pathKeywords": []
  },
  "representativePaths": [],
  "notes": [
    "Declare stable repo-relative prefixes or path keywords for project-specific customization zones.",
    "Keep this file project-owned and update it when recurring project-owned hotspots change.",
    "After changing selectors, refresh automation/context/project-delta-hotspots.generated.md via ./scripts/llm/export-context.sh --write."
  ]
}
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
  "projectSpecificBaselineExtension": null,
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
      "runbookPath": "docs/agent/operator-local-runbook.md",
      "summary": "Runtime readiness check depends on an operator-owned local profile."
    },
    {
      "id": "load-diff-src",
      "layer": "provisioned",
      "status": "operator-local",
      "entrypoint": "./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run",
      "profileProvenance": "operator-local env/local.json with partial-import-ready load-src or explicit --profile",
      "runbookPath": "docs/agent/operator-local-runbook.md",
      "summary": "Loads only the current git-backed diff inside src/cf through delegated load-src --files and requires an ibcmd-ready operator-owned local profile plus a prepared infobase."
    },
    {
      "id": "load-task-src",
      "layer": "provisioned",
      "status": "operator-local",
      "entrypoint": "./scripts/platform/load-task-src.sh --profile env/local.json --bead task.1 --run-root /tmp/load-task-src-run",
      "profileProvenance": "operator-local env/local.json with partial-import-ready load-src and canonical task markers or explicit --profile",
      "runbookPath": "docs/agent/operator-local-runbook.md",
      "summary": "Loads committed task scope through delegated load-src --files and requires an ibcmd-ready operator-owned local profile, a prepared infobase, and git history with task markers or an explicit revset."
    },
    {
      "id": "xunit",
      "layer": "profile-required",
      "status": "operator-local",
      "entrypoint": "./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run",
      "profileProvenance": "operator-local direct-platform profile with addRoot and a local 1C runtime",
      "runbookPath": "docs/testing/xunit-direct-platform.md",
      "summary": "Template-managed direct-platform xUnit contour with a local TDD wrapper for git-backed src/cf changes."
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
| `doctor` | `operator-local` | `env/local.json` или явный `--profile` | `./scripts/diag/doctor.sh --profile env/local.json --run-root /tmp/doctor-run` | `docs/agent/operator-local-runbook.md` |
| `load-diff-src` | `operator-local` | `env/local.json` с ready partial-import contour или явный `--profile` | `./scripts/platform/load-diff-src.sh --profile env/local.json --run-root /tmp/load-diff-src-run` | `docs/agent/operator-local-runbook.md` |
| `load-task-src` | `operator-local` | `env/local.json` с ready partial-import contour или явный `--profile` | `./scripts/platform/load-task-src.sh --profile env/local.json --bead task.1 --run-root /tmp/load-task-src-run` | `docs/agent/operator-local-runbook.md` |
| `xunit` | `operator-local` | `env/local.json`, `env/wsl.json`, `env/ci.json` или явный `--profile` с wired `capabilities.xunit` | `./scripts/test/run-xunit.sh --profile env/local.json --run-root /tmp/xunit-run` | `docs/testing/xunit-direct-platform.md` |
| `bdd` | `unsupported` | project decides later | `./scripts/test/run-bdd.sh --profile env/local.json --run-root /tmp/bdd-run` | `docs/agent/generated-project-verification.md` |
| `smoke` | `unsupported` | project decides later | `./scripts/test/run-smoke.sh --profile env/local.json --run-root /tmp/smoke-run` | `docs/agent/generated-project-verification.md` |
| `publish-http` | `unsupported` | project decides later | `./scripts/platform/publish-http.sh --profile env/local.json --run-root /tmp/publish-http-run` | `docs/agent/generated-project-verification.md` |

## Optional Project-Specific Baseline Extension

- По умолчанию `projectSpecificBaselineExtension` в `automation/context/runtime-support-matrix.json` остаётся `null`.
- Если проект добавляет extra no-1C smoke, используйте direct repo-owned entrypoint или `make project-smoke` и держите его отдельным от template baseline.
- `docs/agent/runtime-quickstart.md` и `make codex-onboard` должны ссылаться на extension только после того, как он объявлен здесь.

## Rules

- Если durable docs ссылаются на contour, который живёт только через ignored local-private profile, отмечайте его здесь как `operator-local` и ведите decision bridge через `docs/agent/operator-local-runbook.md`.
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

  {
    cat <<'EOF'
# Project Context

## Purpose
EOF
    printf '`%s` это generated 1С-проект, созданный на шаблоне runner-agnostic monorepo.\n' "$project_name"
    cat <<'EOF'

Начальное описание проекта:

EOF
    printf -- '- %s\n' "$project_description"
    cat <<'EOF'

Project-specific business context, bounded contexts и metadata entrypoint-ы команда проекта должна уточнить и поддерживать в этом файле и в `automation/context/project-map.md`.

## Tech Stack

- 1С source tree в `src/`
- Bash launcher/test/QA scripts из шаблона
- OpenSpec для spec-driven development
- Beads (`bd`) для code-change tracking, если контур включён
- Markdown docs и machine-readable context в `automation/context/`

## Project Conventions

### Ownership Model

- `template-managed`: reusable scripts, shared skills, template docs, CI contours, managed blocks
- `seed-once / project-owned`: `README.md`, этот файл, `automation/context/project-map.md`, `automation/context/runtime-support-matrix.md`, `automation/context/runtime-support-matrix.json`
- `generated-derived`: `automation/context/source-tree.generated.txt`, `automation/context/metadata-index.generated.json`, `automation/context/hotspots-summary.generated.md`
- `local-private`: local runtime profiles, host-specific MCP/Codex overrides вне checked-in `.codex/config.toml`, secrets

### Architecture Patterns

- Deployable source tree живёт в `src/`.
- Intent и изменения фиксируются в `openspec/`.
- `docs/exec-plans/` хранит living progress и handoff для длинных задач.
- `docs/work-items/` хранит bulky supporting artifacts, которые не должны жить в `OpenSpec`, одном exec-plan файле или в `src/`.
- Runtime/test/QA contract задаётся repo-owned scripts.
- Template maintenance path изолирован от feature-delivery workflow и документирован отдельно в `docs/template-maintenance.md`.

### Testing Strategy

- First-pass no-1C verification path: `make codex-onboard`, затем `make agent-verify`.
- Shared runtime support truth должна жить в `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`.
- Operator-local contour может использовать `env/local.json`, но не должен становиться единственным durable shared source of truth.
- Provisioned/self-hosted 1C contours запускаются только там, где есть нужный runtime и операторские credentials.

## Important Constraints

EOF
    printf -- '- Имя проекта: `%s`\n' "$project_name"
    printf -- '- Slug проекта: `%s`\n' "$project_slug"
    cat <<'EOF'
- Project-owned truth не должна перетираться template overlay applies вне managed blocks.
- Generated-derived inventories нужно refresh-ить через explicit repo-owned commands.
EOF
  } >"$target_file"
}

seed_generated_project_surface_on_copy() {
  local root="$1"
  local project_name="$2"
  local project_slug="$3"
  local project_description="$4"

  ensure_generated_source_roots "$root"
  remove_retired_source_root_docs "$root"
  write_generated_readme_starter "$root/README.md" "$project_name" "$project_slug" "$project_description"
  write_project_map_starter "$root/automation/context/project-map.md" "$project_name" "$project_slug" "$project_description"
  write_architecture_map_starter "$root/docs/agent/architecture-map.md"
  write_operator_local_runbook_starter "$root/docs/agent/operator-local-runbook.md"
  write_runtime_quickstart_starter "$root/docs/agent/runtime-quickstart.md"
  write_work_items_readme_starter "$root/docs/work-items/README.md"
  write_work_items_template_starter "$root/docs/work-items/TEMPLATE.md"
  write_project_delta_hints_starter "$root/automation/context/project-delta-hints.json"
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

  ensure_generated_source_roots "$root"
  remove_retired_source_root_docs "$root"
  refresh_generated_readme_router "$root/README.md" "$project_name" "$project_slug" "$project_description"

  if [ ! -f "$root/automation/context/project-map.md" ]; then
    write_project_map_starter "$root/automation/context/project-map.md" "$project_name" "$project_slug" "$project_description"
  fi

  if [ ! -f "$root/docs/agent/architecture-map.md" ]; then
    write_architecture_map_starter "$root/docs/agent/architecture-map.md"
  fi

  if [ ! -f "$root/docs/agent/operator-local-runbook.md" ]; then
    write_operator_local_runbook_starter "$root/docs/agent/operator-local-runbook.md"
  fi

  if [ ! -f "$root/docs/agent/runtime-quickstart.md" ]; then
    write_runtime_quickstart_starter "$root/docs/agent/runtime-quickstart.md"
  fi

  if [ ! -f "$root/docs/work-items/README.md" ]; then
    write_work_items_readme_starter "$root/docs/work-items/README.md"
  fi

  if [ ! -f "$root/docs/work-items/TEMPLATE.md" ]; then
    write_work_items_template_starter "$root/docs/work-items/TEMPLATE.md"
  fi

  if [ ! -f "$root/automation/context/project-delta-hints.json" ]; then
    write_project_delta_hints_starter "$root/automation/context/project-delta-hints.json"
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
