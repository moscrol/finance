"""Build and audit a no-gold instruction export from immutable Git objects."""

from __future__ import annotations

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
    scan_export,
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
- Give a direct Chinese answer with evidence, uncertainty, continuation conditions,
  and invalidation conditions when relevant.
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


def _included(path: str) -> bool:
    if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    return any(
        path == prefix.rstrip("/") or path.startswith(prefix)
        for prefix in INCLUDE_PREFIXES
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
    input_payload = {
        "source_revision": resolved_revision,
        "include_prefixes": list(INCLUDE_PREFIXES),
        "exclude_prefixes": list(EXCLUDE_PREFIXES),
        "neutral_agents_sha256": hashlib.sha256(
            NEUTRAL_AGENTS.encode("utf-8")
        ).hexdigest(),
        "forbidden_corpus_sha256": corpus_sha,
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
            if not _included(relative):
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
        leak_scan = scan_export(instruction, corpus)
        scan_payload = leak_scan.to_dict()
        _write_once(
            control / "deterministic-leak-scan.json",
            (json.dumps(scan_payload, ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8"
            ),
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
