"""Lightweight, read-only identity checks for a managed KB RAG consumer.

The knowledge-base repository remains the authority for full manifest validation.
This module only pins the already-approved consumer binding and checks small
identity metadata.  It deliberately never imports KB runtime code, scans an
index, loads a model, or mutates the generation root.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


MARKER = ".rag-generation.json"
MANAGED_CORE_KEYS = (
    "KB_RAG_GENERATION",
    "RAG_GENERATION_MANIFEST",
    "RAG_GENERATIONS_ROOT",
)
MANAGED_BINDING_KEYS = MANAGED_CORE_KEYS + (
    "KB_RAG_CODE_ROOT",
    "KB_RAG_PYTHON",
    "KB_VAULT",
    "RAG_INDEX_DIR",
    "KB_RAG_FULL_INDEX_DIR",
)


class RagGenerationUnavailable(RuntimeError):
    """The worker's pinned managed generation can no longer be consumed."""

    def __init__(self, message: str, *, reason: str, status: str = "invalid") -> None:
        super().__init__(message)
        self.reason = reason
        self.status = status


@dataclass(frozen=True)
class GenerationCheck:
    available: bool
    status: str
    reason: str | None = None


def _read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def _identity(path: Path) -> tuple[int, int]:
    value = path.stat()
    return value.st_dev, value.st_ino


def _link_identity(path: Path) -> tuple[int, int]:
    value = path.lstat()
    return value.st_dev, value.st_ino


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(Path(path).expanduser()))


def _has_symlink_component(path: Path) -> bool:
    path = _absolute(path)
    for candidate in (path, *path.parents):
        try:
            if stat.S_ISLNK(candidate.lstat().st_mode):
                return True
        except FileNotFoundError:
            continue
    return False


def _same_path(left: Path | str, right: Path | str) -> bool:
    return _absolute(left).resolve(strict=False) == _absolute(right).resolve(strict=False)


def _managed_marker(path: Path) -> Path | None:
    resolved = _absolute(path).resolve(strict=False)
    for candidate in (resolved, *resolved.parents):
        marker = candidate / MARKER
        if marker.exists():
            return marker
    return None


def _unavailable(reason: str, *, status: str = "invalid") -> RagGenerationUnavailable:
    messages = {
        "managed_binding_incomplete": "managed generation binding is incomplete",
        "managed_index_without_binding": "managed index requires a complete generation binding",
        "managed_binding_mismatch": "managed generation binding does not match its manifest",
        "managed_binding_alias": "managed generation binding contains a symlink or alias",
        "managed_identity_io_error": "managed generation identity could not be read",
        "manifest_missing": "managed generation manifest is missing",
        "manifest_changed": "managed generation manifest changed",
        "generation_root_replaced": "managed generation root was replaced",
        "generation_directory_replaced": "managed generation directory was replaced",
        "code_root_replaced": "managed generation code root was replaced",
        "source_root_replaced": "managed generation source root was replaced",
        "index_directory_replaced": "managed generation index directory was replaced",
        "interpreter_replaced": "managed generation interpreter was replaced",
        "marker_changed": "managed generation marker changed",
        "current_missing": "managed generation current pointer is missing",
        "current_invalid": "managed generation current pointer is invalid",
        "current_generation_changed": "worker generation retired",
        "environment_changed": "managed generation environment changed",
    }
    return RagGenerationUnavailable(messages.get(reason, reason), reason=reason, status=status)


