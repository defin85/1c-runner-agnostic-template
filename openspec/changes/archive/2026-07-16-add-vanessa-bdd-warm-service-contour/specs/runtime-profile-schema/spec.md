## ADDED Requirements
### Requirement: Vanessa BDD Target Contract
The template SHALL provide a checked-in target contract for operator-local Vanessa BDD profiles.

#### Scenario: Local BDD profile is selected for warm-service
- **WHEN** a generated repository runs a Vanessa BDD or BDD warm-service entrypoint with a local-private runtime profile
- **THEN** the entrypoint MUST validate the profile against checked-in target truth at `automation/context/operator-local-targets.json` under `operatorLocalTargets.vanessaBdd`
- **AND** the target truth MUST include a stable target id, expected infobase mode, and the non-secret infobase identity fields needed for that mode, such as file path for file infobases or server/ref for client-server infobases
- **AND** the entrypoint MUST fail closed when the local-private profile target id or infobase identity does not match the checked-in target truth
- **AND** local-private profiles MUST remain credential and path carriers rather than the only durable source of target identity
- **AND** the validation contract MUST allow projects to keep BDD unsupported until they explicitly configure their target truth

### Requirement: Repo-Local Port Lease Helper Fallback
The template SHALL provide a repo-local port lease helper fallback for operator-local runtime contours.

#### Scenario: Global port lease helper is not installed
- **WHEN** an operator-local contour needs a TestClient port lease
- **AND** `ONEC_TEST_PORT_LEASE_HELPER` is not set
- **AND** no `onec-test-port-lease` command is available in `PATH`
- **THEN** the contour MUST be able to use a template-managed repo-local helper
- **AND** the helper MUST support at least `lease`, `release`, and `status`
- **AND** the lookup order MUST prefer `ONEC_TEST_PORT_LEASE_HELPER`, then `PATH`, then the template-managed repo-local helper
- **AND** the helper MUST avoid embedding project-specific repository names by default
