from __future__ import annotations

import json
import subprocess

import pytest

from intelligence.services.keychain_credentials import (
    KeychainCredentialError,
    KeychainCredentialStore,
)
from intelligence.services.llm_refine import LLMProvider


class FakeSecurityRunner:
    def __init__(self) -> None:
        self.payloads: dict[tuple[str, str], str] = {}
        self.calls: list[tuple[list[str], str | None]] = []
        self.fail_operation: str | None = None

    def __call__(self, args: list[str], **kwargs: object):
        input_text = kwargs.get("input")
        assert input_text is None or isinstance(input_text, str)
        self.calls.append((list(args), input_text))
        operation = args[1]
        if self.fail_operation == operation:
            return subprocess.CompletedProcess(args, 1, "", "security failed")
        account = args[args.index("-a") + 1]
        service = args[args.index("-s") + 1]
        key = (account, service)
        if operation == "add-generic-password":
            assert isinstance(input_text, str)
            lines = input_text.splitlines()
            assert len(lines) == 2
            assert lines[0] == lines[1]
            self.payloads[key] = lines[0]
            return subprocess.CompletedProcess(args, 0, "", "")
        if operation == "find-generic-password":
            if key not in self.payloads:
                return subprocess.CompletedProcess(args, 44, "", "not found")
            return subprocess.CompletedProcess(args, 0, self.payloads[key] + "\n", "")
        if operation == "delete-generic-password":
            if key not in self.payloads:
                return subprocess.CompletedProcess(args, 44, "", "not found")
            del self.payloads[key]
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(f"unexpected operation: {operation}")


def _provider() -> LLMProvider:
    return LLMProvider(
        name="openai",
        api_key="keychain-secret-value",
        base_url="http://localhost:57244/v1",
        model="gpt-5.6-sol",
    )


def test_keychain_round_trip_keeps_secret_out_of_argv() -> None:
    runner = FakeSecurityRunner()
    store = KeychainCredentialStore(runner=runner)

    store.save("alice", _provider())
    loaded = store.load("alice")

    assert loaded == _provider()
    add_args, add_stdin = runner.calls[0]
    assert add_args[-1] == "-w"
    assert "keychain-secret-value" not in " ".join(add_args)
    assert add_stdin is not None
    assert add_stdin.count("keychain-secret-value") == 2
    assert "keychain-secret-value" not in repr(store)


def test_keychain_delete_is_explicit_and_missing_is_idempotent() -> None:
    runner = FakeSecurityRunner()
    store = KeychainCredentialStore(runner=runner)
    store.save("alice", _provider())

    store.delete("alice")
    store.delete("alice")

    assert store.load("alice") is None
    delete_args = [args for args, _stdin in runner.calls if args[1].startswith("delete")]
    assert len(delete_args) == 2
    assert all("keychain-secret-value" not in " ".join(args) for args in delete_args)


def test_keychain_rejects_malformed_or_unsafe_record() -> None:
    runner = FakeSecurityRunner()
    store = KeychainCredentialStore(runner=runner)
    runner.payloads[("alice", store.service)] = json.dumps(
        {
            "provider": "openai",
            "api_key": "long-enough-secret",
            "base_url": "http://api.openai.com/v1",
            "model": "gpt-5.6-sol",
        }
    )

    with pytest.raises(KeychainCredentialError, match="invalid saved credential"):
        store.load("alice")


def test_keychain_failure_is_sanitized() -> None:
    runner = FakeSecurityRunner()
    runner.fail_operation = "add-generic-password"
    store = KeychainCredentialStore(runner=runner)

    with pytest.raises(KeychainCredentialError) as caught:
        store.save("alice", _provider())

    assert "keychain-secret-value" not in str(caught.value)
    assert "security failed" not in str(caught.value)


@pytest.mark.parametrize("user_id", ("", "a" * 129))
def test_keychain_rejects_invalid_account_identity(user_id: str) -> None:
    store = KeychainCredentialStore(runner=FakeSecurityRunner())

    with pytest.raises(ValueError, match="user id"):
        store.load(user_id)
