SHELL := bash

.PHONY: help agent-verify act-preflight qa analyze-bsl format-bsl check-agent-docs check-skill-bindings check-overlay-manifest codex-onboard imported-skills-readiness create-ib dump-src load-src load-cfe configure-cfe-runtime-flags check-cfe-applicability check-cfe-config load-diff-src load-task-src update-db diff-src doctor check-x11-contour test-xunit tdd-xunit test-yaxunit sync-yaxunit-runtime yaxunit-warm-service web-client-diagnostic golden-create golden-restore golden-baseline test-bdd bdd-warm-service smoke export-context export-context-preview export-context-check export-context-write verify-traceability template-check-update template-update

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make agent-verify' \
		'  make act-preflight' \
		'  make qa' \
		'  make analyze-bsl' \
		'  make format-bsl' \
		'  make check-agent-docs' \
		'  make check-skill-bindings' \
		'  make check-overlay-manifest' \
		'  make codex-onboard' \
		'  make imported-skills-readiness' \
		'  make create-ib' \
		'  make dump-src' \
		'  make load-src' \
		'  make load-cfe' \
		'  make configure-cfe-runtime-flags' \
		'  make check-cfe-applicability' \
		'  make check-cfe-config' \
		'  make load-diff-src' \
		'  make load-task-src' \
		'  make update-db' \
			'  make diff-src' \
			'  make doctor' \
			'  make check-x11-contour' \
			'  make test-xunit' \
		'  make tdd-xunit' \
		'  make test-yaxunit' \
		'  make sync-yaxunit-runtime' \
		'  make yaxunit-warm-service' \
		'  make web-client-diagnostic' \
		'  make golden-create' \
		'  make golden-restore' \
		'  make golden-baseline' \
		'  make test-bdd' \
		'  make bdd-warm-service' \
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

act-preflight:
	@./scripts/qa/act-preflight.sh

qa: analyze-bsl check-agent-docs check-skill-bindings check-overlay-manifest verify-traceability

analyze-bsl:
	@./scripts/qa/analyze-bsl.sh

format-bsl:
	@./scripts/qa/format-bsl.sh

check-agent-docs:
	@./scripts/qa/check-agent-docs.sh

check-skill-bindings:
	@./scripts/qa/check-skill-bindings.sh

check-overlay-manifest:
	@./scripts/qa/check-overlay-manifest.sh

codex-onboard:
	@./scripts/qa/codex-onboard.sh

imported-skills-readiness:
	@./scripts/skills/run-imported-skill.sh --readiness

create-ib:
	@./scripts/platform/create-ib.sh

dump-src:
	@./scripts/platform/dump-src.sh

load-src:
	@./scripts/platform/load-src.sh

load-cfe:
	@./scripts/platform/load-cfe.sh

configure-cfe-runtime-flags:
	@./scripts/platform/configure-cfe-runtime-flags.sh

check-cfe-applicability:
	@./scripts/platform/check-cfe-applicability.sh

check-cfe-config:
	@./scripts/platform/check-cfe-config.sh

load-diff-src:
	@./scripts/platform/load-diff-src.sh

load-task-src:
	@./scripts/platform/load-task-src.sh

update-db:
	@./scripts/platform/update-db.sh

diff-src:
	@./scripts/platform/diff-src.sh

doctor:
	@./scripts/diag/doctor.sh

check-x11-contour:
	@./scripts/diag/check-x11-contour.sh

test-xunit:
	@./scripts/test/run-xunit.sh

tdd-xunit:
	@./scripts/test/tdd-xunit.sh

test-yaxunit:
	@./scripts/test/run-yaxunit.sh

sync-yaxunit-runtime:
	@./scripts/test/sync-yaxunit-runtime.sh

yaxunit-warm-service:
	@./scripts/test/run-yaxunit-warm-service.sh

web-client-diagnostic:
	@./scripts/test/run-web-client-diagnostic.sh

golden-create:
	@./tests/golden/create.sh

golden-restore:
	@./tests/golden/restore.sh

golden-baseline:
	@./scripts/test/run-golden-baseline.sh

test-bdd:
	@./scripts/test/run-bdd.sh

bdd-warm-service:
	@./scripts/test/run-bdd-warm-service.sh up

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
