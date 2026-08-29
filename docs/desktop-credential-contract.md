# Desktop Credential Contract

The canonical local Core credential is owned by Python/Core in the OS
credential store. On Windows, the current credential uses the target
`orbit-core.local-client-auth` with account `loopback-core`.

The Desktop Rust host must read that canonical target first. It may read
`loopback-core@orbit-core.local-client-auth` only when the canonical target is
missing; that target exists solely for compatibility with an older rotation
layout. A current credential always wins over a legacy or rotation credential.

Rotation, revoke, and reset must not leave Desktop using a stale credential.
Credential-store errors fail closed and are not treated as a missing value.
Credentials never belong in this repository, configuration files, command-line
arguments, application state, or logs.
