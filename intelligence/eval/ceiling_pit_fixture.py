"""Physical point-in-time exports for the sealed runtime ceiling benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Iterator, Literal
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
TEMPORAL_COLUMNS = frozenset(
    {
        "trade_date",
        "date",
        "source_date",
        "report_date",
        "ann_date",
        "announcement_date",
        "end_date",
        "report_period",
        "source_update_time",
        "updated_at",
        "created_at",
        "calculated_at",
        "published_at",
        "first_seen_date",
        "last_seen_date",
        "start_date",
        "similar_date",
        "first_limit_date",
        "startup_date_small",
        "startup_date_big",
        "startup_date_super",
        "startup_date_extend",
        "strength_updated_at",
        "stock_high_updated_at",
        "sh_index_updated_at",
        "multi_period_updated_at",
        "limit_update_time",
        "prev_limitup_date",
        "as_of_date",
    }
)
NON_TEMPORAL_MARKER_COLUMNS = frozenset(
    {
        "multi_period_resonance",
        "multi_period_source",
        "period_type",
        "limit_times",
        "primary_high_period",
        "high_periods_json",
        "is_realtime",
        "open_times",
    }
)
INTRADAY_TIME_COLUMNS = frozenset({"first_limit_time", "last_limit_time"})
TEMPORAL_MARKERS = ("date", "time", "year", "period", "when")
_NUMERIC_TYPES = re.compile(
    r"^(?:U?TINYINT|U?SMALLINT|U?INTEGER|U?BIGINT|HUGEINT|DECIMAL|NUMERIC)"
)
_PUBLICATION_DATE_KEYS = frozenset(
    {
        "date",
        "source_date",
        "report_date",
        "ann_date",
        "announcement_date",
        "publication_date",
        "published_at",
    }
)
_PUBLICATION_DATE_VALUE = re.compile(
    r"(?<!\d)(\d{4}(?:-\d{2}-\d{2}|\d{4}))(?!\d)"
)
_CHINESE_PUBLICATION_DATE_VALUE = re.compile(
    r"(?<!\d)(\d{4})年(\d{1,2})月(\d{1,2})日(?!\d)"
)
_CHINESE_PUBLICATION_LINE = re.compile(
    r"^\s*(?:发布日期|发布时间|报告日期)\s*[：:]\s*(.+?)\s*$"
)


class TemporalSchemaError(ValueError):
    """Raised when a temporal column cannot be classified safely."""


class TemporalValueError(ValueError):
    """Raised when a date-bearing value cannot be parsed safely."""


@dataclass(frozen=True)
class TableCopyReceipt:
    name: str
    source_kind: Literal["BASE TABLE", "VIEW"]
    temporal_columns: tuple[str, ...]
    intraday_time_columns: tuple[str, ...]
    marker_exceptions: tuple[str, ...]
    source_rows: int
    target_rows: int
    maxima: dict[str, str | None]
    derivation: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "source_kind": self.source_kind,
            "temporal_columns": list(self.temporal_columns),
            "intraday_time_columns": list(self.intraday_time_columns),
            "marker_exceptions": list(self.marker_exceptions),
            "source_rows": self.source_rows,
            "target_rows": self.target_rows,
            "maxima": dict(self.maxima),
        }
        if self.derivation is not None:
            payload["derivation"] = dict(self.derivation)
        return payload


@dataclass(frozen=True)
class FilteredDuckDBReceipt:
    source_path: Path
    target_path: Path
    as_of: str
    cutoff_timestamp: str
    tables: tuple[TableCopyReceipt, ...]
    target_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source_path": str(self.source_path),
            "target_path": str(self.target_path),
            "as_of": self.as_of,
            "cutoff_timestamp": self.cutoff_timestamp,
            "tables": [item.to_dict() for item in self.tables],
            "target_sha256": self.target_sha256,
        }


@dataclass(frozen=True)
class FilteredDuckDBAudit:
    status: Literal["valid", "invalid"]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class WikiFileReceipt:
    path: str
    mode: int
    bytes: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "mode": self.mode,
            "bytes": self.bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class WikiExportReceipt:
    source_repo: Path
    selected_revision: str
    as_of: str
    wiki_root: Path
    files: tuple[WikiFileReceipt, ...]
    max_publication_date: str | None
    manifest_sha256: str

    def manifest_payload(self) -> dict[str, object]:
        return {
            "source_repo": str(self.source_repo),
            "selected_revision": self.selected_revision,
            "as_of": self.as_of,
            "files": [item.to_dict() for item in self.files],
            "max_publication_date": self.max_publication_date,
        }


@dataclass(frozen=True)
class WikiExportAudit:
    status: Literal["valid", "invalid"]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class HybridIndexReceipt:
    index_root: Path
    code_runtime: Path
    code_revision: str
    code_script_sha256: str
    python_executable: str
    python_prefix: str
    python_version: str
    model: str
    num_chunks: int
    source_file_count: int
    source_revision: str
    query: str
    query_mode: Literal["hybrid"]
    hits: tuple[dict[str, object], ...]
    index_files: tuple[WikiFileReceipt, ...]
    manifest_sha256: str


@dataclass(frozen=True)
class _ObjectPlan:
    schema: str
    name: str
    source_kind: Literal["BASE TABLE", "VIEW"]
    columns: tuple[tuple[str, str], ...]
    temporal_columns: tuple[tuple[str, str], ...]
    intraday_time_columns: tuple[str, ...]
    marker_exceptions: tuple[str, ...]
    source_rows: int

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"


def _duckdb() -> Any:
    try:
        import duckdb
    except Exception as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("duckdb is required for PIT fixture construction") from exc
    return duckdb


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
    blobs: dict[str, bytes] = {}
    offset = 0
    for expected in object_ids:
        newline = process.stdout.find(b"\n", offset)
        if newline < 0:
            raise ValueError("git cat-file batch header is truncated")
        header = process.stdout[offset:newline].decode("ascii").split(" ")
        if len(header) != 3 or header[0] != expected or header[1] != "blob":
            raise ValueError("git cat-file batch returned an unexpected object")
        size = int(header[2])
        start = newline + 1
        end = start + size
        if end >= len(process.stdout) or process.stdout[end : end + 1] != b"\n":
            raise ValueError("git cat-file batch payload is truncated")
        blobs[expected] = process.stdout[start:end]
        offset = end + 1
    return blobs


def _stream_git_blobs(
    repo: Path,
    object_ids: tuple[str, ...],
) -> Iterator[tuple[str, bytes]]:
    process = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdin is None or process.stdout is None:
        process.kill()
        raise RuntimeError("unable to open git cat-file pipes")
    try:
        for expected in object_ids:
            process.stdin.write(expected.encode("ascii") + b"\n")
            process.stdin.flush()
            header = process.stdout.readline().decode("ascii").strip().split(" ")
            if len(header) != 3 or header[0] != expected or header[1] != "blob":
                raise ValueError("git cat-file batch returned an unexpected object")
            size = int(header[2])
            data = process.stdout.read(size)
            terminator = process.stdout.read(1)
            if len(data) != size or terminator != b"\n":
                raise ValueError("git cat-file batch payload is truncated")
            yield expected, data
        process.stdin.close()
        return_code = process.wait(timeout=30)
        if return_code != 0:
            stderr = process.stderr.read().decode("utf-8", errors="replace")
            raise ValueError(f"git cat-file failed: {stderr.strip()}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


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


def _quote_ident(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _quote_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _qualified(schema: str, name: str, *, database: str | None = None) -> str:
    parts = [] if database is None else [_quote_ident(database)]
    parts.extend((_quote_ident(schema), _quote_ident(name)))
    return ".".join(parts)


def _cutoff(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("as_of must be non-empty")
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            parsed = datetime.combine(date.fromisoformat(raw), time(23, 59, 59))
            return parsed.replace(tzinfo=SHANGHAI)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("as_of must be an ISO date or timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI)


def _publication_dates(relative: str, data: bytes) -> tuple[date, ...]:
    if Path(relative).suffix.casefold() not in {".md", ".txt", ".yaml", ".yml"}:
        return ()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Wiki text is not UTF-8: {relative}") from exc
    lines = text.splitlines()
    metadata_lines = lines[:80]
    if lines and lines[0].strip() == "---":
        try:
            end = next(
                index
                for index, line in enumerate(lines[1:], start=1)
                if line.strip() == "---"
            )
        except StopIteration as exc:
            raise ValueError(f"Wiki frontmatter is unterminated: {relative}") from exc
        metadata_lines = lines[1:end]
    values: list[date] = []
    for line in metadata_lines:
        key, separator, raw_value = line.partition(":")
        candidate: str | None = None
        if separator and key.strip().casefold() in _PUBLICATION_DATE_KEYS:
            candidate = raw_value.strip().strip("'\"")
        else:
            chinese = _CHINESE_PUBLICATION_LINE.fullmatch(line)
            if chinese is not None:
                candidate = chinese.group(1).strip().strip("'\"")
        if candidate is None:
            continue
        match = _PUBLICATION_DATE_VALUE.search(candidate)
        try:
            if match is not None:
                raw_date = match.group(1)
                parsed = (
                    date.fromisoformat(raw_date)
                    if "-" in raw_date
                    else datetime.strptime(raw_date, "%Y%m%d").date()
                )
            else:
                chinese_date = _CHINESE_PUBLICATION_DATE_VALUE.search(candidate)
                if chinese_date is None:
                    raise ValueError
                parsed = date(
                    int(chinese_date.group(1)),
                    int(chinese_date.group(2)),
                    int(chinese_date.group(3)),
                )
        except ValueError as exc:
            raise ValueError(f"malformed Wiki publication date: {relative}") from exc
        values.append(parsed)
    return tuple(values)


def select_revision_at_cutoff(
    source_repo: str | Path,
    as_of: str,
    *,
    ref: str = "HEAD",
) -> str:
    """Select the last commit whose commit time is not after ``as_of``."""

    repo = Path(source_repo).expanduser().resolve()
    if not (repo / ".git").exists():
        raise ValueError("knowledge source must be a Git repository")
    cutoff = _cutoff(as_of).isoformat(timespec="seconds")
    result = _run_git(repo, ["rev-list", "-1", f"--before={cutoff}", ref])
    revision = result.stdout.decode("utf-8").strip()
    if not revision:
        raise ValueError("no knowledge revision exists at or before cutoff")
    return revision


def audit_wiki_export(receipt: WikiExportReceipt) -> WikiExportAudit:
    issues: list[str] = []
    root = receipt.wiki_root
    if not root.is_dir() or root.is_symlink():
        return WikiExportAudit("invalid", ("wiki_root_missing_or_non_regular",))
    if (root / ".git").exists():
        issues.append("git_directory_present")
    expected_paths = {item.path for item in receipt.files}
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual_paths != expected_paths:
        issues.append("file_set_mismatch")
    publication_dates: list[date] = []
    for item in receipt.files:
        path = root / item.path
        if path.is_symlink() or not path.is_file():
            issues.append(f"non_regular:{item.path}")
            continue
        if path.stat().st_nlink != 1:
            issues.append(f"hardlink:{item.path}")
        if path.stat().st_mode & 0o777 != item.mode:
            issues.append(f"mode:{item.path}")
        if path.stat().st_size != item.bytes:
            issues.append(f"bytes:{item.path}")
        if _sha256_file(path) != item.sha256:
            issues.append(f"content_hash:{item.path}")
        try:
            publication_dates.extend(_publication_dates(item.path, path.read_bytes()))
        except ValueError:
            issues.append(f"publication_date:{item.path}")
    observed_max = max(publication_dates).isoformat() if publication_dates else None
    if observed_max != receipt.max_publication_date:
        issues.append("publication_date_max_mismatch")
    if publication_dates and max(publication_dates) > _cutoff(receipt.as_of).date():
        issues.append("post_cutoff_publication_date")
    if receipt.manifest_sha256 != _canonical_sha(receipt.manifest_payload()):
        issues.append("manifest_self_hash_mismatch")
    return WikiExportAudit(
        "invalid" if issues else "valid",
        tuple(dict.fromkeys(issues)),
    )


def export_cutoff_wiki(
    source_repo: str | Path,
    destination: str | Path,
    *,
    as_of: str,
    ref: str = "HEAD",
) -> WikiExportReceipt:
    """Export ``wiki/`` regular blobs from the last revision before ``as_of``."""

    repo = Path(source_repo).expanduser().resolve()
    selected_revision = select_revision_at_cutoff(repo, as_of, ref=ref)
    output = Path(destination).expanduser().resolve()
    if output.exists():
        raise FileExistsError("Wiki export destination already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    raw_tree = _run_git(
        repo,
        ["ls-tree", "-r", "-z", selected_revision, "--", "wiki"],
    ).stdout
    selected: list[tuple[str, str, int]] = []
    for raw_entry in raw_tree.split(b"\0"):
        if not raw_entry:
            continue
        metadata, raw_path = raw_entry.split(b"\t", 1)
        mode, object_type, object_sha = metadata.decode("ascii").split(" ")
        source_path = raw_path.decode("utf-8")
        if not source_path.startswith("wiki/"):
            raise ValueError("Wiki export path escaped source prefix")
        relative = source_path.removeprefix("wiki/")
        if not relative or relative.startswith("/") or ".." in Path(relative).parts:
            raise ValueError("Wiki export path is unsafe")
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("Wiki export accepts regular Git blobs only")
        selected.append(
            (relative, object_sha, 0o555 if mode == "100755" else 0o444)
        )
    if not selected:
        raise ValueError("selected knowledge revision has no wiki files")
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent)
    )
    file_receipts: list[WikiFileReceipt] = []
    publication_dates: list[date] = []
    try:
        stream = _stream_git_blobs(repo, tuple(item[1] for item in selected))
        for (relative, object_sha, mode), (returned_sha, data) in zip(
            selected,
            stream,
            strict=True,
        ):
            if returned_sha != object_sha:
                raise ValueError("git blob stream order mismatch")
            dates = _publication_dates(relative, data)
            if dates and max(dates) > _cutoff(as_of).date():
                raise ValueError(f"post-cutoff publication date: {relative}")
            publication_dates.extend(dates)
            path = temporary / relative
            _write_once(path, data, mode)
            file_receipts.append(
                WikiFileReceipt(
                    path=relative,
                    mode=mode,
                    bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            )
        for directory in sorted(
            (path for path in temporary.rglob("*") if path.is_dir()),
            reverse=True,
        ):
            directory.chmod(0o555)
        temporary.chmod(0o555)
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    files = tuple(sorted(file_receipts, key=lambda item: item.path))
    provisional = WikiExportReceipt(
        source_repo=repo,
        selected_revision=selected_revision,
        as_of=str(as_of),
        wiki_root=output,
        files=files,
        max_publication_date=(
            max(publication_dates).isoformat() if publication_dates else None
        ),
        manifest_sha256="",
    )
    receipt = WikiExportReceipt(
        source_repo=repo,
        selected_revision=selected_revision,
        as_of=str(as_of),
        wiki_root=output,
        files=files,
        max_publication_date=provisional.max_publication_date,
        manifest_sha256=_canonical_sha(provisional.manifest_payload()),
    )
    audit = audit_wiki_export(receipt)
    if audit.status != "valid":
        raise ValueError("new Wiki export failed audit: " + ",".join(audit.issues))
    return receipt


def _export_rag_code(
    code_root: Path,
    code_revision: str,
    destination: Path,
) -> tuple[str, tuple[WikiFileReceipt, ...]]:
    resolved = _run_git(
        code_root,
        ["rev-parse", f"{code_revision}^{{commit}}"],
    ).stdout.decode("utf-8").strip()
    if destination.exists():
        raise FileExistsError("RAG code runtime already exists")
    raw_tree = _run_git(code_root, ["ls-tree", "-r", "-z", resolved]).stdout
    selected: list[tuple[str, str, int]] = []
    exact = {"scripts/rag_index.py", "scripts/rag_freshness.py"}
    for raw_entry in raw_tree.split(b"\0"):
        if not raw_entry:
            continue
        metadata, raw_path = raw_entry.split(b"\t", 1)
        mode, object_type, object_sha = metadata.decode("ascii").split(" ")
        relative = raw_path.decode("utf-8")
        if relative not in exact and not relative.startswith("skills/lib/"):
            continue
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("RAG code export accepts regular Git blobs only")
        selected.append(
            (relative, object_sha, 0o555 if mode == "100755" else 0o444)
        )
    if not exact.issubset({item[0] for item in selected}):
        raise ValueError("RAG code revision is missing required scripts")
    blobs = _read_git_blobs(code_root, tuple(item[1] for item in selected))
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    receipts: list[WikiFileReceipt] = []
    try:
        for relative, object_sha, mode in selected:
            data = blobs[object_sha]
            _write_once(temporary / relative, data, mode)
            receipts.append(
                WikiFileReceipt(
                    path=relative,
                    mode=mode,
                    bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            )
        for directory in sorted(
            (path for path in temporary.rglob("*") if path.is_dir()),
            reverse=True,
        ):
            directory.chmod(0o555)
        temporary.chmod(0o555)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return resolved, tuple(sorted(receipts, key=lambda item: item.path))


def _probe_python(python: Path) -> dict[str, object]:
    code = (
        "import json,sys;"
        "print(json.dumps({'executable':sys.executable,'prefix':sys.prefix,"
        "'version':sys.version.split()[0],'path':sys.path}))"
    )
    result = subprocess.run(
        [str(python), "-c", code],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("RAG Python provenance probe returned invalid JSON")
    return value


def _wiki_manifest_revision(wiki_root: Path) -> tuple[str, int]:
    entries: list[tuple[str, str]] = []
    for directory in ("entities", "concepts", "sources", "synthesis", "briefings"):
        root = wiki_root / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Wiki manifest accepts regular Markdown files only")
            relative = path.relative_to(wiki_root.parent).as_posix()
            entries.append((relative, _sha256_file(path)))
    entries.sort()
    digest = hashlib.sha256()
    digest.update(b"include_raw=0;max_files=0\n")
    for relative, file_hash in entries:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return f"manifest:v1:{digest.hexdigest()}", len(entries)


def _parse_json_array(stdout: str) -> list[object]:
    text = str(stdout or "").strip()
    for index in reversed([i for i, char in enumerate(text) if char == "["]):
        try:
            value = json.loads(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            return value
    raise ValueError("Hybrid query did not return a JSON array")


def _seal_regular_tree(root: Path) -> tuple[WikiFileReceipt, ...]:
    receipts: list[WikiFileReceipt] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("sealed tree cannot contain symlinks")
        if not path.is_file():
            continue
        mode = 0o444
        path.chmod(mode)
        receipts.append(
            WikiFileReceipt(
                path=path.relative_to(root).as_posix(),
                mode=mode,
                bytes=path.stat().st_size,
                sha256=_sha256_file(path),
            )
        )
    if not receipts:
        raise ValueError("sealed tree must contain files")
    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        reverse=True,
    ):
        directory.chmod(0o555)
    root.chmod(0o555)
    return tuple(receipts)


def _copy_regular_tree(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise ValueError("prebuilt Hybrid index must be a regular directory")
    destination.mkdir(mode=0o700)
    try:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise ValueError("prebuilt Hybrid index cannot contain symlinks")
            relative = path.relative_to(source)
            target = destination / relative
            if path.is_dir():
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
                continue
            if not path.is_file() or path.stat().st_nlink != 1:
                raise ValueError("prebuilt Hybrid index must contain private regular files")
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(target, flags, 0o600)
            try:
                with path.open("rb") as source_handle, os.fdopen(
                    descriptor,
                    "wb",
                    closefd=False,
                ) as target_handle:
                    shutil.copyfileobj(source_handle, target_handle, 1024 * 1024)
                    target_handle.flush()
                    os.fsync(target_handle.fileno())
            finally:
                os.close(descriptor)
    except BaseException:
        _remove_tree(destination)
        raise


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


def _rag_environment(*, wiki_root: Path, index_root: Path, python: Path) -> dict[str, str]:
    environment = {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "TOKENIZERS_PARALLELISM": "false",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "KB_VAULT": str(wiki_root),
        "RAG_INDEX_DIR": str(index_root),
        "KB_RAG_PYTHON": str(python),
        "RAG_INCLUDE_RAW": "0",
        "RAG_MAX_FILES": "0",
        "RAG_MODEL": "bge-m3",
    }
    for name in ("HF_HOME", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE"):
        if os.environ.get(name):
            environment[name] = os.environ[name]
    return environment


def build_true_hybrid_index(
    *,
    wiki_receipt: WikiExportReceipt,
    index_root: str | Path,
    code_root: str | Path,
    code_revision: str,
    rag_python: str | Path,
    query: str,
    timeout_seconds: float = 3600.0,
    prebuilt_index_root: str | Path | None = None,
) -> HybridIndexReceipt:
    """Build and seal one content-bound BGE-m3 + BM25 Hybrid index."""

    if audit_wiki_export(wiki_receipt).status != "valid":
        raise ValueError("Wiki export must pass audit before indexing")
    index = Path(index_root).expanduser().resolve()
    if index.exists():
        raise FileExistsError("Hybrid index destination already exists")
    index.parent.mkdir(parents=True, exist_ok=True)
    code_source = Path(code_root).expanduser().resolve()
    python = Path(rag_python).expanduser().absolute()
    if not python.is_file():
        raise ValueError("RAG Python executable is unavailable")
    python_probe = _probe_python(python)
    code_runtime = index.parent / "rag-code-runtime"
    resolved_revision, _code_files = _export_rag_code(
        code_source,
        code_revision,
        code_runtime,
    )
    script = code_runtime / "scripts" / "rag_index.py"
    environment = _rag_environment(
        wiki_root=wiki_receipt.wiki_root,
        index_root=index,
        python=python,
    )
    try:
        if prebuilt_index_root is None:
            subprocess.run(
                [str(python), str(script), "build", "--model", "bge-m3"],
                check=True,
                text=True,
                env=environment,
                timeout=timeout_seconds,
            )
        else:
            _copy_regular_tree(
                Path(prebuilt_index_root).expanduser().absolute(),
                index,
            )
        required = {
            "chunks.jsonl",
            "dense.npy",
            "meta.json",
            "bm25_tokens.jsonl.gz",
        }
        if not required.issubset(
            {path.name for path in index.iterdir() if path.is_file()}
        ):
            raise ValueError("Hybrid index is missing required files")
        meta = json.loads((index / "meta.json").read_text(encoding="utf-8"))
        if meta.get("format_version") != 2:
            raise ValueError("Hybrid index format_version must be 2")
        if meta.get("model") != "bge-m3":
            raise ValueError("Hybrid index model must be bge-m3")
        expected_revision, expected_file_count = _wiki_manifest_revision(
            wiki_receipt.wiki_root
        )
        if meta.get("source_revision") != expected_revision:
            raise ValueError("Hybrid index source manifest mismatch")
        if int(meta.get("source_file_count") or -1) != expected_file_count:
            raise ValueError("Hybrid index source file count mismatch")
        if meta.get("source_dirty") is True:
            raise ValueError("Hybrid index cannot be built from dirty source")
        import numpy as np

        dense = np.load(index / "dense.npy", mmap_mode="r")
        num_chunks = int(meta.get("num_chunks") or 0)
        if dense.ndim != 2 or dense.shape[0] != num_chunks or dense.shape[1] <= 0:
            raise ValueError("Hybrid dense matrix shape mismatch")
        fingerprint = hashlib.sha256()
        chunk_count = 0
        source_files: set[str] = set()
        with (index / "chunks.jsonl").open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                chunk_count += 1
                source_files.add(str(chunk.get("file_path") or ""))
                fingerprint.update(str(chunk.get("id") or "").encode("utf-8"))
                fingerprint.update(b"\0")
                fingerprint.update(
                    str(chunk.get("content_hash") or "").encode("ascii")
                )
                fingerprint.update(b"\n")
        if chunk_count != num_chunks:
            raise ValueError("Hybrid chunks count mismatch")
        if len(source_files) != expected_file_count:
            raise ValueError("Hybrid chunks source set mismatch")
        if meta.get("source_fingerprint") != fingerprint.hexdigest():
            raise ValueError("Hybrid chunks fingerprint mismatch")
        import gzip

        with gzip.open(index / "bm25_tokens.jsonl.gz", "rt", encoding="utf-8") as handle:
            header = json.loads(handle.readline())
        if header != {"format": "bm25-tokens-v1", "num_chunks": num_chunks}:
            raise ValueError("Hybrid BM25 receipt mismatch")
        query_result = subprocess.run(
            [
                str(python),
                str(script),
                "query",
                str(query),
                "--mode",
                "hybrid",
                "--k",
                "5",
                "--json",
                "--stale-policy",
                "fail",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
            timeout=timeout_seconds,
        )
        parsed_hits = _parse_json_array(query_result.stdout)
        hits = tuple(item for item in parsed_hits if isinstance(item, dict))
        if not hits or any(item.get("index_freshness") != "fresh" for item in hits):
            raise ValueError("Hybrid probe must return fresh hits")
        for hit in hits:
            relative = str(hit.get("file_path") or "")
            source_path = wiki_receipt.wiki_root.parent / relative
            if not source_path.is_file() or source_path.is_symlink():
                raise ValueError("Hybrid probe returned an unbound source path")
        index_files = _seal_regular_tree(index)
    except BaseException:
        _remove_tree(index)
        _remove_tree(code_runtime)
        raise
    payload = {
        "index_root": str(index),
        "code_runtime": str(code_runtime),
        "code_revision": resolved_revision,
        "code_script_sha256": _sha256_file(script),
        "python_executable": str(python_probe.get("executable") or ""),
        "python_prefix": str(python_probe.get("prefix") or ""),
        "python_version": str(python_probe.get("version") or ""),
        "model": "bge-m3",
        "num_chunks": num_chunks,
        "source_file_count": expected_file_count,
        "source_revision": expected_revision,
        "query": str(query),
        "query_mode": "hybrid",
        "hits": list(hits),
        "index_files": [item.to_dict() for item in index_files],
    }
    return HybridIndexReceipt(
        index_root=index,
        code_runtime=code_runtime,
        code_revision=resolved_revision,
        code_script_sha256=str(payload["code_script_sha256"]),
        python_executable=str(payload["python_executable"]),
        python_prefix=str(payload["python_prefix"]),
        python_version=str(payload["python_version"]),
        model="bge-m3",
        num_chunks=num_chunks,
        source_file_count=expected_file_count,
        source_revision=expected_revision,
        query=str(query),
        query_mode="hybrid",
        hits=hits,
        index_files=index_files,
        manifest_sha256=_canonical_sha(payload),
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized_sql(column: str, data_type: str) -> str:
    quoted = _quote_ident(column)
    normalized_type = data_type.upper().strip()
    if normalized_type == "TIMESTAMP WITH TIME ZONE":
        return f"CAST({quoted} AS TIMESTAMPTZ)"
    if normalized_type == "DATE" or normalized_type.startswith("TIMESTAMP"):
        return f"CAST({quoted} AS TIMESTAMP) AT TIME ZONE 'Asia/Shanghai'"
    text = f"TRIM(CAST({quoted} AS VARCHAR))"
    if _NUMERIC_TYPES.match(normalized_type):
        return (
            f"TRY_STRPTIME({text}, '%Y%m%d') "
            "AT TIME ZONE 'Asia/Shanghai'"
        )
    return (
        "CASE "
        f"WHEN REGEXP_FULL_MATCH({text}, '^[0-9]{{8}}$') "
        f"THEN TRY_STRPTIME({text}, '%Y%m%d') AT TIME ZONE 'Asia/Shanghai' "
        f"ELSE TRY_CAST({text} AS TIMESTAMPTZ) END"
    )


def _iso_datetime(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.min).replace(tzinfo=SHANGHAI)
    if not isinstance(value, datetime):
        raise TypeError("temporal maximum must be date or datetime")
    if value.tzinfo is None:
        value = value.replace(tzinfo=SHANGHAI)
    return value.astimezone(SHANGHAI).isoformat(timespec="seconds")


def _user_objects(connection: Any) -> tuple[tuple[str, str, str], ...]:
    rows = connection.execute(
        """
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY CASE WHEN table_type = 'BASE TABLE' THEN 0 ELSE 1 END,
                 table_schema,
                 table_name
        """
    ).fetchall()
    return tuple((str(schema), str(name), str(kind)) for schema, name, kind in rows)


def _columns(connection: Any, schema: str, name: str) -> tuple[tuple[str, str], ...]:
    rows = connection.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema, name],
    ).fetchall()
    return tuple((str(column), str(data_type)) for column, data_type in rows)


def _plan_objects(connection: Any) -> tuple[_ObjectPlan, ...]:
    plans: list[_ObjectPlan] = []
    for schema, name, kind in _user_objects(connection):
        if kind not in {"BASE TABLE", "VIEW"}:
            raise ValueError(f"unsupported DuckDB object type: {kind}")
        columns = _columns(connection, schema, name)
        unknown = tuple(
            column
            for column, _data_type in columns
            if column.casefold() not in TEMPORAL_COLUMNS
            and column.casefold() not in NON_TEMPORAL_MARKER_COLUMNS
            and column.casefold() not in INTRADAY_TIME_COLUMNS
            and any(marker in column.casefold() for marker in TEMPORAL_MARKERS)
        )
        if unknown:
            joined = ",".join(unknown)
            raise TemporalSchemaError(
                f"unclassified_temporal_column:{schema}.{name}:{joined}"
            )
        temporal = tuple(
            (column, data_type)
            for column, data_type in columns
            if column.casefold() in TEMPORAL_COLUMNS
        )
        intraday = tuple(
            column
            for column, _data_type in columns
            if column.casefold() in INTRADAY_TIME_COLUMNS
        )
        marker_exceptions = tuple(
            column
            for column, _data_type in columns
            if column.casefold() in NON_TEMPORAL_MARKER_COLUMNS
        )
        column_names = {column.casefold() for column, _data_type in columns}
        if intraday and not ({"trade_date", "date"} & column_names):
            raise TemporalSchemaError(
                f"intraday_time_without_date_anchor:{schema}.{name}:"
                + ",".join(intraday)
            )
        qualified = _qualified(schema, name)
        for column, data_type in temporal:
            expression = _normalized_sql(column, data_type)
            malformed = connection.execute(
                f"SELECT COUNT(*) FROM {qualified} "
                f"WHERE {_quote_ident(column)} IS NOT NULL AND ({expression}) IS NULL"
            ).fetchone()[0]
            if malformed:
                raise TemporalValueError(
                    f"malformed_temporal_value:{schema}.{name}:{column}:{malformed}"
                )
        for column in intraday:
            text = f"TRIM(CAST({_quote_ident(column)} AS VARCHAR))"
            valid_clock = (
                f"({text} = '0' OR "
                f"TRY_STRPTIME({text}, '%H:%M:%S') IS NOT NULL OR "
                f"(REGEXP_FULL_MATCH({text}, '^[0-9]{{5,6}}$') AND "
                f"TRY_STRPTIME(LPAD({text}, 6, '0'), '%H%M%S') IS NOT NULL))"
            )
            malformed = connection.execute(
                f"SELECT COUNT(*) FROM {qualified} "
                f"WHERE {_quote_ident(column)} IS NOT NULL AND NOT {valid_clock}"
            ).fetchone()[0]
            if malformed:
                raise TemporalValueError(
                    f"malformed_intraday_time:{schema}.{name}:{column}:{malformed}"
                )
        source_rows = int(
            connection.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0]
        )
        plans.append(
            _ObjectPlan(
                schema=schema,
                name=name,
                source_kind=kind,  # type: ignore[arg-type]
                columns=columns,
                temporal_columns=temporal,
                intraday_time_columns=intraday,
                marker_exceptions=marker_exceptions,
                source_rows=source_rows,
            )
        )
    return tuple(plans)


def _predicate(plan: _ObjectPlan) -> str:
    if not plan.temporal_columns:
        return "TRUE"
    return " AND ".join(
        "(" + _quote_ident(column) + " IS NULL OR "
        + _normalized_sql(column, data_type)
        + " <= ?::TIMESTAMPTZ)"
        for column, data_type in plan.temporal_columns
    )


def _maxima(connection: Any, plan: _ObjectPlan) -> dict[str, str | None]:
    qualified = _qualified(plan.schema, plan.name)
    maxima: dict[str, str | None] = {}
    for column, data_type in plan.temporal_columns:
        value = connection.execute(
            f"SELECT MAX({_normalized_sql(column, data_type)}) FROM {qualified}"
        ).fetchone()[0]
        maxima[column] = _iso_datetime(value)
    return maxima


_PIT_DERIVED_MARKET_SOURCE = (
    "derived:pitsafe_fact_stock_daily+feature_market_window"
)
_PIT_DERIVED_MARKET_NOTE = (
    "PIT-safe derived market base; late source fields withheld"
)


def _null_as(data_type: str) -> str:
    return f"CAST(NULL AS {data_type})"


def _safe_component_expression(
    *,
    column: str,
    data_type: str,
    timestamp_column: str,
    available_columns: set[str],
    cutoff_sql: str,
) -> str:
    if timestamp_column not in available_columns:
        return _null_as(data_type)
    timestamp = f'f.{_quote_ident(timestamp_column)}'
    value = f'f.{_quote_ident(column)}'
    return (
        f"CASE WHEN {timestamp} IS NOT NULL "
        f"AND CAST({timestamp} AS TIMESTAMPTZ) <= {cutoff_sql} "
        f"THEN {value} ELSE {_null_as(data_type)} END"
    )


def _derive_cutoff_market_row(
    connection: Any,
    *,
    plan: _ObjectPlan,
    plans: tuple[_ObjectPlan, ...],
    cutoff_text: str,
) -> int:
    if plan.schema != "main" or plan.name != "fact_market_daily":
        return 0
    by_name = {(item.schema, item.name): item for item in plans}
    stock = by_name.get((plan.schema, "fact_stock_daily"))
    window = by_name.get((plan.schema, "feature_market_window"))
    if stock is None or window is None:
        return 0
    market_columns = {column.casefold() for column, _type in plan.columns}
    stock_columns = {column.casefold() for column, _type in stock.columns}
    window_columns = {column.casefold() for column, _type in window.columns}
    if not {
        "trade_date",
        "updated_at",
        "total_amount",
        "advancers",
        "limit_up",
        "limit_down",
        "note",
        "source",
    }.issubset(market_columns):
        return 0
    if not {"trade_date", "pct_chg", "amount", "updated_at"}.issubset(
        stock_columns
    ):
        return 0
    if not {
        "as_of_date",
        "start_date",
        "end_date",
        "advancers_end",
        "amount_avg",
        "calculated_at",
    }.issubset(window_columns):
        return 0

    cutoff_sql = f"{_quote_literal(cutoff_text)}::TIMESTAMPTZ"
    cutoff_date_sql = f"CAST({cutoff_sql} AS DATE)"
    target_name = _qualified(plan.schema, plan.name)
    source_market = _qualified(plan.schema, plan.name, database="source_db")
    source_stock = _qualified(
        stock.schema,
        stock.name,
        database="source_db",
    )
    source_window = _qualified(
        window.schema,
        window.name,
        database="source_db",
    )
    stock_total = "stock.total_amount"
    previous_total = (
        f"(SELECT t.{_quote_ident('total_amount')} FROM {target_name} t "
        f"WHERE t.{_quote_ident('trade_date')} < f.{_quote_ident('trade_date')} "
        f"ORDER BY t.{_quote_ident('trade_date')} DESC LIMIT 1)"
    )
    expressions: list[str] = []
    for column, data_type in plan.columns:
        lowered = column.casefold()
        if lowered == "trade_date":
            expression = f'f.{_quote_ident(column)}'
        elif lowered.startswith("strength_"):
            expression = _safe_component_expression(
                column=column,
                data_type=data_type,
                timestamp_column="strength_updated_at",
                available_columns=market_columns,
                cutoff_sql=cutoff_sql,
            )
        elif lowered.startswith("stock_high_"):
            expression = _safe_component_expression(
                column=column,
                data_type=data_type,
                timestamp_column="stock_high_updated_at",
                available_columns=market_columns,
                cutoff_sql=cutoff_sql,
            )
        elif lowered.startswith("sh_index_"):
            expression = _safe_component_expression(
                column=column,
                data_type=data_type,
                timestamp_column="sh_index_updated_at",
                available_columns=market_columns,
                cutoff_sql=cutoff_sql,
            )
        elif lowered == "total_amount":
            expression = stock_total
        elif lowered == "advancers":
            expression = "COALESCE(window_stats.advancers_end, stock.advancers)"
        elif lowered == "limit_up":
            expression = "stock.limit_up"
        elif lowered == "limit_down":
            expression = "stock.limit_down"
        elif lowered == "amount_ma20":
            expression = "window_stats.amount_avg"
        elif lowered == "amount_vs_yesterday_pct":
            expression = (
                f"(({stock_total} / NULLIF({previous_total}, 0)) - 1.0) * 100.0"
            )
        elif lowered == "volume_ratio":
            expression = (
                f"({stock_total} / NULLIF(window_stats.amount_avg, 0)) * 100.0"
            )
        elif lowered == "note":
            expression = _quote_literal(_PIT_DERIVED_MARKET_NOTE)
        elif lowered == "source":
            expression = _quote_literal(_PIT_DERIVED_MARKET_SOURCE)
        elif lowered == "updated_at":
            component_timestamps = [
                "stock.max_updated_at",
                "window_stats.max_calculated_at",
            ]
            for timestamp_column in (
                "strength_updated_at",
                "stock_high_updated_at",
                "sh_index_updated_at",
            ):
                if timestamp_column in market_columns:
                    timestamp = f'f.{_quote_ident(timestamp_column)}'
                    component_timestamps.append(
                        f"CASE WHEN {timestamp} IS NOT NULL "
                        f"AND CAST({timestamp} AS TIMESTAMPTZ) <= {cutoff_sql} "
                        f"THEN {timestamp} END"
                    )
            expression = "GREATEST(" + ", ".join(component_timestamps) + ")"
        else:
            expression = _null_as(data_type)
        expressions.append(f"{expression} AS {_quote_ident(column)}")

    before = int(
        connection.execute(f"SELECT COUNT(*) FROM {target_name}").fetchone()[0]
    )
    connection.execute(
        f"""
        INSERT INTO {target_name}
        WITH f AS (
            SELECT *
            FROM {source_market}
            WHERE CAST({_quote_ident('trade_date')} AS DATE) = {cutoff_date_sql}
              AND {_quote_ident('updated_at')} IS NOT NULL
              AND CAST({_quote_ident('updated_at')} AS TIMESTAMPTZ) > {cutoff_sql}
            ORDER BY {_quote_ident('updated_at')} DESC
            LIMIT 1
        ),
        stock AS (
            SELECT COUNT(*) AS row_count,
                   SUM({_quote_ident('amount')}) AS total_amount,
                   SUM(CASE WHEN {_quote_ident('pct_chg')} > 0 THEN 1 ELSE 0 END) AS advancers,
                   SUM(CASE WHEN {_quote_ident('pct_chg')} >= 9.8 THEN 1 ELSE 0 END) AS limit_up,
                   SUM(CASE WHEN {_quote_ident('pct_chg')} <= -9.8 THEN 1 ELSE 0 END) AS limit_down,
                   MAX({_quote_ident('updated_at')}) AS max_updated_at
            FROM {source_stock}
            WHERE CAST({_quote_ident('trade_date')} AS DATE) = {cutoff_date_sql}
              AND ({_quote_ident('updated_at')} IS NULL OR
                   CAST({_quote_ident('updated_at')} AS TIMESTAMPTZ) <= {cutoff_sql})
        ),
        window_stats AS (
            SELECT COUNT(*) AS row_count,
                   MAX({_quote_ident('advancers_end')}) AS advancers_end,
                   ARG_MAX({_quote_ident('amount_avg')}, {_quote_ident('start_date')})
                     FILTER (WHERE DATE_DIFF('day', {_quote_ident('start_date')},
                                             {_quote_ident('as_of_date')}) BETWEEN 20 AND 45)
                     AS amount_avg,
                   MAX({_quote_ident('calculated_at')}) AS max_calculated_at
            FROM {source_window}
            WHERE CAST({_quote_ident('as_of_date')} AS DATE) = {cutoff_date_sql}
              AND CAST({_quote_ident('end_date')} AS DATE) <= {cutoff_date_sql}
              AND ({_quote_ident('calculated_at')} IS NULL OR
                   CAST({_quote_ident('calculated_at')} AS TIMESTAMPTZ) <= {cutoff_sql})
        )
        SELECT {", ".join(expressions)}
        FROM f CROSS JOIN stock CROSS JOIN window_stats
        WHERE stock.row_count > 0
          AND window_stats.row_count > 0
          AND NOT EXISTS (
              SELECT 1 FROM {target_name} existing
              WHERE existing.{_quote_ident('trade_date')} = f.{_quote_ident('trade_date')}
          )
        """
    )
    after = int(
        connection.execute(f"SELECT COUNT(*) FROM {target_name}").fetchone()[0]
    )
    return max(0, after - before)


def audit_filtered_duckdb(receipt: FilteredDuckDBReceipt) -> FilteredDuckDBAudit:
    issues: list[str] = []
    target = receipt.target_path
    if not target.is_file() or target.is_symlink():
        return FilteredDuckDBAudit("invalid", ("target_missing_or_non_regular",))
    if receipt.source_path.resolve() == target.resolve():
        issues.append("source_target_path_alias")
    if target.stat().st_mode & 0o777 != 0o444:
        issues.append("target_mode")
    if _sha256_file(target) != receipt.target_sha256:
        issues.append("target_hash")
    duckdb = _duckdb()
    try:
        connection = duckdb.connect(str(target), read_only=True)
        connection.execute("SET TimeZone = 'Asia/Shanghai'")
        attached = connection.execute("PRAGMA database_list").fetchall()
        target_resolved = target.resolve()
        for row in attached:
            attached_path = str(row[-1] or "").strip()
            if attached_path and Path(attached_path).resolve() != target_resolved:
                issues.append("external_database_attached")
        objects = {
            (schema, name): kind for schema, name, kind in _user_objects(connection)
        }
        for table in receipt.tables:
            schema, name = table.name.split(".", 1)
            if objects.get((schema, name)) != "BASE TABLE":
                issues.append(f"missing_materialized_table:{table.name}")
                continue
            plan = _ObjectPlan(
                schema=schema,
                name=name,
                source_kind=table.source_kind,
                columns=_columns(connection, schema, name),
                temporal_columns=tuple(
                    (column, data_type)
                    for column, data_type in _columns(connection, schema, name)
                    if column in table.temporal_columns
                ),
                intraday_time_columns=table.intraday_time_columns,
                marker_exceptions=table.marker_exceptions,
                source_rows=table.source_rows,
            )
            rows = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {_qualified(schema, name)}"
                ).fetchone()[0]
            )
            if rows != table.target_rows:
                issues.append(f"row_count:{table.name}")
            if _maxima(connection, plan) != table.maxima:
                issues.append(f"temporal_maximum:{table.name}")
            if table.derivation is not None:
                expected_rows = int(table.derivation.get("derived_rows") or 0)
                if table.derivation.get("kind") != "pit_safe_market_base":
                    issues.append(f"derivation_kind:{table.name}")
                elif "source" not in {
                    column.casefold() for column, _type in plan.columns
                }:
                    issues.append(f"derivation_source_column:{table.name}")
                else:
                    derived_rows = int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {_qualified(schema, name)} "
                            f"WHERE {_quote_ident('source')} = ?",
                            [_PIT_DERIVED_MARKET_SOURCE],
                        ).fetchone()[0]
                    )
                    if derived_rows != expected_rows:
                        issues.append(f"derivation_row_count:{table.name}")
        connection.close()
    except Exception:
        issues.append("target_reopen_failed")
    return FilteredDuckDBAudit(
        "invalid" if issues else "valid",
        tuple(dict.fromkeys(issues)),
    )


def build_filtered_duckdb(
    source_path: str | Path,
    target_path: str | Path,
    *,
    as_of: str,
) -> FilteredDuckDBReceipt:
    """Build one physical DuckDB whose date-bearing rows stop at ``as_of``."""

    source = Path(source_path).expanduser().resolve()
    target = Path(target_path).expanduser().resolve()
    if not source.is_file() or source.is_symlink():
        raise ValueError("source DuckDB must be a regular file")
    if source == target:
        raise ValueError("source and target DuckDB paths must differ")
    if target.exists():
        raise FileExistsError("target DuckDB already exists")
    cutoff = _cutoff(as_of)
    cutoff_text = cutoff.isoformat(timespec="seconds")
    duckdb = _duckdb()
    source_connection = duckdb.connect(str(source), read_only=True)
    source_connection.execute("SET TimeZone = 'Asia/Shanghai'")
    try:
        plans = _plan_objects(source_connection)
    finally:
        source_connection.close()

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    receipts: list[TableCopyReceipt] = []
    try:
        connection = duckdb.connect(str(temporary))
        connection.execute("SET TimeZone = 'Asia/Shanghai'")
        connection.execute(
            f"ATTACH {_quote_literal(source)} AS source_db (READ_ONLY)"
        )
        try:
            for schema in sorted({plan.schema for plan in plans}):
                if schema != "main":
                    connection.execute(f"CREATE SCHEMA {_quote_ident(schema)}")
            for plan in plans:
                parameters = [cutoff_text] * len(plan.temporal_columns)
                source_name = _qualified(
                    plan.schema,
                    plan.name,
                    database="source_db",
                )
                target_name = _qualified(plan.schema, plan.name)
                connection.execute(
                    f"CREATE TABLE {target_name} AS "
                    f"SELECT * FROM {source_name} WHERE {_predicate(plan)}",
                    parameters,
                )
                derived_rows = _derive_cutoff_market_row(
                    connection,
                    plan=plan,
                    plans=plans,
                    cutoff_text=cutoff_text,
                )
                target_rows = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {target_name}"
                    ).fetchone()[0]
                )
                receipts.append(
                    TableCopyReceipt(
                        name=plan.qualified_name,
                        source_kind=plan.source_kind,
                        temporal_columns=tuple(
                            column for column, _data_type in plan.temporal_columns
                        ),
                        intraday_time_columns=plan.intraday_time_columns,
                        marker_exceptions=plan.marker_exceptions,
                        source_rows=plan.source_rows,
                        target_rows=target_rows,
                        maxima=_maxima(connection, plan),
                        derivation=(
                            {
                                "kind": "pit_safe_market_base",
                                "derived_rows": derived_rows,
                                "source_tables": [
                                    "fact_stock_daily",
                                    "feature_market_window",
                                ],
                            }
                            if derived_rows
                            else None
                        ),
                    )
                )
            connection.execute("DETACH source_db")
        finally:
            connection.close()
        temporary.chmod(0o444)
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise

    receipt = FilteredDuckDBReceipt(
        source_path=source,
        target_path=target,
        as_of=str(as_of),
        cutoff_timestamp=cutoff_text,
        tables=tuple(receipts),
        target_sha256=_sha256_file(target),
    )
    audit = audit_filtered_duckdb(receipt)
    if audit.status != "valid":
        target.chmod(0o600)
        target.unlink(missing_ok=True)
        raise ValueError("filtered DuckDB failed post-build audit: " + ",".join(audit.issues))
    return receipt
