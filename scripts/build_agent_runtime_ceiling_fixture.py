#!/usr/bin/env python3
"""Build and seal the private physical fixture for the runtime ceiling experiment."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Literal

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.eval.ceiling_instruction_export import build_instruction_export
from intelligence.eval.ceiling_leakage import (
    build_forbidden_corpus,
    validate_semantic_receipt,
)
from intelligence.eval.ceiling_pit_fixture import (
    build_filtered_duckdb,
    build_true_hybrid_index,
    export_cutoff_wiki,
    select_revision_at_cutoff,
)


SEMANTIC_REVIEW_PROMPT = """Review only the candidate snippets and manifests for semantic leakage.
Fail if the export paraphrases or reveals any frozen question, answer, rubric, expected fact,
required output, prior answer, or post-cutoff result. Generic production vocabulary alone is not
leakage. Return one hash-bound gpt-5.6-sol receipt and do not modify any artifact.
"""
CONTROL_FILES = {
    "component-state.json",
    "semantic-leak-review-request.json",
    "semantic-leak-review-receipt.json",
    "fixture.manifest.json",
}


@dataclass(frozen=True)
class CeilingFixtureConfig:
    source_repo: Path
    source_revision: str
    finance_db: Path
    kb_source_repo: Path
    kb_code_root: Path
    kb_code_revision: str
    kb_rag_python: Path
    question_file: Path
    reference_file: Path
    prior_artifacts: tuple[Path, ...]
    post_cutoff_documents: tuple[Path, ...]
    generic_exception_file: Path | None
    as_of: str
    output_root: Path
    instruction_allowlist_file: Path | None = None
    prebuilt_hybrid_index: Path | None = None


@dataclass(frozen=True)
class FixtureBuildResult:
    status: Literal["dry_run", "semantic_review_pending", "sealed"]
    component_root: Path
    input_sha256: str
    manifest_sha256: str | None = None
    review_request: Path | None = None


def _canonical_sha(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_revision(repo: Path, revision: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"{revision}^{{commit}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _private_output_root(path: Path) -> Path:
    expanded = path.expanduser().absolute()
    if expanded.is_symlink():
        raise ValueError("fixture output root cannot be a symlink")
    if expanded.exists() and not expanded.is_dir():
        raise ValueError("fixture output root must be a directory")
    return expanded.resolve()


def _python_identity(python: Path) -> dict[str, object]:
    distributions = (
        "FlagEmbedding",
        "PyYAML",
        "huggingface-hub",
        "numpy",
        "rank-bm25",
        "safetensors",
        "scikit-learn",
        "scipy",
        "sentence-transformers",
        "tokenizers",
        "torch",
        "transformers",
    )
    code = (
        "import importlib.metadata as m,json,sys\n"
        f"names={distributions!r}\n"
        "packages={}\n"
        "for name in names:\n"
        "    try: packages[name]=m.version(name)\n"
        "    except m.PackageNotFoundError: packages[name]=None\n"
        "print(json.dumps({'executable':sys.executable,'prefix':sys.prefix,"
        "'version':sys.version.split()[0],'packages':packages},sort_keys=True))\n"
    )
    value = json.loads(
        subprocess.run(
            [str(python), "-c", code],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    )
    packages = value.get("packages")
    if not isinstance(packages, dict) or any(
        not isinstance(name, str)
        or not name
        or (version is not None and not isinstance(version, str))
        for name, version in packages.items()
    ):
        raise ValueError("RAG Python dependency probe returned invalid packages")
    identity: dict[str, object] = {
        key: str(value.get(key) or "")
        for key in ("executable", "prefix", "version")
    }
    identity["packages"] = {
        name: packages[name]
        for name in sorted(packages)
    }
    identity["dependency_fingerprint_sha256"] = _canonical_sha(
        {
            "python_version": identity["version"],
            "packages": identity["packages"],
        }
    )
    return identity


def _input_payload(config: CeilingFixtureConfig) -> dict[str, object]:
    source_repo = config.source_repo.expanduser().resolve()
    finance_db = config.finance_db.expanduser().resolve()
    kb_source = config.kb_source_repo.expanduser().resolve()
    code_root = config.kb_code_root.expanduser().resolve()
    python = config.kb_rag_python.expanduser().absolute()
    exception_file = (
        config.generic_exception_file.expanduser().resolve()
        if config.generic_exception_file is not None
        else None
    )
    allowlist_file = (
        config.instruction_allowlist_file.expanduser().resolve()
        if config.instruction_allowlist_file is not None
        else None
    )
    prebuilt_hybrid = (
        _sealed_tree_identity(config.prebuilt_hybrid_index)
        if config.prebuilt_hybrid_index is not None
        else None
    )
    prior_artifacts = tuple(
        path.expanduser().resolve() for path in config.prior_artifacts
    )
    post_cutoff_documents = tuple(
        path.expanduser().resolve() for path in config.post_cutoff_documents
    )
    if not prior_artifacts or not post_cutoff_documents:
        raise ValueError(
            "fixture requires prior artifacts and post-cutoff documents"
        )
    for path in (*prior_artifacts, *post_cutoff_documents):
        if not path.is_file() or path.is_symlink():
            raise ValueError("forbidden corpus sources must be regular files")
    return {
        "schema_version": 1,
        "as_of": config.as_of,
        "source_repo": str(source_repo),
        "source_revision": _git_revision(source_repo, config.source_revision),
        "finance_db": str(finance_db),
        "finance_db_sha256": _sha256_file(finance_db),
        "kb_source_repo": str(kb_source),
        "kb_source_revision": select_revision_at_cutoff(kb_source, config.as_of),
        "kb_code_root": str(code_root),
        "kb_code_revision": _git_revision(code_root, config.kb_code_revision),
        "kb_rag_python": _python_identity(python),
        "question_file": str(config.question_file.expanduser().resolve()),
        "question_file_sha256": _sha256_file(config.question_file),
        "reference_file": str(config.reference_file.expanduser().resolve()),
        "reference_file_sha256": _sha256_file(config.reference_file),
        "prior_artifacts": [
            {"path": str(path), "sha256": _sha256_file(path)}
            for path in prior_artifacts
        ],
        "post_cutoff_documents": [
            {"path": str(path), "sha256": _sha256_file(path)}
            for path in post_cutoff_documents
        ],
        "generic_exception_file": str(exception_file) if exception_file else None,
        "generic_exception_file_sha256": (
            _sha256_file(exception_file) if exception_file else None
        ),
        "instruction_allowlist_file": (
            str(allowlist_file) if allowlist_file else None
        ),
        "instruction_allowlist_file_sha256": (
            _sha256_file(allowlist_file) if allowlist_file else None
        ),
        "prebuilt_hybrid_index": prebuilt_hybrid,
    }


def _generic_exception_ids(path: Path | None) -> tuple[str, ...]:
    if path is None:
        return ()
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("generic exception manifest schema is invalid")
    source_ids = value.get("source_ids")
    if not isinstance(source_ids, list) or any(
        not isinstance(item, str) or not item.strip() for item in source_ids
    ):
        raise ValueError("generic exception manifest source_ids are invalid")
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("generic exception manifest source_ids must be unique")
    return tuple(source_ids)


def _instruction_allowlist(
    path: Path | None,
) -> tuple[tuple[str, ...] | None, tuple[str, ...]]:
    if path is None:
        return None, ()
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("instruction allowlist schema is invalid")
    prefixes = value.get("prefixes")
    files = value.get("files")
    if not isinstance(prefixes, list) or not isinstance(files, list):
        raise ValueError("instruction allowlist paths are invalid")
    combined = [*prefixes, *files]
    if any(not isinstance(item, str) or not item.strip() for item in combined):
        raise ValueError("instruction allowlist paths are invalid")
    if len(combined) != len(set(combined)):
        raise ValueError("instruction allowlist paths must be unique")
    return tuple(prefixes), tuple(files)


def _sealed_tree_identity(path: Path) -> dict[str, object]:
    root = path.expanduser().absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("prebuilt Hybrid index must be a regular directory")
    if root.stat().st_mode & 0o777 != 0o555:
        raise ValueError("prebuilt Hybrid index root must be read-only")
    files: list[dict[str, object]] = []
    for item in sorted(root.rglob("*")):
        if item.is_symlink():
            raise ValueError("prebuilt Hybrid index cannot contain symlinks")
        if item.is_dir():
            if item.stat().st_mode & 0o777 != 0o555:
                raise ValueError("prebuilt Hybrid index directory must be read-only")
            continue
        if (
            not item.is_file()
            or item.stat().st_nlink != 1
            or item.stat().st_mode & 0o777 != 0o444
        ):
            raise ValueError("prebuilt Hybrid index files must be private and read-only")
        files.append(
            {
                "path": item.relative_to(root).as_posix(),
                "mode": 0o444,
                "bytes": item.stat().st_size,
                "sha256": _sha256_file(item),
            }
        )
    if not files:
        raise ValueError("prebuilt Hybrid index cannot be empty")
    return {
        "root": str(root.resolve()),
        "files": files,
        "manifest_sha256": _canonical_sha(files),
    }


def _write_json_once(path: Path, value: object, *, mode: int = 0o600) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
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


def _state_payload(value: dict[str, object]) -> dict[str, object]:
    payload = dict(value)
    payload.pop("state_sha256", None)
    return payload


def _manifest_payload(value: dict[str, object]) -> dict[str, object]:
    payload = dict(value)
    payload.pop("manifest_sha256", None)
    return payload


def _file_manifest(
    root: Path,
    *,
    include_control: bool,
    excluded: frozenset[str] = frozenset(),
) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("fixture cannot contain symlinks")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        if not include_control and relative in CONTROL_FILES:
            continue
        files.append(
            {
                "path": relative,
                "mode": path.stat().st_mode & 0o777,
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return files


def _audit_file_manifest(
    root: Path,
    expected: object,
    *,
    include_control: bool,
) -> None:
    if not isinstance(expected, list):
        raise ValueError("fixture artifact manifest is invalid")
    current = _file_manifest(root, include_control=include_control)
    if current != expected:
        raise ValueError("fixture artifact manifest mismatch")


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _component_payload(
    staging: Path,
    instruction: object,
    finance: object,
    wiki: object,
    hybrid: object,
) -> dict[str, object]:
    return {
        "instruction": {
            "component_root": _relative(staging, instruction.component_root),
            "manifest_sha256": instruction.manifest_sha256,
            "deterministic_scan_sha256": instruction.leak_scan.scan_sha256,
            "files_scanned": instruction.leak_scan.files_scanned,
            "semantic_candidate_count": len(instruction.leak_scan.semantic_candidates),
        },
        "finance": {
            "target": _relative(staging, finance.target_path),
            "sha256": finance.target_sha256,
            "cutoff_timestamp": finance.cutoff_timestamp,
            "source_rows": sum(item.source_rows for item in finance.tables),
            "target_rows": sum(item.target_rows for item in finance.tables),
            "tables": [item.to_dict() for item in finance.tables],
        },
        "wiki": {
            "root": _relative(staging, wiki.wiki_root),
            "selected_revision": wiki.selected_revision,
            "manifest_sha256": wiki.manifest_sha256,
            "file_count": len(wiki.files),
        },
        "hybrid": {
            "index_root": _relative(staging, hybrid.index_root),
            "code_runtime": _relative(staging, hybrid.code_runtime),
            "manifest_sha256": hybrid.manifest_sha256,
            "code_revision": hybrid.code_revision,
            "code_script_sha256": hybrid.code_script_sha256,
            "python_executable": hybrid.python_executable,
            "python_prefix": hybrid.python_prefix,
            "python_version": hybrid.python_version,
            "model": hybrid.model,
            "num_chunks": hybrid.num_chunks,
            "source_file_count": hybrid.source_file_count,
            "source_revision": hybrid.source_revision,
            "query": hybrid.query,
            "query_mode": hybrid.query_mode,
            "hits": list(hybrid.hits),
        },
    }


def _review_request(
    *,
    input_sha256: str,
    instruction: object,
    producer_identity: str,
) -> dict[str, object]:
    generic_exceptions = json.loads(
        (
            instruction.component_root / "control" / "generic-leak-exceptions.json"
        ).read_text(encoding="utf-8")
    )
    payload: dict[str, object] = {
        "schema_version": 1,
        "fixture_input_sha256": input_sha256,
        "export_manifest_sha256": instruction.manifest_sha256,
        "deterministic_scan_sha256": instruction.leak_scan.scan_sha256,
        "model": "gpt-5.6-sol",
        "prompt": SEMANTIC_REVIEW_PROMPT,
        "prompt_sha256": hashlib.sha256(
            SEMANTIC_REVIEW_PROMPT.encode("utf-8")
        ).hexdigest(),
        "producer_identity": producer_identity,
        "semantic_candidates": [
            item.to_dict() for item in instruction.leak_scan.semantic_candidates
        ],
        "generic_exceptions": generic_exceptions,
    }
    payload["request_sha256"] = _canonical_sha(payload)
    return payload


def _load_pending_state(root: Path, input_sha256: str) -> dict[str, object]:
    state = json.loads((root / "component-state.json").read_text(encoding="utf-8"))
    if state.get("state_sha256") != _canonical_sha(_state_payload(state)):
        raise ValueError("fixture state self hash mismatch")
    if state.get("input_sha256") != input_sha256:
        raise ValueError("fixture input hash mismatch")
    _audit_file_manifest(
        root,
        state.get("artifact_files"),
        include_control=False,
    )
    return state


def _load_sealed_result(root: Path, input_sha256: str) -> FixtureBuildResult:
    manifest = json.loads(
        (root / "fixture.manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("manifest_sha256") != _canonical_sha(
        _manifest_payload(manifest)
    ):
        raise ValueError("sealed fixture manifest self hash mismatch")
    if manifest.get("input_sha256") != input_sha256:
        raise ValueError("sealed fixture input hash mismatch")
    current = _file_manifest(
        root,
        include_control=True,
        excluded=frozenset({"fixture.manifest.json"}),
    )
    if current != manifest.get("files"):
        raise ValueError("sealed fixture file manifest mismatch")
    return FixtureBuildResult(
        status="sealed",
        component_root=root,
        input_sha256=input_sha256,
        manifest_sha256=str(manifest["manifest_sha256"]),
    )


def _remove_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("*"):
        try:
            path.chmod(0o700 if path.is_dir() else 0o600)
        except OSError:
            pass
    try:
        root.chmod(0o700)
    except OSError:
        pass
    shutil.rmtree(root, ignore_errors=True)


def _seal_fixture(
    *,
    root: Path,
    output_root: Path,
    state: dict[str, object],
    semantic_receipt_path: Path,
    producer_identity: str,
) -> FixtureBuildResult:
    pointer = output_root / "sealed-fixture.json"
    if pointer.exists():
        raise ValueError("sealed fixture pointer already targets another manifest")
    request = json.loads(
        (root / "semantic-leak-review-request.json").read_text(encoding="utf-8")
    )
    request_payload = dict(request)
    request_sha256 = str(request_payload.pop("request_sha256", ""))
    if request_sha256 != _canonical_sha(request_payload):
        raise ValueError("semantic review request self hash mismatch")
    if request_sha256 != state.get("review_request_sha256"):
        raise ValueError("semantic review request hash mismatch")
    if (
        request.get("prompt") != SEMANTIC_REVIEW_PROMPT
        or request.get("prompt_sha256")
        != hashlib.sha256(SEMANTIC_REVIEW_PROMPT.encode("utf-8")).hexdigest()
    ):
        raise ValueError("semantic review request prompt mismatch")
    if request.get("fixture_input_sha256") != state.get("input_sha256"):
        raise ValueError("semantic review request input hash mismatch")
    raw_receipt = json.loads(semantic_receipt_path.read_text(encoding="utf-8"))
    receipt = validate_semantic_receipt(
        raw_receipt,
        expected_export_manifest_sha256=str(request["export_manifest_sha256"]),
        expected_deterministic_scan_sha256=str(
            request["deterministic_scan_sha256"]
        ),
        producer_identity=producer_identity,
    )
    if receipt.prompt_sha256 != request.get("prompt_sha256"):
        raise ValueError("semantic receipt prompt hash mismatch")
    receipt_path = root / "semantic-leak-review-receipt.json"
    _write_json_once(receipt_path, receipt.to_dict())
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    sealed_files = _file_manifest(root, include_control=True)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "status": "sealed",
        "input_sha256": state["input_sha256"],
        "input": state["input"],
        "components": state["components"],
        "semantic_review_request_sha256": request_sha256,
        "semantic_receipt_sha256": receipt.receipt_sha256,
        "files": sealed_files,
    }
    manifest["manifest_sha256"] = _canonical_sha(manifest)
    manifest_path = root / "fixture.manifest.json"
    _write_json_once(manifest_path, manifest, mode=0o444)
    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        reverse=True,
    ):
        directory.chmod(0o555)
    root.chmod(0o555)
    pointer_payload: dict[str, object] = {
        "schema_version": 1,
        "relative_component": root.name,
        "manifest_sha256": manifest["manifest_sha256"],
    }
    pointer_payload["pointer_sha256"] = _canonical_sha(pointer_payload)
    if pointer.exists():
        if json.loads(pointer.read_text(encoding="utf-8")) != pointer_payload:
            raise ValueError("sealed fixture pointer already targets another manifest")
    else:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".sealed-fixture.",
            dir=output_root,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            temporary.write_text(
                json.dumps(pointer_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.chmod(0o444)
            os.replace(temporary, pointer)
        finally:
            temporary.unlink(missing_ok=True)
    return FixtureBuildResult(
        status="sealed",
        component_root=root,
        input_sha256=str(state["input_sha256"]),
        manifest_sha256=str(manifest["manifest_sha256"]),
    )


def build_ceiling_fixture(
    config: CeilingFixtureConfig,
    *,
    semantic_receipt_path: Path | None = None,
    seal: bool = False,
    dry_run: bool = False,
    producer_identity: str = "codex:/root",
) -> FixtureBuildResult:
    input_payload = _input_payload(config)
    input_sha256 = _canonical_sha(input_payload)
    output_root = _private_output_root(config.output_root)
    component_root = output_root / input_sha256[:16]
    if dry_run:
        return FixtureBuildResult("dry_run", component_root, input_sha256)
    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if component_root.exists():
        if (component_root / "fixture.manifest.json").exists():
            return _load_sealed_result(component_root, input_sha256)
        state = _load_pending_state(component_root, input_sha256)
    else:
        staging = Path(
            tempfile.mkdtemp(prefix=f".{input_sha256[:16]}.", dir=output_root)
        )
        try:
            include_prefixes, include_files = _instruction_allowlist(
                config.instruction_allowlist_file
            )
            corpus = build_forbidden_corpus(
                question_file=config.question_file,
                reference_file=config.reference_file,
                prior_artifacts=config.prior_artifacts,
                post_cutoff_documents=config.post_cutoff_documents,
            )
            instruction = build_instruction_export(
                source_repo=config.source_repo,
                source_revision=str(input_payload["source_revision"]),
                output_root=staging / "instruction-export",
                corpus=corpus,
                generic_exception_source_ids=_generic_exception_ids(
                    config.generic_exception_file
                ),
                include_prefixes=include_prefixes,
                include_files=include_files,
            )
            finance = build_filtered_duckdb(
                config.finance_db,
                staging / "finance.duckdb",
                as_of=config.as_of,
            )
            wiki = export_cutoff_wiki(
                config.kb_source_repo,
                staging / "wiki",
                as_of=config.as_of,
            )
            hybrid = build_true_hybrid_index(
                wiki_receipt=wiki,
                index_root=staging / "index",
                code_root=config.kb_code_root,
                code_revision=config.kb_code_revision,
                rag_python=config.kb_rag_python,
                query="瑞华泰",
                timeout_seconds=14400,
                prebuilt_index_root=config.prebuilt_hybrid_index,
            )
            prebuilt_identity = input_payload.get("prebuilt_hybrid_index")
            if isinstance(prebuilt_identity, dict) and prebuilt_identity.get(
                "manifest_sha256"
            ) != _canonical_sha([item.to_dict() for item in hybrid.index_files]):
                raise ValueError("adopted Hybrid index differs from prebuilt input")
            components = _component_payload(
                staging,
                instruction,
                finance,
                wiki,
                hybrid,
            )
            request = _review_request(
                input_sha256=input_sha256,
                instruction=instruction,
                producer_identity=producer_identity,
            )
            state: dict[str, object] = {
                "schema_version": 1,
                "status": "semantic_review_pending",
                "input_sha256": input_sha256,
                "input": input_payload,
                "components": components,
                "review_request_sha256": request["request_sha256"],
                "artifact_files": _file_manifest(staging, include_control=False),
            }
            state["state_sha256"] = _canonical_sha(state)
            _write_json_once(staging / "component-state.json", state)
            _write_json_once(staging / "semantic-leak-review-request.json", request)
            os.replace(staging, component_root)
        except BaseException:
            _remove_tree(staging)
            raise
    if not seal:
        return FixtureBuildResult(
            status="semantic_review_pending",
            component_root=component_root,
            input_sha256=input_sha256,
            review_request=component_root / "semantic-leak-review-request.json",
        )
    if semantic_receipt_path is None:
        raise ValueError("--seal requires --semantic-receipt")
    return _seal_fixture(
        root=component_root,
        output_root=output_root,
        state=state,
        semantic_receipt_path=semantic_receipt_path,
        producer_identity=producer_identity,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-repo", default=".")
    parser.add_argument("--finance-db", required=True)
    parser.add_argument("--kb-source-repo", required=True)
    parser.add_argument("--kb-code-root", required=True)
    parser.add_argument("--kb-code-revision", required=True)
    parser.add_argument("--kb-rag-python", required=True)
    parser.add_argument("--question-file", required=True)
    parser.add_argument("--reference-file", required=True)
    parser.add_argument("--prior-artifact", action="append", required=True)
    parser.add_argument(
        "--post-cutoff-document",
        action="append",
        required=True,
    )
    parser.add_argument(
        "--generic-exception-file",
        default="intelligence/eval/cases/ceiling_generic_leak_exceptions.json",
    )
    parser.add_argument(
        "--instruction-allowlist-file",
        default="intelligence/eval/cases/ceiling_instruction_allowlist.json",
    )
    parser.add_argument("--prebuilt-hybrid-index")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--semantic-receipt")
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    config = CeilingFixtureConfig(
        source_repo=Path(args.source_repo),
        source_revision=args.source_revision,
        finance_db=Path(args.finance_db),
        kb_source_repo=Path(args.kb_source_repo),
        kb_code_root=Path(args.kb_code_root),
        kb_code_revision=args.kb_code_revision,
        kb_rag_python=Path(args.kb_rag_python),
        question_file=Path(args.question_file),
        reference_file=Path(args.reference_file),
        prior_artifacts=tuple(Path(path) for path in args.prior_artifact),
        post_cutoff_documents=tuple(
            Path(path) for path in args.post_cutoff_document
        ),
        generic_exception_file=(
            Path(args.generic_exception_file)
            if args.generic_exception_file
            else None
        ),
        as_of=args.as_of,
        output_root=Path(args.output_root),
        instruction_allowlist_file=(
            Path(args.instruction_allowlist_file)
            if args.instruction_allowlist_file
            else None
        ),
        prebuilt_hybrid_index=(
            Path(args.prebuilt_hybrid_index)
            if args.prebuilt_hybrid_index
            else None
        ),
    )
    try:
        result = build_ceiling_fixture(
            config,
            semantic_receipt_path=(
                Path(args.semantic_receipt) if args.semantic_receipt else None
            ),
            seal=args.seal,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"ceiling fixture failed: {exc}")
        return 1
    print(
        json.dumps(
            {
                "status": result.status,
                "component_root": str(result.component_root),
                "input_sha256": result.input_sha256,
                "manifest_sha256": result.manifest_sha256,
                "review_request": (
                    str(result.review_request) if result.review_request else None
                ),
            },
            ensure_ascii=False,
        )
    )
    return 3 if result.status == "semantic_review_pending" else 0


if __name__ == "__main__":
    raise SystemExit(main())