@dataclass(frozen=True)
class FrozenRagGeneration:
    managed: bool
    environment: tuple[tuple[str, str], ...] = ()
    launch_environment: tuple[tuple[str, str], ...] = ()
    generation: str | None = None
    manifest_sha256: str | None = None
    root: Path | None = None
    manifest: Path | None = None
    marker: Path | None = None
    paths: tuple[tuple[str, Path], ...] = ()
    identities: tuple[tuple[str, tuple[int, int]], ...] = ()

    @property
    def pool_identity(self) -> tuple[object, ...]:
        if not self.managed:
            return ("legacy",)
        return (
            "managed",
            self.generation,
            self.manifest_sha256,
            str(self.root),
            self.environment,
        )

    def _check(self) -> GenerationCheck:
        if not self.managed:
            return GenerationCheck(True, "legacy")

        paths = dict(self.paths)
        identities = dict(self.identities)
        root = self.root
        manifest = self.manifest
        marker = self.marker
        assert root is not None and manifest is not None and marker is not None

        try:
            if _has_symlink_component(root) or _identity(root) != identities["root"]:
                return GenerationCheck(False, "invalid", "generation_root_replaced")
        except (OSError, ValueError):
            return GenerationCheck(False, "invalid", "generation_root_replaced")

        try:
            if not manifest.is_file():
                return GenerationCheck(False, "invalid", "manifest_missing")
            if _has_symlink_component(manifest):
                return GenerationCheck(False, "invalid", "manifest_changed")
            manifest_bytes = manifest.read_bytes()
            if (
                _identity(manifest) != identities["manifest"]
                or hashlib.sha256(manifest_bytes).hexdigest() != self.manifest_sha256
            ):
                return GenerationCheck(False, "invalid", "manifest_changed")
        except OSError:
            return GenerationCheck(False, "invalid", "manifest_missing")

        reasons = {
            "candidate": "generation_directory_replaced",
            "code": "code_root_replaced",
            "source": "source_root_replaced",
            "wiki": "source_root_replaced",
            "standard": "index_directory_replaced",
            "full": "index_directory_replaced",
            "python": "interpreter_replaced",
            "python_entry": "interpreter_replaced",
        }
        for name, path in paths.items():
            try:
                if name == "python_entry":
                    if (
                        _link_identity(path) != identities[name]
                        or path.resolve(strict=True) != paths["python"]
                    ):
                        return GenerationCheck(False, "invalid", reasons[name])
                    continue
                if _has_symlink_component(path) or _identity(path) != identities[name]:
                    return GenerationCheck(False, "invalid", reasons[name])
            except OSError:
                return GenerationCheck(False, "invalid", reasons[name])

        try:
            if _read_object(marker) != {"root": str(root), "generation": self.generation}:
                return GenerationCheck(False, "invalid", "marker_changed")
        except (OSError, ValueError, json.JSONDecodeError):
            return GenerationCheck(False, "invalid", "marker_changed")

        current = root / "current.json"
        try:
            if _has_symlink_component(current) or not current.is_file():
                return GenerationCheck(False, "invalid", "current_missing")
            pointer = _read_object(current)
        except FileNotFoundError:
            return GenerationCheck(False, "invalid", "current_missing")
        except (OSError, ValueError, json.JSONDecodeError):
            return GenerationCheck(False, "invalid", "current_invalid")
        if pointer.get("generation") != self.generation:
            return GenerationCheck(False, "retired", "current_generation_changed")
        if pointer.get("manifest_sha256") != self.manifest_sha256:
            return GenerationCheck(False, "retired", "current_generation_changed")

        return GenerationCheck(True, "current")

    def check(self) -> GenerationCheck:
        return self._check()

    def require_available(self) -> None:
        result = self._check()
        if not result.available:
            assert result.reason is not None
            raise _unavailable(result.reason, status=result.status)

    def child_environment(self) -> dict[str, str] | None:
        if not self.managed:
            return None
        return dict(self.launch_environment)


