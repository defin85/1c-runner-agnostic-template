## ADDED Requirements

### Requirement: Direct-Platform Xpra Process Cleanup

The direct-platform adapter SHALL clean up wrapper-owned GUI session processes after an `xpra` runtime command exits.

#### Scenario: Xpra wrapper starts helper processes

- **WHEN** a direct-platform command runs with `platform.xpra.enabled=true`
- **THEN** the wrapper MUST tag the `xpra` session with a per-run token
- **AND** shutdown MUST stop the display and terminate wrapper-owned `xpra`, `Xvfb`, window manager, `dbus`, and `gvfs` helper processes
- **AND** cleanup MUST avoid killing processes that existed before the wrapper started
