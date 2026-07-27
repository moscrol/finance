from __future__ import annotations

import ctypes
import json
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


def _native_backend(payload: bytes, *, status: int = 0):
    backend = MacOSKeychainBackend.__new__(MacOSKeychainBackend)
    released: list[int] = []
    buffer = (ctypes.c_uint8 * len(payload)).from_buffer_copy(payload)

    class FakeCoreFoundation:
        @staticmethod
        def CFDataGetLength(ref):
            assert ref == 404
            return len(payload)

        @staticmethod
        def CFDataGetBytePtr(ref):
            assert ref == 404
            return ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint8))

    class FakeSecurity:
        def SecItemCopyMatching(self, query, output):
            assert query == 303
            if status == 0:
                ctypes.cast(
                    output,
                    ctypes.POINTER(ctypes.c_void_p),
                )[0] = ctypes.c_void_p(404)
            return status

    backend._cf = FakeCoreFoundation()
    backend._security = FakeSecurity()
    backend._constants = {
        "kSecClass": 1,
        "kSecClassGenericPassword": 2,
        "kSecAttrService": 3,
        "kSecAttrAccount": 4,
        "kSecReturnData": 5,
        "kSecMatchLimit": 6,
        "kSecMatchLimitOne": 7,
    }
    backend._true = 8

    def fake_string(value, refs):
        ref = 100 + len(refs)
        refs.append(ref)
        return ref

    def fake_dictionary(pairs, refs):
        assert (5, 8) in pairs
        assert (6, 7) in pairs
        refs.append(303)
        return 303

    backend._string = fake_string
    backend._dictionary = fake_dictionary
    backend._release = lambda refs: released.extend(refs)
    return backend, released


def test_native_keychain_load_copies_cfdata_and_releases_refs() -> None:
    payload = b'{"provider":"openai","api_key":"secret-value"}'
    backend, released = _native_backend(payload)

    loaded = backend.load(
        service="com.foresight.workbench.llm",
        account="alice",
    )

    assert loaded == payload
    assert released[-1] == 404
    assert keychain_credentials.__dict__.get("subprocess") is None


def test_native_keychain_load_returns_none_for_missing_item() -> None:
    backend, released = _native_backend(b"unused", status=-25300)

    loaded = backend.load(
        service="com.foresight.workbench.llm",
        account="alice",
    )

    assert loaded is None
    assert 404 not in released


@pytest.mark.parametrize("user_id", ("", "a" * 129))
def test_keychain_rejects_invalid_account_identity(user_id: str) -> None:
    store = KeychainCredentialStore(backend=FakeKeychainBackend())

    with pytest.raises(ValueError, match="user id"):
        store.load(user_id)
