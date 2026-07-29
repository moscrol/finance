"""Build and audit a no-gold instruction export from immutable Git objects."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Literal

from intelligence.eval.ceiling_leakage import (
    ForbiddenCorpus,
    LeakScanResult,
    build_leak_diagnostic,
    scan_export,
    validate_leak_diagnostic,
)


INCLUDE_PREFIXES = (
    "intelligence/services/",
    "intelligence/workbench_skills/",
    "intelligence/README.md",
    "skills/",
    "UBIQUITOUS_LANGUAGE.md",
)
EXCLUDE_PREFIXES = (
    ".git/",
    ".agent-memory/",
    "tmp/",
    "docs/",
    "intelligence/eval/",
    "intelligence/tests/",
)
NEUTRAL_AGENTS = """# Sealed Finance Research Instructions

- Work read-only. Do not edit files, use Git, or persist memory.
- Treat the supplied as_of date as an immutable point-in-time cutoff.
- Use the local finance-tool command for financial and knowledge evidence.
- Do not access external web, apps, plugins, MCP, browser, or other agents.
- Give a direct Chinese answer with evidence and uncertainty. Explain what new
  evidence would justify continuing and what would invalidate the conclusion.
- If evidence is unavailable, report the precise gap instead of guessing.
"""


def _canonical_sha(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_git(repo: Path, arguments: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
    )


def _read_git_blobs(repo: Path, object_ids: tuple[str, ...]) -> dict[str, bytes]:
    if not object_ids:
        return {}
    process = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        input=("\n".join(object_ids) + "\n").encode("ascii"),
        check=True,
        capture_output=True,
    )
    output = memoryview(process.stdout)
    offset = 0
    blobs: dict[str, bytes] = {}
    for expected in object_ids:
        newline = process.stdout.find(b"\n", offset)
        if newline < 0:
            raise ValueError("git cat-file batch header is truncated")
        header = bytes(output[offset:newline]).decode("ascii").split(" ")
        if len(header) != 3 or header[0] != expected or header[1] != "blob":
            raise ValueError("git cat-file batch returned an unexpected object")
        size = int(header[2])
        start = newline + 1
        end = start + size
        if end >= len(output) or process.stdout[end : end + 1] != b"\n":
            raise ValueError("git cat-file batch payload is truncated")
        blobs[expected] = bytes(output[start:end])
        offset = end + 1
    return blobs


def _included(
    path: str,
    *,
    include_prefixes: Sequence[str],
    include_files: frozenset[str],
) -> bool:
    if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    if path in include_files:
        return True
    return any(
        path == prefix.rstrip("/") or path.startswith(prefix)
        for prefix in include_prefixes
    )


def _write_once(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    try:
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _manifest_payload(value: dict[str, object]) -> dict[str, object]:
    payload = dict(value)
    payload.pop("manifest_sha256", None)
    return payload


def _receipt_payload(value: dict[str, object], hash_field: str) -> dict[str, object]:
    payload = dict(value)
    payload.pop(hash_field, None)
    return payload


@dataclass(frozen=True)
class InstructionExportAudit:
    status: Literal["valid", "invalid"]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class InstructionExportReceipt:
    component_root: Path
    instruction_root: Path
    manifest_sha256: str
    leak_scan: LeakScanResult


def _load_scan(value: object) -> LeakScanResult:
    if not isinstance(value, dict):
        raise ValueError("leak scan receipt must be an object")
    from intelligence.eval.ceiling_leakage import (  # local to avoid export surface
        LeakFinding,
        SemanticLeakCandidate,
    )

    return LeakScanResult(
        status=str(value.get("status") or "rejected"),  # type: ignore[arg-type]
        files_scanned=int(value.get("files_scanned") or 0),
        findings=tuple(
            LeakFinding(
                relative_path=str(item.get("relative_path") or ""),
                source_id=str(item.get("source_id") or ""),
                rule=str(item.get("rule") or "full_normalized_match"),  # type: ignore[arg-type]
                sentence_sha256=str(item.get("sentence_sha256") or ""),
            )
            for item in value.get("findings", ())
            if isinstance(item, dict)
        ),
        semantic_candidates=tuple(
            SemanticLeakCandidate(
                relative_path=str(item.get("relative_path") or ""),
                source_id=str(item.get("source_id") or ""),
                sentence=str(item.get("sentence") or ""),
                token_jaccard=float(item.get("token_jaccard") or 0.0),
            )
            for item in value.get("semantic_candidates", ())
            if isinstance(item, dict)
        ),
        generic_exception_source_ids=tuple(
            str(item)
            for item in value.get("generic_exception_source_ids", ())
            if str(item).strip()
        ),
        scan_sha256=str(value.get("scan_sha256") or ""),
    )


def _receipt_from_root(component_root: Path) -> InstructionExportReceipt:
    manifest = json.loads(
        (component_root / "control" / "instruction-export.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    scan = _load_scan(
        json.loads(
            (component_root / "control" / "deterministic-leak-scan.json").read_text(
                encoding="utf-8"
            )
        )
    )
    return InstructionExportReceipt(
        component_root=component_root,
        instruction_root=component_root / "instruction",
        manifest_sha256=str(manifest.get("manifest_sha256") or ""),
        leak_scan=scan,
    )


def audit_instruction_export(
    component_root: str | Path,
    *,
    expected_manifest_sha256: str,
) -> InstructionExportAudit:
    root = Path(component_root)
    issues: list[str] = []
    try:
        manifest = json.loads(
            (root / "control" / "instruction-export.manifest.json").read_text(
                encoding="utf-8"
            )
        )
        scan_value = json.loads(
            (root / "control" / "deterministic-leak-scan.json").read_text(
                encoding="utf-8"
            )
        )
        exception_value = json.loads(
            (root / "control" / "generic-leak-exceptions.json").read_text(
                encoding="utf-8"
            )
        )
        diagnostic_value = json.loads(
            (root / "control" / "leak-diagnostic.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return InstructionExportAudit("invalid", ("control_receipt_unreadable",))
    manifest_sha = str(manifest.get("manifest_sha256") or "")
    if manifest_sha != expected_manifest_sha256:
        issues.append("manifest_hash_mismatch")
    if manifest_sha != _canonical_sha(_manifest_payload(manifest)):
        issues.append("manifest_self_hash_mismatch")
    scan = _load_scan(scan_value)
    if scan.status != "passed":
        issues.append("deterministic_leak_scan_failed")
    scan_payload = scan.to_dict()
    scan_payload.pop("scan_sha256", None)
    if scan.scan_sha256 != _canonical_sha(scan_payload):
        issues.append("deterministic_scan_self_hash_mismatch")
    if scan.scan_sha256 != manifest.get("deterministic_scan_sha256"):
        issues.append("deterministic_scan_hash_mismatch")
    if not isinstance(exception_value, dict):
        issues.append("generic_exception_receipt_invalid")
        exception_value = {}
    exception_sha = str(exception_value.get("manifest_sha256") or "")
    if exception_sha != _canonical_sha(
        _receipt_payload(exception_value, "manifest_sha256")
    ):
        issues.append("generic_exception_self_hash_mismatch")
    if exception_sha != manifest.get("generic_exception_manifest_sha256"):
        issues.append("generic_exception_manifest_hash_mismatch")
    exception_entries = exception_value.get("exceptions")
    exception_ids = tuple(
        str(item.get("source_id") or "")
        for item in exception_entries
        if isinstance(item, dict)
    ) if isinstance(exception_entries, list) else ()
    if tuple(sorted(exception_ids)) != tuple(sorted(scan.generic_exception_source_ids)):
        issues.append("generic_exception_scan_mismatch")
    try:
        diagnostic = validate_leak_diagnostic(
            diagnostic_value,
            expected_scan_sha256=scan.scan_sha256,
        )
    except ValueError:
        issues.append("leak_diagnostic_invalid")
    else:
        if diagnostic.diagnostic_sha256 != manifest.get(
            "leak_diagnostic_sha256"
        ):
            issues.append("leak_diagnostic_hash_mismatch")
    instruction = root / "instruction"
    if (instruction / ".git").exists():
        issues.append("git_directory_present")
    expected_paths: set[str] = set()
    files = manifest.get("files")
    if not isinstance(files, list):
        issues.append("manifest_files_invalid")
        files = []
    for entry in files:
        if not isinstance(entry, dict):
            issues.append("manifest_file_entry_invalid")
            continue
        relative = str(entry.get("path") or "")
        expected_paths.add(relative)
        path = instruction / relative
        if path.is_symlink() or not path.is_file():
            issues.append(f"non_regular:{relative}")
            continue
        if path.stat().st_nlink != 1:
            issues.append(f"hardlink:{relative}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry.get("sha256"):
            issues.append(f"content_hash:{relative}")
        if path.stat().st_mode & 0o777 != int(entry.get("mode") or 0):
            issues.append(f"mode:{relative}")
    actual_paths = {
        path.relative_to(instruction).as_posix()
        for path in instruction.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual_paths != expected_paths:
        issues.append("file_set_mismatch")
    return InstructionExportAudit(
        "invalid" if issues else "valid",
        tuple(dict.fromkeys(issues)),
    )


def build_instruction_export(
    *,
    source_repo: str | Path,
    source_revision: str,
    output_root: str | Path,
    corpus: ForbiddenCorpus,
    generic_exception_source_ids: Sequence[str] = (),
    include_prefixes: Sequence[str] | None = None,
    include_files: Sequence[str] = (),
) -> InstructionExportReceipt:
    """Export an immutable, leak-scanned instruction tree from one Git commit."""

    repo = Path(source_repo).resolve()
    revision = _run_git(repo, ["rev-parse", f"{source_revision}^{{commit}}"])
    resolved_revision = revision.stdout.decode("utf-8").strip()
    corpus_sha = _canonical_sha(
        [
            {"source_id": item.source_id, "kind": item.kind, "text": item.text}
            for item in corpus.entries
        ]
    )
    selected_prefixes = tuple(
        dict.fromkeys(
            str(item).strip()
            for item in (INCLUDE_PREFIXES if include_prefixes is None else include_prefixes)
            if str(item).strip()
        )
    )
    selected_files = tuple(
        dict.fromkeys(
            str(item).strip()
            for item in include_files
            if str(item).strip()
        )
    )
    if any(
        Path(item).is_absolute() or ".." in Path(item).parts
        for item in (*selected_prefixes, *selected_files)
    ):
        raise ValueError("instruction allowlist paths must stay repository-relative")
    input_payload = {
        "source_revision": resolved_revision,
        "include_prefixes": list(selected_prefixes),
        "include_files": list(selected_files),
        "exclude_prefixes": list(EXCLUDE_PREFIXES),
        "neutral_agents_sha256": hashlib.sha256(
            NEUTRAL_AGENTS.encode("utf-8")
        ).hexdigest(),
        "forbidden_corpus_sha256": corpus_sha,
        "generic_exception_source_ids": sorted(
            {str(item).strip() for item in generic_exception_source_ids if str(item).strip()}
        ),
    }
    component_id = _canonical_sha(input_payload)[:16]
    parent = Path(output_root).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / component_id
    if destination.exists():
        receipt = _receipt_from_root(destination)
        audit = audit_instruction_export(
            destination,
            expected_manifest_sha256=receipt.manifest_sha256,
        )
        if audit.status != "valid":
            raise ValueError("existing instruction export is invalid")
        return receipt

    temporary = Path(tempfile.mkdtemp(prefix=f".{component_id}.", dir=parent))
    instruction = temporary / "instruction"
    control = temporary / "control"
    instruction.mkdir(mode=0o700)
    control.mkdir(mode=0o700)
    try:
        raw_tree = _run_git(repo, ["ls-tree", "-r", "-z", resolved_revision]).stdout
        file_modes: dict[str, int] = {}
        selected: list[tuple[str, str, int]] = []
        for raw_entry in raw_tree.split(b"\0"):
            if not raw_entry:
                continue
            metadata, raw_path = raw_entry.split(b"\t", 1)
            mode, object_type, object_sha = metadata.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8")
            if not _included(
                relative,
                include_prefixes=selected_prefixes,
                include_files=frozenset(selected_files),
            ):
                continue
            if object_type != "blob" or mode not in {"100644", "100755"}:
                raise ValueError("instruction export accepts regular Git blobs only")
            file_mode = 0o555 if mode == "100755" else 0o444
            selected.append((relative, object_sha, file_mode))
        blobs = _read_git_blobs(
            repo,
            tuple(object_sha for _relative, object_sha, _mode in selected),
        )
        for relative, object_sha, file_mode in selected:
            data = blobs[object_sha]
            _write_once(instruction / relative, data, file_mode)
            file_modes[relative] = file_mode
        _write_once(instruction / "AGENTS.md", NEUTRAL_AGENTS.encode("utf-8"), 0o444)
        file_modes["AGENTS.md"] = 0o444
        initial_scan = scan_export(
            instruction,
            corpus,
            generic_exception_source_ids=generic_exception_source_ids,
        )
        corpus_by_id = {item.source_id: item for item in corpus.entries}
        exception_entries = []
        for source_id in initial_scan.generic_exception_source_ids:
            item = corpus_by_id[source_id]
            exception_entries.append(
                {
                    "source_id": item.source_id,
                    "kind": item.kind,
                    "text": item.text,
                    "text_sha256": hashlib.sha256(
                        item.text.encode("utf-8")
                    ).hexdigest(),
                    "reason": "reviewed generic production term below n-gram thresholds",
                }
            )
        exception_receipt: dict[str, object] = {
            "schema_version": 1,
            "exceptions": exception_entries,
        }
        exception_receipt["manifest_sha256"] = _canonical_sha(exception_receipt)
        _write_once(
            control / "generic-leak-exceptions.json",
            (
                json.dumps(exception_receipt, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8"),
            0o600,
        )
        leak_scan = initial_scan
        diagnostic = build_leak_diagnostic(leak_scan, corpus)
        scan_payload = leak_scan.to_dict()
        _write_once(
            control / "deterministic-leak-scan.json",
            (json.dumps(scan_payload, ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8"
            ),
            0o600,
        )
        _write_once(
            control / "leak-diagnostic.json",
            (
                json.dumps(diagnostic.to_dict(), ensure_ascii=False, indent=2)
                + "\n"
            ).encode("utf-8"),
            0o600,
        )
        if leak_scan.status != "passed":
            raise ValueError("instruction export contains forbidden evaluation text")
        files = []
        for relative, file_mode in sorted(file_modes.items()):
            path = instruction / relative
            files.append(
                {
                    "path": relative,
                    "mode": file_mode,
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        manifest: dict[str, object] = {
            "schema_version": 1,
            **input_payload,
            "component_id": component_id,
            "file_count": len(files),
            "files": files,
            "deterministic_scan_sha256": leak_scan.scan_sha256,
            "leak_diagnostic_sha256": diagnostic.diagnostic_sha256,
            "generic_exception_manifest_sha256": exception_receipt[
                "manifest_sha256"
            ],
        }
        manifest["manifest_sha256"] = _canonical_sha(manifest)
        _write_once(
            control / "instruction-export.manifest.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8"
            ),
            0o600,
        )
        for directory in sorted(
            (path for path in instruction.rglob("*") if path.is_dir()),
            reverse=True,
        ):
            directory.chmod(0o555)
        instruction.chmod(0o555)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    receipt = _receipt_from_root(destination)
    audit = audit_instruction_export(
        destination,
        expected_manifest_sha256=receipt.manifest_sha256,
    )
    if audit.status != "valid":
        raise ValueError("new instruction export failed audit")
    return receipt
