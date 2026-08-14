## 1. Runtime schema and foundation

- [x] 1.1 Add schemaVersion 3 local-default profile validation and canonical examples with structured driver/backend/transport fields.
- [x] 1.2 Add schemaVersion 2 dry-run migration reporting and fail-closed diagnostics for unsupported shell orchestration.
- [x] 1.3 Split profile, secret, path, redaction, result, process, service, and lock primitives into focused Python modules.
- [x] 1.4 Add atomic JSON publication, resource locking, timeout, cancellation, and cleanup ownership contracts.

## 2. Runtime capabilities

- [x] 2.1 Move doctor and core create/dump/load/update/diff orchestration behind the Python CLI.
- [x] 2.2 Keep `designer` and `ibcmd` as per-capability drivers independent of local/remote execution and verify Windows/Linux argv parity.
- [x] 2.3 Move diff-aware and task-aware loading to the shared Python result and source-root contract.
- [x] 2.4 Convert core `.sh` and `.ps1` files to thin launchers and add source contracts preventing orchestration drift.

## 3. Extended contours

- [x] 3.1 Move reusable CFE lifecycle operations to Python capabilities with target/extension validation.
- [x] 3.2 Add a structured HTTP publication backend with Windows service and HTTP postconditions.
- [x] 3.3 Route BSL Analyzer MCP through its deterministic rendezvous with readiness, reuse, and trusted endpoint checks instead of duplicating an external process registry.
- [x] 3.4 Keep Xpra/Xvfb/LD_PRELOAD POSIX-only and fail closed when enabled in Windows profiles.

## 4. Generated surface and delivery

- [x] 4.1 Update `make`/`make.ps1`, skills, runtime docs, and generated templates to expose equivalent native Windows/Linux targets.
- [x] 4.2 Extend generated runtime support matrix templates with platform/evidence dimensions and freshness checks.
- [x] 4.3 Update managed-path manifests and overlay/bootstrap fixtures for the full Python-first runtime surface.
- [x] 4.4 Verify overlay update preserves project-owned, local-private, secret, and `src/**` content.

## 5. Verification and release

- [x] 5.1 Add Python unit tests and Windows/Linux contract fixtures for Unicode paths, CRLF, executable resolution, redaction, atomic writes, locks, cancellation, and postconditions.
- [x] 5.2 Run runtime smoke, generated fixture, copier/update, source release, and strict OpenSpec checks.
- [x] 5.3 Produce Requirement → Code → Test traceability and verify rollback to the previous overlay/profile pair.
- [x] 5.4 Merge through the source-repo review path and publish the next overlay tag using the repo-owned release command.
