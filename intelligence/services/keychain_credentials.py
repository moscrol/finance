"""macOS Keychain storage for an explicitly persisted Workbench LLM provider."""

from __future__ import annotations

from collections.abc import Callable
import ipaddress
import json
import re
import subprocess
from urllib.parse import urlsplit, urlunsplit

from intelligence.services.llm_refine import LLMProvider


DEFAULT_KEYCHAIN_SERVICE = "com.foresight.workbench.llm"
_SECURITY_BIN = "/usr/bin/security"
_ALLOWED_PROVIDERS = frozenset(
    {"zhipu", "openai", "deepseek", "moonshot", "dashscope"}
)
_MODEL_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")


class KeychainCredentialError(RuntimeError):
    """A sanitized Keychain operation or record validation failure."""


def normalize_provider_base_url(value: str) -> str:
    """Validate a user-selected model endpoint without retaining URL secrets."""

    cleaned = str(value or "").strip().rstrip("/")
    if not cleaned:
        raise ValueError("provider base URL must not be blank")
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("provider base URL must use http or https")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("provider base URL must not contain credentials or query data")
    if parsed.scheme == "http":
        host = parsed.hostname.lower()
        is_loopback = host == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                is_loopback = False
        if not is_loopback:
            raise ValueError("provider base URL requires https outside loopback")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("provider base URL has an invalid port") from exc
    hostname = parsed.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path or "", "", ""))


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class KeychainCredentialStore:
    """Persist provider settings with the secret supplied only through stdin."""

    def __init__(
        self,
        *,
        service: str = DEFAULT_KEYCHAIN_SERVICE,
        runner: CommandRunner = subprocess.run,
        security_bin: str = _SECURITY_BIN,
        timeout: float = 10.0,
    ) -> None:
        cleaned_service = str(service or "").strip()
        if not cleaned_service:
            raise ValueError("keychain service must not be blank")
        self.service = cleaned_service
        self._runner = runner
        self._security_bin = security_bin
        self._timeout = max(0.1, float(timeout))

    def __repr__(self) -> str:
        return f"KeychainCredentialStore(service={self.service!r})"

    def save(self, user_id: str, provider: LLMProvider) -> None:
        account = self._account(user_id)
        payload = json.dumps(
            {
                "schema_version": 1,
                "provider": provider.name,
                "api_key": provider.api_key,
                "base_url": normalize_provider_base_url(provider.base_url),
                "model": provider.model,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        args = [
            self._security_bin,
            "add-generic-password",
            "-U",
            "-a",
            account,
            "-s",
            self.service,
            "-l",
            "Foresight Workbench model",
            "-w",
        ]
        result = self._run(args, input=f"{payload}\n{payload}\n")
        if result.returncode != 0:
            raise KeychainCredentialError("unable to save Keychain credential")

    def load(self, user_id: str) -> LLMProvider | None:
        account = self._account(user_id)
        result = self._run(
            [
                self._security_bin,
                "find-generic-password",
                "-a",
                account,
                "-s",
                self.service,
                "-w",
            ]
        )
        if result.returncode == 44:
            return None
        if result.returncode != 0:
            raise KeychainCredentialError("unable to read Keychain credential")
        try:
            value = json.loads(result.stdout.strip())
            if not isinstance(value, dict):
                raise ValueError("record must be an object")
            provider_name = str(value.get("provider") or "").strip()
            api_key = str(value.get("api_key") or "").strip()
            base_url = normalize_provider_base_url(
                str(value.get("base_url") or "")
            )
            model = str(value.get("model") or "").strip()
            if provider_name not in _ALLOWED_PROVIDERS:
                raise ValueError("unsupported provider")
            if not 8 <= len(api_key) <= 4096:
                raise ValueError("invalid key")
            if not _MODEL_RE.fullmatch(model):
                raise ValueError("invalid model")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise KeychainCredentialError("invalid saved credential") from exc
        return LLMProvider(
            name=provider_name,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

    def delete(self, user_id: str) -> None:
        account = self._account(user_id)
        result = self._run(
            [
                self._security_bin,
                "delete-generic-password",
                "-a",
                account,
                "-s",
                self.service,
            ]
        )
        if result.returncode not in {0, 44}:
            raise KeychainCredentialError("unable to delete Keychain credential")

    def _run(
        self,
        args: list[str],
        *,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return self._runner(
                args,
                input=input,
                text=True,
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise KeychainCredentialError("Keychain command unavailable") from exc

    @staticmethod
    def _account(user_id: str) -> str:
        account = str(user_id or "").strip()
        if not account or len(account) > 128:
            raise ValueError("keychain user id must contain 1-128 characters")
        return account


__all__ = [
    "DEFAULT_KEYCHAIN_SERVICE",
    "KeychainCredentialError",
    "KeychainCredentialStore",
    "normalize_provider_base_url",
]
