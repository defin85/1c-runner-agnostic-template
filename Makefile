SHELL := bash

.PHONY: help qa analyze-bsl format-bsl test-xunit test-bdd smoke export-context verify-traceability template-check-update template-update

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make qa' \
		'  make analyze-bsl' \
		'  make format-bsl' \
		'  make test-xunit' \
		'  make test-bdd' \
		'  make smoke' \
		'  make export-context' \
		'  make verify-traceability' \
		'  make template-check-update' \
		'  make template-update'

qa: analyze-bsl verify-traceability

analyze-bsl:
	@./scripts/qa/analyze-bsl.sh

format-bsl:
	@./scripts/qa/format-bsl.sh

test-xunit:
	@./scripts/test/run-xunit.sh

test-bdd:
	@./scripts/test/run-bdd.sh

smoke:
	@./scripts/test/run-smoke.sh

export-context:
	@./scripts/llm/export-context.sh

verify-traceability:
	@./scripts/llm/verify-traceability.sh

template-check-update:
	@./scripts/template/check-update.sh

template-update:
	@./scripts/template/update-template.sh
