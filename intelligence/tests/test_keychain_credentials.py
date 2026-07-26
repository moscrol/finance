from __future__ import annotations

import json
import subprocess
import pytest

from intelligence.services import keychain_credentials
from intelligence.services.keychain_credentials import (
    KeychainCredentialError,
    KeychainCredentialStore,
    MacOSKeychainBackend,
)
from intelligence.services.llm_refine import LLMProvider


class FakeKeychainBackend:
    def __init__(self) -> None:
        self.payloads: dict[tuple[str, str], bytes] = {}
        self.calls: list[tuple[str, str, str, bytes | None]] = []
        self.fail_operation: str | None = None

    def save(
        self,
        *,
        service: str,
        account: str,
        label: str,
        payload: bytes,
    ) -> None:
        self.calls.append(("save", service, account, payload))
        if self.fail_operation == "save":
            raise KeychainCredentialError("native failure")
        assert label == "Foresight Workbench model"
        self.payloads[(account, service)] = payload

    def load(self, *, service: str, account: str) -> bytes | None:
        self.calls.append(("load", service, account, None))
        if self.fail_operation == "load":
            raise KeychainCredentialError("native failure")
        return self.payloads.get((account, service))

    def delete(self, *, service: str, account: str) -> None:
        self.calls.append(("delete", service, account, None))
        if self.fail_operation == "delete":
            raise KeychainCredentialError("native failure")
        self.payloads.pop((account, service), None)


def _provider(*, api_key: str = "keychain-secret-value") -> LLMProvider:
    return LLMProvider(
        name="openai",
        api_key=api_key,
        base_url="http://localhost:57244/v1",
        model="gpt-5.6-sol",
    )


def test_keychain_round_trip_supports_payloads_larger_than_cli_prompt_limit() -> None:
    backend = FakeKeychainBackend()
    store = KeychainCredentialStore(backend=backend)
    provider = _provider(api_key="k" * 512)

    store.save("alice", provider)
    loaded = store.load("alice")

    assert loaded == provider
    operation, service, account, payload = backend.calls[0]
    assert operation == "save"
    assert service == store.service
    assert account == "alice"
    assert payload is not None and len(payload) > 512
    assert "k" * 32 not in repr(store)


def test_keychain_delete_is_explicit_and_missing_is_idempotent() -> None:
    backend = FakeKeychainBackend()
    store = KeychainCredentialStore(backend=backend)
    store.save("alice", _provider())

    store.delete("alice")
    store.delete("alice")

    assert store.load("alice") is None
    delete_calls = [call for call in backend.calls if call[0] == "delete"]
    assert len(delete_calls) == 2
    assert all(call[3] is None for call in delete_calls)


def test_keychain_rejects_malformed_or_unsafe_record() -> None:
    backend = FakeKeychainBackend()
    store = KeychainCredentialStore(backend=backend)
    backend.payloads[("alice", store.service)] = json.dumps(
        {
            "provider": "openai",
            "api_key": "long-enough-secret",
            "base_url": "http://api.openai.com/v1",
            "model": "gpt-5.6-sol",
        }
    ).encode("utf-8")

    with pytest.raises(KeychainCredentialError, match="invalid saved credential"):
        store.load("alice")


def test_keychain_failure_is_sanitized() -> None:
    backend = FakeKeychainBackend()
    backend.fail_operation = "save"
    store = KeychainCredentialStore(backend=backend)

    with pytest.raises(KeychainCredentialError) as caught:
        store.save("alice", _provider())

    assert "keychain-secret-value" not in str(caught.value)
    assert "native failure" not in str(caught.value)


def test_native_keychain_load_times_out_without_exposing_secret(
    monkeypatch,
) -> None:
    def fake_run(command, **kwargs):
        assert command == [
            "/usr/bin/security",
            "find-generic-password",
            "-s",
            "com.foresight.workbench.llm",
            "-a",
            "alice",
            "-w",
        ]
        assert kwargs["capture_output"] is True
        assert kwargs["timeout"] == 3.0
        raise subprocess.TimeoutExpired(command, timeout=3.0)

    monkeypatch.setattr(keychain_credentials.subprocess, "run", fake_run)
    backend = MacOSKeychainBackend.__new__(MacOSKeychainBackend)

    with pytest.raises(KeychainCredentialError, match="unable to read"):
        backend.load(service="com.foresight.workbench.llm", account="alice")


@pytest.mark.parametrize("user_id", ("", "a" * 129))
def test_keychain_rejects_invalid_account_identity(user_id: str) -> None:
    store = KeychainCredentialStore(backend=FakeKeychainBackend())

    with pytest.raises(ValueError, match="user id"):
        store.load(user_id)
