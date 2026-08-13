## Context

The runtime already routes several PowerShell entrypoints through `scripts.python.cli`, while Bash still owns substantial orchestration and generated profiles require `runnerAdapter`. Generated project `tnl` provides the initial native Windows live-validation contour and links to this source change.

## Goals / Non-Goals

**Goals:**

- One Python orchestration implementation per supported capability.
- Native Windows without mandatory WSL/Git Bash for declared capabilities.
- Small OS primitives rather than a public adapter class hierarchy.
- Versioned overlay delivery with deterministic profile migration and rollback.

**Non-Goals:**

- Replacing 1C, Apache, or other external tools.
- Making Windows interactive desktop and POSIX Xpra/Xvfb identical.
- Preserving arbitrary shell snippets as a supported extension API.
- Promoting operator-local live contours to shared CI without evidence.

## Decisions

### Python CLI owns orchestration

Profiles, secrets, argv construction, process lifecycle, artifacts, redaction, and postconditions move behind `scripts.python.cli`. Shell files remain platform launchers only. This reuses the existing runtime instead of maintaining parallel Bash and PowerShell behavior.

### OS differences are narrow primitives

Executable resolution, process trees, services, paths, locks, and atomic replacement are internal primitives. Capability decisions remain in operation modules. POSIX GUI isolation is an explicit platform-only feature.

### Driver/backend is separate from transport

`designer` and `ibcmd` remain capability drivers; HTTP publication uses a structured backend; remote execution is an optional transport. Local execution is the default.

### SchemaVersion 3 is a controlled break

SchemaVersion 3 removes mandatory local `runnerAdapter`. The migration command reads schemaVersion 2, emits a dry-run report by default, and refuses arbitrary shell orchestration without a supported backend. No silent fallback is allowed.

### Results and registries are atomic and ownership-aware

JSON is written to the same directory and atomically replaced. Conflicting resource operations use an interprocess lock with timeout and owner metadata. Cancellation cleans up only processes owned by the current attempt; successful detached services follow their declared retention policy.

### Delivery is source-template first

Implementation and reusable tests land here, then a verified overlay release is consumed by `tnl`. Generated-project-specific MCP configuration stays project-owned. BSL Analyzer broker identity, cold-start arbitration and trusted endpoint verification remain owned by BSL Analyzer's deterministic rendezvous; the template does not duplicate them with an external registry.

## Risks / Trade-offs

- [Large migration surface] → Deliver vertical capability slices with parity fixtures before deleting legacy orchestration.
- [Profile breakage] → Provide deterministic dry-run migration and retain rollback to the previous overlay/profile pair.
- [Windows process identity mistakes] → Match PID, start time, executable identity, and owner fingerprint before cleanup.
- [Template update overwrites project truth] → Keep managed manifest explicit and test preservation in generated fixtures.
- [Live validation is environment-dependent] → Separate hermetic contracts from fingerprinted, expiring operator-local evidence.

## Migration Plan

1. Add schemaVersion 3 validation, migration report, runtime primitives, and golden contracts.
2. Convert core 1C capabilities and thin launchers; verify Windows/Linux parity.
3. Convert extension, HTTP, and reusable long-running-process capabilities.
4. Update generated templates, docs, support matrices, skills, and copier/update fixtures.
5. Validate source repo and generated fixtures, merge to `main`, and publish the next overlay tag through the repo-owned release command.
6. Consume the tag in `tnl`, run live evidence, rehearse rollback, then remove superseded project-local workarounds.
