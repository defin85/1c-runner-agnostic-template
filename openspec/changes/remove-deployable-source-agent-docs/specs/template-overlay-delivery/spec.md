## ADDED Requirements

### Requirement: Overlay Update Retires Legacy Source-Root Routing Files

Generated repositories SHALL remove retired template-seeded routing docs from deployable `src/cf` during overlay maintenance.

#### Scenario: Generated repo updates from an older template release

- **WHEN** `make template-update` or the repo-owned overlay apply path runs in a generated repository that still contains legacy `src/cf/AGENTS.md` or `src/cf/README.md`
- **THEN** the update path MUST remove those retired files as part of the template migration
- **AND** the cleanup MUST NOT rewrite or sanitize neighboring 1C source files under `src/cf`
- **AND** template-maintenance docs and smoke tests MUST describe and verify that stale files disappear after the update
