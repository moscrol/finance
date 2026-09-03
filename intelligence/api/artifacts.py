"""Read-only artifact registry for the Agent Workbench."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Iterable, Protocol

from intelligence.services.run_store import RunStore, artifact_visibility

SCHEMA_VERSION = 1
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
VIEWER_BY_SUFFIX = {
    ".md": "native_markdown",
    ".json": "native_json",
    ".html": "legacy_html",
}
FORMAT_BY_SUFFIX = {
    ".md": "markdown",
    ".json": "json",
    ".html": "html",
}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _iso_mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def _date_from_path(path: Path) -> str | None:
    match = DATE_RE.search(path.name) or DATE_RE.search(path.as_posix())
    return match.group(1) if match else None


def _artifact_id(category: str, source_path: str, fmt: str, date: str | None) -> str:
    digest = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:10]
    return f"{category}:{date or 'undated'}:{fmt}:{digest}"


def _title_for(path: Path, fallback: str) -> str:
    date = _date_from_path(path)
    return f"{fallback} - {date}" if date else fallback


@dataclass(frozen=True)
class ArtifactDescriptor:
    artifact_id: str
    title: str
    category: str
    format: str
    date: str | None
    viewer: str
    source_of_truth: str | None
    source_label: str | None
    source_path: str
    related_run_id: str | None
    status: str
    schema_version: int
    updated_at: str | None
    canonical_exists: bool
    content_path: Path = field(repr=False, compare=False)

    def public_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "title": self.title,
            "category": self.category,
            "format": self.format,
            "date": self.date,
            "viewer": self.viewer,
            "source_of_truth": self.source_of_truth,
            "source_label": self.source_label,
            "source_path": self.source_path,
            "related_run_id": self.related_run_id,
            "status": self.status,
            "schema_version": self.schema_version,
            "updated_at": self.updated_at,
            "canonical_exists": self.canonical_exists,
        }


@dataclass(frozen=True)
class ProviderContext:
    repo_root: Path
    run_store: RunStore

    def repo_relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.repo_root.resolve()).as_posix()


class ArtifactProvider(Protocol):
    def discover(self, context: ProviderContext) -> Iterable[ArtifactDescriptor]: ...


def _descriptor(
    context: ProviderContext,
    path: Path,
    *,
    title: str,
    category: str,
    source_of_truth: str | None = None,
    source_label: str | None = None,
    related_run_id: str | None = None,
    source_path: str | None = None,
    viewer: str | None = None,
    artifact_date: str | None = None,
) -> ArtifactDescriptor:
    resolved = path.resolve()
    public_path = source_path or context.repo_relative(path)
    suffix = path.suffix.lower()
    fmt = FORMAT_BY_SUFFIX.get(suffix, suffix.removeprefix(".") or "file")
    canonical_exists = False
    if source_of_truth:
        if source_of_truth.startswith(("run:", "user:")):
            canonical_exists = True
        else:
            canonical_exists = (context.repo_root / source_of_truth).is_file()
    status = "missing" if not resolved.is_file() else ("ok" if canonical_exists else "warn")
    date = artifact_date or _date_from_path(path)
    return ArtifactDescriptor(
        artifact_id=_artifact_id(category, public_path, fmt, date),
        title=title,
        category=category,
        format=fmt,
        date=date,
        viewer=viewer or VIEWER_BY_SUFFIX.get(suffix, "download"),
        source_of_truth=source_of_truth,
        source_label=source_label,
        source_path=public_path,
        related_run_id=related_run_id,
        status=status,
        schema_version=SCHEMA_VERSION,
        updated_at=_iso_mtime(resolved),
        canonical_exists=canonical_exists,
        content_path=resolved,
    )


def _daily_kind(path: Path) -> tuple[str, str] | None:
    name = path.stem
    mapping = (
        ("daily-agent", "daily_agent", "每日 Agent 简报"),
        ("research-queue", "research_queue", "研究队列"),
        ("daily-review", "daily_review", "每日复盘"),
        ("theme-candidates", "theme_candidates", "题材候选"),
        ("daily-workflow-summary", "daily_review", "每日工作流摘要"),
        ("dual-blind-compare", "dual_blind", "双盲对照"),
    )
    for marker, category, title in mapping:
        if marker in name:
            return category, title
    return None


def _daily_canonical(context: ProviderContext, path: Path, category: str) -> str | None:
    date = _date_from_path(path)
    if not date:
        return context.repo_relative(path) if path.suffix in {".md", ".json"} else None
    exports = context.repo_root / "market_feature_store" / "exports"
    candidates = {
        "daily_agent": [exports / f"{date}-daily-agent.json", exports / f"{date}-daily-agent.md"],
        "research_queue": [
            exports / f"{date}-research-queue.json",
            exports / f"{date}-research-queue.md",
        ],
        "theme_candidates": [
            exports / f"{date}-theme-candidates.json",
            exports / f"{date}-theme-candidates.md",
        ],
        "daily_review": [
            exports / f"{date}-daily-review.json",
            path.with_suffix(".md"),
            exports / f"{date}-daily-review.md",
        ],
        "dual_blind": [
            context.repo_root / "docs" / "learning" / "forecast-review-ledger" / f"{date}.verdict.json",
            context.repo_root / "docs" / "learning" / "forecast-review-ledger" / f"{date}.manifest.json",
        ],
    }
    if path.suffix in {".md", ".json"} and not (
        category in {"daily_agent", "research_queue"} and path.suffix == ".md"
    ):
        return context.repo_relative(path)
    for candidate in candidates.get(category, []):
        if candidate.is_file():
            return context.repo_relative(candidate)
    return None


class RunArtifactProvider:
    def discover(self, context: ProviderContext) -> Iterable[ArtifactDescriptor]:
        for run in context.run_store.list_runs():
            run_dir = context.run_store.run_dir(run.run_id).resolve()
            for artifact in run.artifacts:
                if artifact_visibility(artifact) != "public":
                    continue
                relative = str(artifact.get("path") or "")
                path = (run_dir / relative).resolve()
                if not relative or not _is_within(path, run_dir):
                    continue
                renderer = str(artifact.get("renderer") or "")
                viewer = {
                    "markdown": "native_markdown",
                    "json": "native_json",
                    "html": "legacy_html",
                }.get(renderer, VIEWER_BY_SUFFIX.get(path.suffix.lower(), "download"))
                question = re.sub(r"\s+", " ", run.question).strip()
                source_label = (
                    f"研究任务：{question[:48]}{'…' if len(question) > 48 else ''}"
                    if question
                    else "研究任务"
                )
                yield _descriptor(
                    context,
                    path,
                    title=str(artifact.get("title") or relative),
                    category="run",
                    source_of_truth=f"run:{run.run_id}",
                    source_label=source_label,
                    source_path=f"user:{context.run_store.user_id}/runs/{run.run_id}/{relative}",
                    related_run_id=run.run_id,
                    viewer=viewer,
                    artifact_date=(
                        run.source_date
                        or run.duckdb_cutoff
                        or run.created_at[:10]
                    ),
                )


class DailyArtifactProvider:
    def discover(self, context: ProviderContext) -> Iterable[ArtifactDescriptor]:
        daily_root = context.repo_root / "复盘" / "daily"
        for suffix in ("*.html", "*.md"):
            for path in sorted(daily_root.glob(f"*/{suffix}")):
                if "market-triggered-theme-brief" in path.name:
                    continue
                kind = _daily_kind(path)
                if not kind:
                    continue
                category, title = kind
                yield _descriptor(
                    context,
                    path,
                    title=_title_for(path, title),
                    category=category,
                    source_of_truth=_daily_canonical(context, path, category),
                )

        exports = context.repo_root / "market_feature_store" / "exports"
        patterns = (
            "*-daily-agent.md",
            "*-daily-agent.json",
            "*-research-queue.md",
            "*-research-queue.json",
            "*-theme-candidates.md",
            "*-theme-candidates.json",
            "*-daily-workflow-summary.json",
        )
        seen: set[Path] = set()
        for pattern in patterns:
            for path in sorted(exports.glob(pattern)):
                if path in seen:
                    continue
                seen.add(path)
                kind = _daily_kind(path)
                if not kind:
                    continue
                category, title = kind
                yield _descriptor(
                    context,
                    path,
                    title=_title_for(path, title),
                    category=category,
                    source_of_truth=_daily_canonical(context, path, category),
                )


class CockpitArtifactProvider:
    FILES = (
        ("复盘/index.html", "驾驶舱总入口", "cockpit", None),
        (
            "复盘/matrices/strategy-review-workbench.html",
            "策略复盘工作台",
            "cockpit",
            "复盘/matrices/strategy1-priority-stock-matrix.html",
        ),
    )

    def discover(self, context: ProviderContext) -> Iterable[ArtifactDescriptor]:
        for relative, title, category, canonical in self.FILES:
            path = context.repo_root / relative
            yield _descriptor(
                context,
                path,
                title=title,
                category=category,
                source_of_truth=(
                    canonical
                    if canonical is not None and (context.repo_root / canonical).is_file()
                    else None
                ),
            )


class LedgerArtifactProvider:
    def discover(self, context: ProviderContext) -> Iterable[ArtifactDescriptor]:
        root = context.repo_root / "docs" / "learning" / "forecast-review-ledger"
        for path in sorted(root.glob("*.html")) + sorted(root.glob("20??-??-??.md")):
            if path.name == "index.html":
                title = "双盲与预测回检台账"
                canonical = "docs/learning/forecast-review-ledger/index.md"
            elif path.name == "calendar.html":
                title = "预测回检日历"
                canonical = "docs/learning/forecast-review-ledger/index.md"
            else:
                title = _title_for(path, "预测回检")
                date = _date_from_path(path)
                verdict = root / f"{date}.verdict.json" if date else None
                manifest = root / f"{date}.manifest.json" if date else None
                source = verdict if verdict and verdict.is_file() else manifest
                canonical = context.repo_relative(source) if source and source.is_file() else None
                if path.suffix == ".md":
                    canonical = context.repo_relative(path)
            yield _descriptor(
                context,
                path,
                title=title,
                category="forecast_ledger",
                source_of_truth=canonical,
            )

        for path in sorted((context.repo_root / "复盘" / "winrate").glob("*.html")):
            yield _descriptor(
                context,
                path,
                title=_title_for(path, "胜率复盘"),
                category="forecast_ledger",
                source_of_truth=None,
            )


class MatrixArtifactProvider:
    def discover(self, context: ProviderContext) -> Iterable[ArtifactDescriptor]:
        root = context.repo_root / "复盘" / "matrices"
        for path in sorted(root.glob("*")):
            if not path.is_file() or path.suffix.lower() not in {".html", ".md"}:
                continue
            if path.name == "strategy-review-workbench.html":
                continue
            canonical = context.repo_relative(path)
            if path.suffix == ".md":
                html_sibling = path.with_suffix(".html")
                if html_sibling.is_file():
                    canonical = context.repo_relative(html_sibling)
            yield _descriptor(
                context,
                path,
                title=path.stem.replace("-", " "),
                category="strategy_matrix",
                source_of_truth=canonical,
            )


class BriefingArtifactProvider:
    def discover(self, context: ProviderContext) -> Iterable[ArtifactDescriptor]:
        daily_root = context.repo_root / "复盘" / "daily"
        for path in sorted(daily_root.glob("*/*-market-triggered-theme-brief.html")):
            date = _date_from_path(path)
            canonical_path = (
                context.repo_root / "market_feature_store" / "exports" / f"{date}-market-triggered-theme-brief.md"
                if date
                else None
            )
            canonical = (
                context.repo_relative(canonical_path)
                if canonical_path and canonical_path.is_file()
                else None
            )
            yield _descriptor(
                context,
                path,
                title=_title_for(path, "盘面触发题材简报"),
                category="briefing",
                source_of_truth=canonical,
            )

        exports = context.repo_root / "market_feature_store" / "exports"
        for pattern in ("*-market-triggered-theme-brief.md",):
            for path in sorted(exports.glob(pattern)):
                yield _descriptor(
                    context,
                    path,
                    title=_title_for(path, "研究简报"),
                    category="briefing",
                    source_of_truth=context.repo_relative(path),
                )


DEFAULT_PROVIDERS: tuple[ArtifactProvider, ...] = (
    RunArtifactProvider(),
    DailyArtifactProvider(),
    CockpitArtifactProvider(),
    LedgerArtifactProvider(),
    MatrixArtifactProvider(),
    BriefingArtifactProvider(),
)


class ArtifactRegistry:
    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        run_store: RunStore | None = None,
        providers: Iterable[ArtifactProvider] | None = None,
    ) -> None:
        self.repo_root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
        self.run_store = run_store or RunStore()
        self.providers = tuple(providers or DEFAULT_PROVIDERS)
        self._known: dict[str, ArtifactDescriptor] = {}

    def refresh(self) -> None:
        context = ProviderContext(self.repo_root, self.run_store)
        discovered: dict[str, ArtifactDescriptor] = {}
        for provider in self.providers:
            for descriptor in provider.discover(context):
                if not self._allowed(descriptor.content_path):
                    continue
                discovered[descriptor.artifact_id] = descriptor
        for artifact_id, descriptor in self._known.items():
            if artifact_id not in discovered:
                # RunArtifactProvider deliberately omits internal artifacts.  Do
                # not resurrect a previously public run descriptor as a
                # ``missing`` item: a visibility transition must remove the
                # descriptor from every public projection, including a warm
                # registry cache.  File-backed providers retain their missing
                # entries so the UI can explain deleted/optional artifacts.
                if descriptor.category == "run":
                    continue
                discovered[artifact_id] = replace(
                    descriptor,
                    status="missing",
                    updated_at=None,
                )
        self._known = discovered

    def list(
        self,
        *,
        category: str | None = None,
        date: str | None = None,
        status: str | None = None,
        query: str | None = None,
    ) -> list[ArtifactDescriptor]:
        self.refresh()
        items = list(self._known.values())
        if category:
            items = [item for item in items if item.category == category]
        if date:
            items = [item for item in items if item.date == date]
        if status:
            items = [item for item in items if item.status == status]
        if query:
            needle = query.casefold()
            items = [
                item
                for item in items
                if needle in item.title.casefold()
                or needle in item.source_path.casefold()
                or needle in item.category.casefold()
            ]
        return sorted(
            items,
            key=lambda item: (item.date or "", item.updated_at or "", item.title),
            reverse=True,
        )

    def get(self, artifact_id: str) -> ArtifactDescriptor | None:
        self.refresh()
        descriptor = self._known.get(artifact_id)
        if descriptor and not descriptor.content_path.is_file():
            return replace(descriptor, status="missing", updated_at=None)
        return descriptor

    def content_path(self, artifact_id: str) -> tuple[ArtifactDescriptor, Path]:
        descriptor = self.get(artifact_id)
        if descriptor is None:
            raise KeyError(artifact_id)
        if descriptor.status == "missing" or not descriptor.content_path.is_file():
            raise FileNotFoundError(artifact_id)
        path = descriptor.content_path.resolve()
        if not self._allowed(path):
            raise PermissionError(artifact_id)
        return descriptor, path

    def canonical_path(self, artifact_id: str) -> tuple[ArtifactDescriptor, Path]:
        descriptor = self.get(artifact_id)
        if descriptor is None:
            raise KeyError(artifact_id)
        source = descriptor.source_of_truth
        if not source or source.startswith(("run:", "user:")):
            raise FileNotFoundError(artifact_id)
        path = (self.repo_root / source).resolve()
        if not _is_within(path, self.repo_root):
            raise PermissionError(artifact_id)
        if not path.is_file():
            raise FileNotFoundError(artifact_id)
        return descriptor, path

    def asset_path(
        self, artifact_id: str, asset_path: str
    ) -> tuple[ArtifactDescriptor, Path]:
        descriptor, content = self.content_path(artifact_id)
        if descriptor.viewer != "legacy_html":
            raise PermissionError(artifact_id)
        requested = Path(asset_path)
        if requested.is_absolute():
            raise PermissionError(asset_path)
        root = content.parent.resolve()
        path = (root / requested).resolve()
        if not _is_within(path, root):
            raise PermissionError(asset_path)
        if not path.is_file():
            raise FileNotFoundError(asset_path)
        return descriptor, path

    def _allowed(self, path: Path) -> bool:
        return _is_within(path, self.repo_root) or _is_within(path, self.run_store.root)
