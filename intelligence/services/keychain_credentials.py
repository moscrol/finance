"""macOS Keychain storage for an explicitly persisted Workbench LLM provider."""

from __future__ import annotations

import ctypes
import ipaddress
import json
import re
import subprocess
import sys
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from intelligence.services.llm_refine import LLMProvider


DEFAULT_KEYCHAIN_SERVICE = "com.foresight.workbench.llm"
_ALLOWED_PROVIDERS = frozenset(
    {"zhipu", "openai", "deepseek", "moonshot", "dashscope"}
)
_MODEL_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")


class KeychainCredentialError(RuntimeError):
    """A sanitized Keychain operation or record validation failure."""


class KeychainBackend(Protocol):
    def save(self, *, service: str, account: str, label: str, payload: bytes) -> None: ...
    def load(self, *, service: str, account: str) -> bytes | None: ...
    def delete(self, *, service: str, account: str) -> None: ...


class MacOSKeychainBackend:
    """Call Keychain Services directly so secrets never enter process argv."""

    _ERR_SUCCESS = 0
    _ERR_DUPLICATE_ITEM = -25299
    _ERR_ITEM_NOT_FOUND = -25300
    _UTF8_ENCODING = 0x08000100

    def __init__(self) -> None:
        if sys.platform != "darwin":
            raise KeychainCredentialError("macOS Keychain unavailable")
        try:
            self._cf = ctypes.CDLL(
                "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
            )
            self._security = ctypes.CDLL(
                "/System/Library/Frameworks/Security.framework/Security"
            )
            self._configure_functions()
            self._constants = {
                name: self._symbol(self._security, name)
                for name in (
                    "kSecClass",
                    "kSecClassGenericPassword",
                    "kSecAttrAccount",
                    "kSecAttrService",
                    "kSecAttrLabel",
                    "kSecValueData",
                    "kSecReturnData",
                    "kSecMatchLimit",
                    "kSecMatchLimitOne",
                )
            }
            self._true = self._symbol(self._cf, "kCFBooleanTrue")
            self._key_callbacks = ctypes.addressof(
                ctypes.c_byte.in_dll(
                    self._cf, "kCFTypeDictionaryKeyCallBacks"
                )
            )
            self._value_callbacks = ctypes.addressof(
                ctypes.c_byte.in_dll(
                    self._cf, "kCFTypeDictionaryValueCallBacks"
                )
            )
        except (AttributeError, OSError, ValueError) as exc:
            raise KeychainCredentialError("macOS Keychain unavailable") from exc

    def save(
        self,
        *,
        service: str,
        account: str,
        label: str,
        payload: bytes,
    ) -> None:
        refs: list[int] = []
        try:
            service_ref = self._string(service, refs)
            account_ref = self._string(account, refs)
            label_ref = self._string(label, refs)
            data_ref = self._data(payload, refs)
            query = self._dictionary(
                (
                    (self._constants["kSecClass"], self._constants["kSecClassGenericPassword"]),
                    (self._constants["kSecAttrService"], service_ref),
                    (self._constants["kSecAttrAccount"], account_ref),
                ),
                refs,
            )
            updates = self._dictionary(
                (
                    (self._constants["kSecValueData"], data_ref),
                    (self._constants["kSecAttrLabel"], label_ref),
                ),
                refs,
            )
            status = self._security.SecItemUpdate(query, updates)
            if status == self._ERR_ITEM_NOT_FOUND:
                add_query = self._dictionary(
                    (
                        (self._constants["kSecClass"], self._constants["kSecClassGenericPassword"]),
                        (self._constants["kSecAttrService"], service_ref),
                        (self._constants["kSecAttrAccount"], account_ref),
                        (self._constants["kSecAttrLabel"], label_ref),
                        (self._constants["kSecValueData"], data_ref),
                    ),
                    refs,
                )
                status = self._security.SecItemAdd(add_query, None)
                if status == self._ERR_DUPLICATE_ITEM:
                    status = self._security.SecItemUpdate(query, updates)
            if status != self._ERR_SUCCESS:
                raise KeychainCredentialError("unable to save Keychain credential")
        finally:
            self._release(refs)

    def load(self, *, service: str, account: str) -> bytes | None:
        try:
            result = subprocess.run(
                [
                    "/usr/bin/security",
                    "find-generic-password",
                    "-s",
                    service,
                    "-a",
                    account,
                    "-w",
                ],
                check=False,
                capture_output=True,
                timeout=3.0,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise KeychainCredentialError(
                "unable to read Keychain credential"
            ) from exc
        if result.returncode == 44:
            return None
        if result.returncode != 0:
            raise KeychainCredentialError("unable to read Keychain credential")
        payload = result.stdout.rstrip(b"\r\n")
        if not payload:
            raise KeychainCredentialError("unable to read Keychain credential")
        return payload

    def delete(self, *, service: str, account: str) -> None:
        refs: list[int] = []
        try:
            service_ref = self._string(service, refs)
            account_ref = self._string(account, refs)
            query = self._dictionary(
                (
                    (self._constants["kSecClass"], self._constants["kSecClassGenericPassword"]),
                    (self._constants["kSecAttrService"], service_ref),
                    (self._constants["kSecAttrAccount"], account_ref),
                ),
                refs,
            )
            status = self._security.SecItemDelete(query)
            if status not in {self._ERR_SUCCESS, self._ERR_ITEM_NOT_FOUND}:
                raise KeychainCredentialError("unable to delete Keychain credential")
        finally:
            self._release(refs)

    def _configure_functions(self) -> None:
        void_p = ctypes.c_void_p
        self._cf.CFStringCreateWithCString.argtypes = [
            void_p,
            ctypes.c_char_p,
            ctypes.c_uint32,
        ]
        self._cf.CFStringCreateWithCString.restype = void_p
        self._cf.CFDataCreate.argtypes = [
            void_p,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_long,
        ]
        self._cf.CFDataCreate.restype = void_p
        self._cf.CFDictionaryCreateMutable.argtypes = [
            void_p,
            ctypes.c_long,
            void_p,
            void_p,
        ]
        self._cf.CFDictionaryCreateMutable.restype = void_p
        self._cf.CFDictionarySetValue.argtypes = [void_p, void_p, void_p]
        self._cf.CFDictionarySetValue.restype = None
        self._cf.CFDataGetLength.argtypes = [void_p]
        self._cf.CFDataGetLength.restype = ctypes.c_long
        self._cf.CFDataGetBytePtr.argtypes = [void_p]
        self._cf.CFDataGetBytePtr.restype = ctypes.POINTER(ctypes.c_uint8)
        self._cf.CFRelease.argtypes = [void_p]
        self._cf.CFRelease.restype = None
        self._security.SecItemAdd.argtypes = [
            void_p,
            ctypes.POINTER(void_p),
        ]
        self._security.SecItemAdd.restype = ctypes.c_int32
        self._security.SecItemUpdate.argtypes = [void_p, void_p]
        self._security.SecItemUpdate.restype = ctypes.c_int32
        self._security.SecItemCopyMatching.argtypes = [
            void_p,
            ctypes.POINTER(void_p),
        ]
        self._security.SecItemCopyMatching.restype = ctypes.c_int32
        self._security.SecItemDelete.argtypes = [void_p]
        self._security.SecItemDelete.restype = ctypes.c_int32

    @staticmethod
    def _symbol(library: ctypes.CDLL, name: str) -> int:
        value = ctypes.c_void_p.in_dll(library, name).value
        if value is None:
            raise KeychainCredentialError("macOS Keychain unavailable")
        return value

    def _string(self, value: str, refs: list[int]) -> int:
        result = self._cf.CFStringCreateWithCString(
            None,
            value.encode("utf-8"),
            self._UTF8_ENCODING,
        )
        if not result:
            raise KeychainCredentialError("invalid Keychain attribute")
        refs.append(result)
        return result

    def _data(self, value: bytes, refs: list[int]) -> int:
        buffer = (ctypes.c_uint8 * len(value)).from_buffer_copy(value)
        result = self._cf.CFDataCreate(None, buffer, len(value))
        if not result:
            raise KeychainCredentialError("invalid Keychain payload")
        refs.append(result)
        return result

    def _dictionary(
        self,
        pairs: tuple[tuple[int, int], ...],
        refs: list[int],
    ) -> int:
        result = self._cf.CFDictionaryCreateMutable(
            None,
            0,
            self._key_callbacks,
            self._value_callbacks,
        )
        if not result:
            raise KeychainCredentialError("unable to create Keychain query")
        refs.append(result)
        for key, value in pairs:
            self._cf.CFDictionarySetValue(result, key, value)
        return result

    def _release(self, refs: list[int]) -> None:
        for ref in reversed(refs):
            self._cf.CFRelease(ref)


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


class KeychainCredentialStore:
    """Persist provider settings through a replaceable native secret backend."""

    def __init__(
        self,
        *,
        service: str = DEFAULT_KEYCHAIN_SERVICE,
        backend: KeychainBackend | None = None,
    ) -> None:
        cleaned_service = str(service or "").strip()
        if not cleaned_service:
            raise ValueError("keychain service must not be blank")
        self.service = cleaned_service
        self._backend = backend or MacOSKeychainBackend()

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
        ).encode("utf-8")
        try:
            self._backend.save(
                service=self.service,
                account=account,
                label="Foresight Workbench model",
                payload=payload,
            )
        except KeychainCredentialError as exc:
            raise KeychainCredentialError(
                "unable to save Keychain credential"
            ) from exc

    def load(self, user_id: str) -> LLMProvider | None:
        account = self._account(user_id)
        try:
            payload = self._backend.load(service=self.service, account=account)
        except KeychainCredentialError as exc:
            raise KeychainCredentialError(
                "unable to read Keychain credential"
            ) from exc
        if payload is None:
            return None
        try:
            value = json.loads(payload.decode("utf-8"))
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
        except (TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            raise KeychainCredentialError("invalid saved credential") from exc
        return LLMProvider(
            name=provider_name,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

    def delete(self, user_id: str) -> None:
        account = self._account(user_id)
        try:
            self._backend.delete(service=self.service, account=account)
        except KeychainCredentialError as exc:
            raise KeychainCredentialError(
                "unable to delete Keychain credential"
            ) from exc

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
    "MacOSKeychainBackend",
    "normalize_provider_base_url",
]
