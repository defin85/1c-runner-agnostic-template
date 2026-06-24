## Context
The source implementation is `ut-delans-sdd`; the template must keep only reusable runtime infrastructure.

## Decisions
- Project-specific target names, infobases, routes, extension names, IP addresses, and local paths are not defaults in the template.
- New live 1C contours stay operator-local unless their smoke contract can run with fake binaries.
- Existing runner-agnostic public entrypoints remain shell scripts under `scripts/`.

## Non-Goals
- No Delans release regression, golden dump payloads, delivery stage wrappers, or MCP publication.
- Golden baseline transfer is limited to a generic fail-closed project hook: template ships the entrypoint and starter README, each generated project supplies its own comparison command and artifacts.
- No vendored `node_modules`.
