## MODIFIED Requirements

### Requirement: Adapter-Friendly Runtime Model

The runtime toolkit SHALL expose a stable public contract while allowing the underlying 1C execution backend to vary by adapter.

#### Scenario: Same capability runs through different adapters

- **WHEN** a generated project chooses `direct-platform`, `remote-windows`, or another supported adapter
- **THEN** the public entrypoint path and intent of the capability MUST remain stable
- **AND** the adapter-specific logic MUST stay behind the script contract rather than leak into user workflows

#### Scenario: Direct-platform launch needs GUI isolation

- **WHEN** a generated project runs local `1cv8` or `1cv8c` through `runnerAdapter=direct-platform` on WSL/Linux
- **THEN** the stable entrypoint path MUST remain unchanged
- **AND** the adapter MUST be able to apply repo-owned `Xvfb` isolation behind the same script contract when the runtime profile explicitly enables it
- **AND** the same adapter policy MUST apply both to standard-builder capabilities and to profile-defined command arrays whose executable basename is `1cv8` or `1cv8c`
- **AND** generated project workflows MUST NOT require ad-hoc `xvfb-run ./scripts/...` wrappers as the canonical path

#### Scenario: Direct-platform xvfb preconditions are missing

- **WHEN** `platform.xvfb.enabled=true` but required local tools such as `xvfb-run` or `xauth` are unavailable
- **THEN** doctor and runtime execution MUST fail closed before any 1C process starts
- **AND** the reported failure MUST identify the missing wrapper precondition
