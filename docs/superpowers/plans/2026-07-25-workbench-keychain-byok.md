# Workbench Keychain BYOK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist an explicitly opted-in Workbench BYOK configuration in macOS Keychain and reload it without exposing the key.

**Architecture:** A small Keychain credential store owns native persistence and returns the existing `LLMProvider` value. `SessionLLMSettings` remains the composition boundary for in-memory, disabled-for-session, and persisted states. The API and React dialog expose only persistence intent and non-secret status.

**Tech Stack:** Python 3.12, macOS `security`, FastAPI/Pydantic, React/TypeScript, pytest, Vitest.

---

### Task 1: Keychain Credential Store

**Files:**
- Create: `intelligence/services/keychain_credentials.py`
- Test: `intelligence/tests/test_keychain_credentials.py`

- [ ] **Step 1: Write failing store tests**

Use an injected native backend to assert records larger than 128 characters
round-trip without any command argv; `load()` reconstructs the provider;
`delete()` uses only service/account selectors; malformed records fail closed.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python -m pytest intelligence/tests/test_keychain_credentials.py -q
```

Expected: import or missing implementation failure.

- [ ] **Step 3: Implement the store**

Create `KeychainCredentialStore` with:

```python
def save(self, user_id: str, provider: LLMProvider) -> None: ...
def load(self, user_id: str) -> LLMProvider | None: ...
def delete(self, user_id: str) -> None: ...
```

Use macOS `Security.framework` Keychain Services, a fixed service id, sanitized
exceptions, and the existing Base URL validator. Do not use the `security` CLI:
its interactive password input truncates records at 128 characters.

- [ ] **Step 4: Run tests and commit**

Expected: all Keychain store tests pass and no real Keychain item is touched.

### Task 2: Session Settings and API

**Files:**
- Modify: `intelligence/services/llm_settings.py`
- Modify: `intelligence/api/app.py`
- Test: `intelligence/tests/test_llm_settings.py`
- Test: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: Write failing state-machine tests**

Cover persisted reload, session-only configuration, session disable without
deletion, explicit forget, persistence failure, and public response redaction.

- [ ] **Step 2: Implement state transitions**

Add `persist` to `configure_byok`, lazy persisted load, disabled-user state,
`forget_saved_byok`, `credential_persisted`, and
`saved_credential_available`. Enable the store only when
`FORESIGHT_LLM_KEYCHAIN=1`.

- [ ] **Step 3: Extend the API**

`PUT /api/llm/config` accepts `remember`; existing DELETE disables for the
session; `DELETE /api/llm/config/saved` forgets the Keychain item.

- [ ] **Step 4: Run focused API/settings tests**

Expected: all existing and new tests pass with no secret in response text.

### Task 3: Model Settings UI

**Files:**
- Modify: `intelligence/webapp/src/components/ModelSettings.tsx`
- Modify: `intelligence/webapp/src/App.tsx`
- Modify: `intelligence/webapp/src/api.ts`
- Modify: `intelligence/webapp/src/types.ts`
- Modify: `intelligence/webapp/src/styles.css`
- Test: `intelligence/webapp/src/components/components.test.tsx`

- [ ] **Step 1: Write the failing component test**

Assert the remember checkbox submits `remember: true`, saved status is visible,
and explicit forget calls the new API without showing the key.

- [ ] **Step 2: Implement the controls**

Use a checkbox for persistence and a separate destructive text action for
forgetting. Keep the API key input `type=password` and clear it after save.

- [ ] **Step 3: Run frontend verification**

Run Vitest, ESLint, TypeScript typecheck, and production build.

### Task 4: Live Restart Acceptance

**Files:**
- Modify: `docs/verification/agent-runtime-backends-2026-07-25.md`

- [ ] **Step 1: Run backend regression and commit implementation**

Run focused suites, then all `intelligence/tests`. Record pre-existing
environment-only failures separately.

- [ ] **Step 2: Restart isolated 8798 with Keychain enabled**

Start with `FORESIGHT_LLM_KEYCHAIN=1`, never with a plaintext key environment
variable.

- [ ] **Step 3: One final opt-in submission**

The user enters the key in the Workbench password field and enables remember.
Verify public config says saved without returning the key or Base URL.

- [ ] **Step 4: Restart and prove reuse**

Restart 8798, verify the provider reloads, and complete a real `sdk_gpt` run
without re-entering the key. Then resume the frozen sequential benchmark.
