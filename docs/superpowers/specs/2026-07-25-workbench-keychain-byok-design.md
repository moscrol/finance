# Workbench Keychain BYOK Design

Date: 2026-07-25
Status: approved by user request to persist the local gateway credential

## Goal

Allow a user to opt into reusing an OpenAI-compatible BYOK configuration after
Workbench restarts without storing a plaintext API key in the repository,
environment files, application data, logs, or run artifacts.

## Decision

Use one macOS generic-password Keychain item per Workbench user. The item stores
a JSON payload containing `provider`, `base_url`, `model`, and `api_key`. The
service name is fixed by the application; the Keychain account is the normalized
Workbench user id. The Python process calls Keychain Services through
`Security.framework` (`SecItemAdd`, `SecItemUpdate`, `SecItemCopyMatching`, and
`SecItemDelete`) instead of wrapping the `security` CLI.

The original CLI design was rejected during live acceptance: interactive
`security ... -w` input truncates password data at 128 characters, which cuts a
provider JSON record even when the API key itself is short. Native Keychain
Services keeps the secret out of process arguments and supports the full
configured key length.

Keychain integration is opt-in at runtime through
`FORESIGHT_LLM_KEYCHAIN=1`. Existing runtimes, including canonical 8792, keep
their current behavior unless explicitly enabled.

## Security Boundary

- Write and read through the in-process macOS Security framework. The secret
  never appears in subprocess argv, stdin prompts, environment variables, or
  shell history.
- Never include the Keychain payload, command stdout, API key, or base URL in
  errors, API responses, health responses, logs, traces, or artifacts.
- Continue validating custom endpoints: HTTP is allowed only for loopback;
  non-loopback endpoints require HTTPS; URL credentials/query/fragment are
  forbidden.
- Keychain failures are fail-closed. A response may say persistence failed but
  must not claim that the credential was saved.

## Product Semantics

The existing model settings dialog gains a `Remember securely on this Mac`
checkbox. With it enabled, configuration is written to Keychain before the
session provider becomes active. A saved credential is loaded lazily on the
first configuration or runtime request after restart.

Selecting the built-in model disables BYOK only for the current service
session. It does not delete Keychain state. Deletion is a separate explicit
`Delete saved credential` action. Reconfiguring BYOK re-enables it immediately.

Public configuration metadata may expose only mode, provider, model, readiness,
whether the active key is session-only, and whether a saved credential exists.
It never exposes `api_key` or `base_url`.

## Interfaces

- `KeychainCredentialStore.load(user_id) -> LLMProvider | None`
- `KeychainCredentialStore.save(user_id, provider) -> None`
- `KeychainCredentialStore.delete(user_id) -> None`
- `SessionLLMSettings.configure_byok(..., persist=False)`
- `SessionLLMSettings.disable_byok(user_id)`
- `SessionLLMSettings.forget_saved_byok(user_id)`

API changes:

- `PUT /api/llm/config` accepts `remember: boolean`.
- `DELETE /api/llm/config` selects built-in mode for this service session.
- `DELETE /api/llm/config/saved` explicitly deletes the saved Keychain item.

## Verification

Unit tests use an injected Keychain backend and never touch the real Keychain.
They assert that records larger than the CLI prompt limit round-trip, the key is
absent from public descriptions, saved
configuration reloads after a new settings instance, built-in selection does
not delete it, explicit deletion does, and persistence errors do not claim
success. API and frontend tests cover the new fields and actions.

The live acceptance is one final password-box submission with `remember`
enabled, followed by an 8798 restart and a credential-free GPT request. The
runtime must reload the provider, complete a real SDK episode, and keep all
secret-shaped values out of artifacts and logs.
