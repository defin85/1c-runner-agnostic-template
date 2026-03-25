#!/usr/bin/env bash
set -euo pipefail

project_agents_block_start="<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->"
project_agents_block_end="<!-- RUNNER_AGNOSTIC_TEMPLATE:END -->"

write_generated_agents_scaffold() {
  cat <<'EOF'
<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->
EOF
}

ensure_agents_file() {
  local agents_file="$1"

  if [ ! -f "$agents_file" ]; then
    mkdir -p "$(dirname "$agents_file")"
    write_generated_agents_scaffold >"$agents_file"
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

append_project_agents_overlay() {
  local agents_file="$1"
  local use_beads="$2"

  ensure_agents_file "$agents_file"
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
- Use [automation/context/project-map.md](automation/context/project-map.md) as the project-owned repo map.
- Use [automation/context/metadata-index.generated.json](automation/context/metadata-index.generated.json) as the generated-derived inventory for narrowing the `src/` search space.
- Use [docs/agent/generated-project-verification.md](docs/agent/generated-project-verification.md) and `make agent-verify` as the first no-1C verification path.
- Use [docs/agent/review.md](docs/agent/review.md), [env/README.md](env/README.md), [.agents/skills/README.md](.agents/skills/README.md), [.codex/README.md](.codex/README.md), and [docs/exec-plans/README.md](docs/exec-plans/README.md) as the main follow-up routers.
- Use [docs/template-maintenance.md](docs/template-maintenance.md) only for template refresh and maintenance work.
- Ownership boundaries between template-managed and project-owned artifacts are described in [docs/agent/source-vs-generated.md](docs/agent/source-vs-generated.md).

# Unified Workflow

We operate in a cycle: **OpenSpec (What) -> Beads (How) -> Code (Implementation)**.

## 1. Intent Formation

- Any new capability, breaking change, architecture shift, major performance or security work, or ambiguous request starts with a change in `openspec/changes/<change-id>/`.
- Before code changes begin, the change must be brought to a signable contract through `proposal.md`, one or more `specs/<capability>/spec.md` deltas, `tasks.md`, and `traceability.md`.
- Do not move to production code for new or major changes without explicit approval. Canonical signal: `Go!`.
- Before approval, analysis, requirement clarification, and spec edits are allowed; production code changes are not.

## 2. Task Transformation

- After approval, the change must be translated into an executable plan in `bd`, not left as markdown text only.
- For code changes, `bd` is the source of truth for task tracking. Run `bd prime` before planning or execution and work from `bd ready`.
- Do not use markdown TODO/checklists as a parallel tracker for code work.

## 3. Execution And Delivery

- Before coding, build an execution matrix: `Requirement/Scenario -> target files -> automated checks`.
- Every mandatory `MUST` or Requirement/Scenario must have automated evidence in `tests/` or `features/`, or an exception explicitly approved by the user.
- `partially implemented` or `not implemented` status for mandatory requirements blocks completion.
- Final delivery must include explicit `Requirement -> Code -> Test` evidence with concrete file paths.
EOF

  if [ "$use_beads" = "yes" ]; then
    cat >>"$agents_file" <<'EOF'

## Issue Tracking

This project uses **bd (beads)** for issue tracking.
Run `bd prime` for workflow context, or install hooks (`bd hooks install`) for auto-injection.

**Rules:**
- Use `bd` as the source of truth for code-change tracking.
- Do not use markdown TODO lists as a parallel tracker.
- Prefer `--json` in programmatic or agent flows.
- Check `bd ready` before starting code work.
EOF
  else
    cat >>"$agents_file" <<'EOF'

## Issue Tracking

This template is designed for `bd`-first code-change tracking.
If beads was disabled during bootstrap, treat that as an explicit exception and do not silently replace it with markdown TODO tracking.
EOF
  fi

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
