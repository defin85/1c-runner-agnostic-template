#!/usr/bin/env bash
set -euo pipefail

project_agents_block_start="<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->"
project_agents_block_end="<!-- RUNNER_AGNOSTIC_TEMPLATE:END -->"

ensure_agents_file() {
  local agents_file="$1"

  if [ ! -f "$agents_file" ]; then
    mkdir -p "$(dirname "$agents_file")"
    : >"$agents_file"
  fi
}

remove_managed_block() {
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

trim_trailing_blank_lines() {
  local target_file="$1"
  local tmp_file

  tmp_file="$(mktemp)"

  awk '
    {
      lines[NR] = $0
      if ($0 !~ /^[[:space:]]*$/) {
        last_nonblank = NR
      }
    }
    END {
      for (i = 1; i <= last_nonblank; i++) {
        print lines[i]
      }
    }
  ' "$target_file" >"$tmp_file"

  mv "$tmp_file" "$target_file"
}

remove_stale_openspec_agents_scaffold() {
  local agents_file="$1"

  if ! grep -Fq -- "@/openspec/AGENTS.md" "$agents_file"; then
    return 0
  fi

  remove_managed_block "$agents_file" "<!-- OPENSPEC:START -->" "<!-- OPENSPEC:END -->"
}

append_project_agents_overlay() {
  local agents_file="$1"

  ensure_agents_file "$agents_file"
  remove_stale_openspec_agents_scaffold "$agents_file"
  remove_managed_block "$agents_file" "$project_agents_block_start" "$project_agents_block_end"
  trim_trailing_blank_lines "$agents_file"

  printf '%s\n\n' "$project_agents_block_start" >>"$agents_file"

  cat >>"$agents_file" <<'EOF'
# Language

- Plans, specs, and change descriptions should be written in Russian by default.
- Common technical terms, API names, setting keys, and code identifiers may stay in English.

# Project Docs

- This repository is a generated 1С-project created from `1c-runner-agnostic-template`.
- Start with [docs/agent/generated-project-index.md](docs/agent/generated-project-index.md) for the generated-project-first onboarding path.
- Run `make codex-onboard` for a read-only first screen in a generated repo.
- Use [automation/context/project-map.md](automation/context/project-map.md) as the project-owned repo map.
- Use [automation/context/runtime-support-matrix.md](automation/context/runtime-support-matrix.md) and [automation/context/runtime-support-matrix.json](automation/context/runtime-support-matrix.json) as the checked-in runtime support truth.
- Use [automation/context/recommended-skills.generated.md](automation/context/recommended-skills.generated.md) as the compact project-aware skill router before opening the full catalog.
- Use [automation/context/hotspots-summary.generated.md](automation/context/hotspots-summary.generated.md) as the compact generated-derived map for the first hour.
- Use [automation/context/metadata-index.generated.json](automation/context/metadata-index.generated.json) as the deeper generated-derived inventory for narrowing the `src/` search space.
- Use [automation/context/runtime-profile-policy.json](automation/context/runtime-profile-policy.json) for sanctioned checked-in runtime profile policy.
- Use [docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md) and `make agent-verify` as the first no-1C verification path.
- Use `make imported-skills-readiness` before executable imported compatibility skills when the local contour may miss Python/Node dependencies.
- Use `make export-context-check` as the read-only freshness check for generated-derived context after the first baseline pass.
- Use [docs/agent/codex-workflows.md](docs/agent/codex-workflows.md) as the canonical Codex workflow guide after the first router step.
- Use [docs/agent/review.md](docs/agent/review.md), [docs/agent/operator-local-runbook.md](docs/agent/operator-local-runbook.md), [env/README.md](env/README.md), [.agents/skills/README.md](.agents/skills/README.md), [docs/exec-plans/README.md](docs/exec-plans/README.md), and [docs/work-items/README.md](docs/work-items/README.md) as the main follow-up routers.
- Use [docs/template-maintenance.md](docs/template-maintenance.md) only for template refresh and maintenance work.
- Ownership boundaries between template-managed and project-owned artifacts are described in [docs/agent/source-vs-generated.md](docs/agent/source-vs-generated.md).
- Quick runtime shortcuts: `./scripts/platform/load-diff-src.sh --profile <operator-profile> --run-root /tmp/load-diff-src-run` loads only the current git-backed diff inside `src/cf`, and `./scripts/platform/load-task-src.sh --profile <operator-profile> --work-item <id> --run-root /tmp/load-task-src-run` loads committed task scope by `Work-Item:` trailer or `--range`; operator-local prerequisites stay in [docs/agent/operator-local-runbook.md](docs/agent/operator-local-runbook.md) and [env/README.md](env/README.md).

# Unified Workflow

We operate in a cycle: **OpenSpec (What) -> Execution Plan -> Code (Implementation)**.

## 1. Intent Formation

- Any new capability, breaking change, architecture shift, major performance or security work, or ambiguous request starts with a change in `openspec/changes/<change-id>/`.
- Before code changes begin, the change must be brought to a signable contract through `proposal.md`, one or more `specs/<capability>/spec.md` deltas, `tasks.md`, and `traceability.md`.
## 2. Execution And Delivery

- Before coding, build an execution matrix: `Requirement/Scenario -> target files -> automated checks`.
- Every mandatory `MUST` or Requirement/Scenario must have automated evidence in `tests/` or `features/`, or an exception explicitly approved by the user.
- `partially implemented` or `not implemented` status for mandatory requirements blocks completion.
- Final delivery must include explicit `Requirement -> Code -> Test` evidence with concrete file paths.
EOF

  cat >>"$agents_file" <<'EOF'

## Search Playbook

Search order:

1. `mcp__claude-context__search_code`, if available in the current environment
2. `ast-index search "<query>"`, if the repository uses `ast-index` or semantic search is noisy
3. `rg`
4. `rg --files`
5. Targeted file reads

Optional sidecar: `rlm-tools`

- Use `rlm-tools` for low-context exploration when broad grep or file reads would dump too much raw text into the conversation.
- Treat `rlm-tools` as exploratory evidence, not final proof. Confirm final facts with direct code evidence.

Checklist:

1. Formulate the query as `component + action + context`.
2. Keep the first pass narrow: 6-10 results or equivalent scope.
3. Restrict by extension or relevant directories early.
4. If results are noisy, rephrase with concrete entities.
5. Confirm facts in at least two sources: code + test/spec/README.
6. Do not treat TODO/checklist/status files as proof of implementation.

## Landing the Plane

- For remote-backed repos with a writable Git remote, a code-change session is not complete until the verified branch state is pushed.
- For local-only repos or repos without a writable remote, do not invent a push-only closeout path.
- Before handoff, update task status and run the relevant quality gates. If remote sync is expected, rebase or push only after the local verification set is green.
EOF

  printf '\n%s\n' "$project_agents_block_end" >>"$agents_file"
}
