SHELL := bash

.PHONY: help agent-verify qa analyze-bsl format-bsl check-agent-docs check-skill-bindings create-ib dump-src load-src update-db diff-src doctor test-xunit test-bdd smoke export-context export-context-preview export-context-check export-context-write verify-traceability template-check-update template-update

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make agent-verify' \
		'  make qa' \
		'  make analyze-bsl' \
		'  make format-bsl' \
		'  make check-agent-docs' \
		'  make check-skill-bindings' \
		'  make create-ib' \
		'  make dump-src' \
		'  make load-src' \
		'  make update-db' \
		'  make diff-src' \
		'  make doctor' \
		'  make test-xunit' \
		'  make test-bdd' \
		'  make smoke' \
		'  make export-context' \
		'  make export-context-preview' \
		'  make export-context-check' \
		'  make export-context-write' \
		'  make verify-traceability' \
		'  make template-check-update' \
		'  make template-update'

agent-verify:
	@./scripts/qa/agent-verify.sh

qa: analyze-bsl check-agent-docs check-skill-bindings verify-traceability

analyze-bsl:
	@./scripts/qa/analyze-bsl.sh

format-bsl:
	@./scripts/qa/format-bsl.sh

check-agent-docs:
	@./scripts/qa/check-agent-docs.sh

check-skill-bindings:
	@./scripts/qa/check-skill-bindings.sh

create-ib:
	@./scripts/platform/create-ib.sh

dump-src:
	@./scripts/platform/dump-src.sh

load-src:
	@./scripts/platform/load-src.sh

update-db:
	@./scripts/platform/update-db.sh

diff-src:
	@./scripts/platform/diff-src.sh

doctor:
	@./scripts/diag/doctor.sh

test-xunit:
	@./scripts/test/run-xunit.sh

test-bdd:
	@./scripts/test/run-bdd.sh

smoke:
	@./scripts/test/run-smoke.sh

export-context:
	@./scripts/llm/export-context.sh --help

export-context-preview:
	@./scripts/llm/export-context.sh --preview

export-context-check:
	@./scripts/llm/export-context.sh --check

export-context-write:
	@./scripts/llm/export-context.sh --write

verify-traceability:
	@./scripts/llm/verify-traceability.sh

template-check-update:
	@./scripts/template/check-update.sh

template-update:
	@./scripts/template/update-template.sh