def _capture_generation_unchecked(
    python: str,
    kb_root: Path,
    index_dir: Path,
    kb_wiki: Path | None,
    *,
    environment: Mapping[str, str] | None = None,
) -> FrozenRagGeneration:
    env = dict(os.environ if environment is None else environment)
    present = {key for key in MANAGED_CORE_KEYS if env.get(key)}
    if present and present != set(MANAGED_CORE_KEYS):
        raise _unavailable("managed_binding_incomplete")
    if not present:
        if _managed_marker(index_dir) is not None:
            raise _unavailable("managed_index_without_binding")
        return FrozenRagGeneration(managed=False)
    if any(not env.get(key) for key in MANAGED_BINDING_KEYS):
        raise _unavailable("managed_binding_incomplete")

    manifest = _absolute(env["RAG_GENERATION_MANIFEST"])
    root = _absolute(env["RAG_GENERATIONS_ROOT"])
    if _has_symlink_component(manifest) or _has_symlink_component(root):
        raise _unavailable("managed_binding_alias")
    try:
        manifest_bytes = manifest.read_bytes()
        data = json.loads(manifest_bytes)
    except FileNotFoundError as exc:
        raise _unavailable("manifest_missing") from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise _unavailable("manifest_changed") from exc
    if not isinstance(data, dict):
        raise _unavailable("manifest_changed")
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    generation = data.get("generation")
    if not isinstance(generation, str) or not generation:
        raise _unavailable("managed_binding_mismatch")
    candidate = root / "generations" / generation
    expected_manifest = candidate / "manifest.json"
    source = candidate / "source"
    sources = data.get("sources")
    indexes = data.get("indexes")
    runtime = data.get("runtime")
    if not all(isinstance(value, dict) for value in (sources, indexes, runtime)):
        raise _unavailable("managed_binding_mismatch")
    assert isinstance(sources, dict) and isinstance(indexes, dict)
    assert isinstance(runtime, dict)
    standard_contract = indexes.get("standard")
    full_contract = indexes.get("full")
    if not isinstance(standard_contract, dict) or not isinstance(full_contract, dict):
        raise _unavailable("managed_binding_mismatch")
    wiki_name = sources.get("wiki_name")
    executable = runtime.get("executable")
    standard_path = standard_contract.get("path")
    full_path = full_contract.get("path")
    if not all(
        isinstance(value, str) and value
        for value in (wiki_name, executable, standard_path, full_path)
    ):
        raise _unavailable("managed_binding_mismatch")
    expected = {
        "KB_RAG_GENERATION": manifest_sha,
        "RAG_GENERATION_MANIFEST": str(expected_manifest),
        "RAG_GENERATIONS_ROOT": str(root),
        "KB_RAG_CODE_ROOT": str(candidate / "code"),
        "KB_RAG_PYTHON": executable,
        "KB_VAULT": str(source / wiki_name),
        "RAG_INDEX_DIR": standard_path,
        "KB_RAG_FULL_INDEX_DIR": full_path,
    }
    actual_directories = (kb_root, index_dir) + (() if kb_wiki is None else (kb_wiki,))
    if any(_has_symlink_component(path) for path in actual_directories):
        raise _unavailable("managed_binding_alias")
    if (
        data.get("root") != str(root)
        or any(env.get(key) != value for key, value in expected.items())
        or not _same_path(manifest, expected_manifest)
        or _absolute(python) != _absolute(expected["KB_RAG_PYTHON"])
        or not _same_path(kb_root, expected["KB_RAG_CODE_ROOT"])
        or not _same_path(index_dir, expected["RAG_INDEX_DIR"])
        and not _same_path(index_dir, expected["KB_RAG_FULL_INDEX_DIR"])
        or kb_wiki is None
        or not _same_path(kb_wiki, expected["KB_VAULT"])
    ):
        raise _unavailable("managed_binding_mismatch")

    marker = candidate / MARKER
    try:
        if _read_object(marker) != {"root": str(root), "generation": generation}:
            raise _unavailable("marker_changed")
    except RagGenerationUnavailable:
        raise
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise _unavailable("marker_changed") from exc

    try:
        python_target = _absolute(expected["KB_RAG_PYTHON"]).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _unavailable("interpreter_replaced") from exc
    paths = {
        "candidate": candidate,
        "code": candidate / "code",
        "source": source,
        "wiki": Path(expected["KB_VAULT"]),
        "standard": Path(expected["RAG_INDEX_DIR"]),
        "full": Path(expected["KB_RAG_FULL_INDEX_DIR"]),
        "python_entry": _absolute(expected["KB_RAG_PYTHON"]),
        "python": python_target,
    }
    declared = data.get("path_identities") or {}
    if not isinstance(declared, dict):
        raise _unavailable("managed_binding_mismatch")
    reasons = {
        "candidate": "generation_directory_replaced",
        "code": "code_root_replaced",
        "source": "source_root_replaced",
        "wiki": "source_root_replaced",
        "standard": "index_directory_replaced",
        "full": "index_directory_replaced",
        "python_entry": "interpreter_replaced",
        "python": "interpreter_replaced",
    }
    identities: dict[str, tuple[int, int]] = {}
    for name, path in paths.items():
        try:
            identities[name] = (
                _link_identity(path) if name == "python_entry" else _identity(path)
            )
        except OSError as exc:
            raise _unavailable(reasons[name]) from exc
    for name, manifest_name in (
        ("candidate", "."),
        ("code", "code"),
        ("source", "source"),
        ("standard", "standard"),
        ("full", "full"),
    ):
        if list(identities[name]) != declared.get(manifest_name):
            raise _unavailable("managed_binding_mismatch")
    if any(
        _has_symlink_component(path)
        for name, path in paths.items()
        if name != "python_entry"
    ):
        raise _unavailable("managed_binding_alias")

    try:
        identities.update(root=_identity(root), manifest=_identity(manifest))
    except OSError as exc:
        reason = "generation_root_replaced" if not root.exists() else "manifest_missing"
        raise _unavailable(reason) from exc
    return FrozenRagGeneration(
        managed=True,
        environment=tuple((key, expected[key]) for key in MANAGED_BINDING_KEYS),
        launch_environment=tuple(env.items()),
        generation=generation,
        manifest_sha256=manifest_sha,
        root=root,
        manifest=manifest,
        marker=marker,
        paths=tuple(paths.items()),
        identities=tuple(identities.items()),
    )


def capture_generation(
    python: str,
    kb_root: Path,
    index_dir: Path,
    kb_wiki: Path | None,
    *,
    environment: Mapping[str, str] | None = None,
) -> FrozenRagGeneration:
    env = dict(os.environ if environment is None else environment)
    complete_managed_binding = all(env.get(key) for key in MANAGED_CORE_KEYS)
    try:
        return _capture_generation_unchecked(
            python,
            kb_root,
            index_dir,
            kb_wiki,
            environment=env,
        )
    except RagGenerationUnavailable:
        raise
    except OSError as exc:
        if complete_managed_binding:
            raise _unavailable("managed_identity_io_error") from exc
        raise
