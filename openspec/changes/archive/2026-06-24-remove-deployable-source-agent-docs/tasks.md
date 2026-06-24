## 1. Contract

- [x] 1.1 Update OpenSpec requirements for generated routing above `src/cf`, semantic verification, and overlay cleanup of retired source-root docs
- [x] 1.2 Document migration impact: template update removes stale `src/cf/AGENTS.md` and `src/cf/README.md`

## 2. Template Surface

- [x] 2.1 Remove `src/cf/AGENTS.md` and `src/cf/README.md` from the template-managed surface and relocate their useful context to allowed files outside deployable `src/cf`
- [x] 2.2 Update bootstrap/generated-project surface scripts and managed manifests so new generated repos no longer receive these files
- [x] 2.3 Ensure overlay update removes stale `src/cf/AGENTS.md` and `src/cf/README.md` from older generated repos without rewriting neighboring 1C source files

## 3. Verification

- [x] 3.1 Update QA and smoke coverage for the new routing contract and add a fail-closed invariant that rejects non-1C routing artifacts in `src/cf`
- [x] 3.2 Run the relevant OpenSpec, QA, and smoke verification set
