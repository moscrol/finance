from pathlib import Path

import pytest

from intelligence.api.artifacts import ArtifactRegistry
from intelligence.services.run_store import RunStore


def _registry(tmp_path: Path) -> tuple[ArtifactRegistry, RunStore]:
    store = RunStore(user_id="default", root=tmp_path / "users" / "default" / "runs")
    return ArtifactRegistry(repo_root=tmp_path, run_store=store), store


def test_registry_discovers_known_providers_and_run_artifacts(tmp_path: Path) -> None:
    daily_dir = tmp_path / "复盘" / "daily" / "2026-07-09"
    daily_dir.mkdir(parents=True)
    (daily_dir / "2026-07-09-daily-agent.html").write_text("<h1>daily</h1>", encoding="utf-8")
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    (exports / "2026-07-09-daily-agent.json").write_text("{}", encoding="utf-8")

    matrix_dir = tmp_path / "复盘" / "matrices"
    matrix_dir.mkdir(parents=True)
    (matrix_dir / "strategy1-priority-stock-matrix.md").write_text("# matrix", encoding="utf-8")
    (matrix_dir / "strategy1-priority-stock-matrix.html").write_text("<h1>matrix</h1>", encoding="utf-8")

    registry, store = _registry(tmp_path)
    run = store.create_run("测试", "ask")
    store.add_artifact(run.run_id, "answer.md", "# answer", renderer="markdown", title="回答")
    store.finish_run(run.run_id, "completed")

    artifacts = registry.list()
    assert len({item.artifact_id for item in artifacts}) == len(artifacts)
    assert any(item.category == "daily_agent" and item.status == "ok" for item in artifacts)
    assert any(item.category == "strategy_matrix" and item.canonical_exists for item in artifacts)
    assert any(item.category == "run" and item.related_run_id == run.run_id for item in artifacts)
    assert all(not item.source_path.startswith("/") for item in artifacts)


def test_run_artifact_uses_research_date_and_readable_source(tmp_path: Path) -> None:
    registry, store = _registry(tmp_path)
    run = store.create_run("复盘最新交易日的市场结构和主要风险", "ask")
    store.update_provenance(
        run.run_id,
        source_date="2026-07-10",
        duckdb_cutoff="2026-07-09",
    )
    store.add_artifact(
        run.run_id,
        "answer.md",
        "# answer",
        renderer="markdown",
        title="回答",
    )
    store.finish_run(run.run_id, "completed")

    descriptor = next(
        item
        for item in registry.list(category="run")
        if item.related_run_id == run.run_id
    )

    assert descriptor.date == "2026-07-10"
    assert descriptor.source_label == "研究任务：复盘最新交易日的市场结构和主要风险"
    assert descriptor.source_of_truth == f"run:{run.run_id}"
    assert descriptor.related_run_id == run.run_id


def test_run_artifact_date_falls_back_to_cutoff_then_creation_date(
    tmp_path: Path,
) -> None:
    registry, store = _registry(tmp_path)
    cutoff_run = store.create_run("按数据截止日生成", "ask")
    store.update_provenance(cutoff_run.run_id, duckdb_cutoff="2026-07-09")
    created_run = store.create_run("按创建日生成", "ask")
    for run in (cutoff_run, created_run):
        store.add_artifact(
            run.run_id,
            "answer.md",
            "# answer",
            renderer="markdown",
            title="回答",
        )
        store.finish_run(run.run_id, "completed")

    descriptors = {
        item.related_run_id: item
        for item in registry.list(category="run")
        if item.related_run_id in {cutoff_run.run_id, created_run.run_id}
    }

    assert descriptors[cutoff_run.run_id].date == "2026-07-09"
    assert descriptors[created_run.run_id].date == created_run.created_at[:10]


def test_registry_filters_and_sorts_latest_first(tmp_path: Path) -> None:
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    for date in ("2026-07-08", "2026-07-09"):
        (exports / f"{date}-theme-candidates.md").write_text(f"# {date}", encoding="utf-8")

    registry, _ = _registry(tmp_path)
    filtered = registry.list(category="theme_candidates", date="2026-07-09", query="题材")
    assert [item.date for item in filtered] == ["2026-07-09"]
    assert registry.list(category="theme_candidates")[0].date == "2026-07-09"


def test_registry_keeps_known_artifact_as_missing_after_deletion(tmp_path: Path) -> None:
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    path = exports / "2026-07-09-daily-agent.md"
    path.write_text("# daily", encoding="utf-8")

    registry, _ = _registry(tmp_path)
    descriptor = next(item for item in registry.list() if item.source_path.endswith("daily-agent.md"))
    path.unlink()

    missing = registry.get(descriptor.artifact_id)
    assert missing is not None
    assert missing.status == "missing"
    assert registry.list(status="missing")


def test_registry_registers_missing_cockpit_without_exposing_arbitrary_path(tmp_path: Path) -> None:
    registry, _ = _registry(tmp_path)
    cockpit = next(item for item in registry.list(category="cockpit") if item.title == "驾驶舱总入口")
    assert cockpit.status == "missing"
    assert cockpit.source_path == "复盘/index.html"
    assert registry.get("../etc/passwd") is None


def test_content_path_is_only_resolved_from_registered_descriptor(tmp_path: Path) -> None:
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    path = exports / "2026-07-09-theme-candidates.md"
    path.write_text("# themes", encoding="utf-8")

    registry, _ = _registry(tmp_path)
    descriptor = next(item for item in registry.list() if item.source_path.endswith("theme-candidates.md"))
    resolved_descriptor, resolved = registry.content_path(descriptor.artifact_id)
    assert resolved_descriptor.artifact_id == descriptor.artifact_id
    assert resolved == path.resolve()


def test_canonical_path_is_only_resolved_from_registered_descriptor(tmp_path: Path) -> None:
    daily_dir = tmp_path / "复盘" / "daily" / "2026-07-09"
    daily_dir.mkdir(parents=True)
    html_path = daily_dir / "2026-07-09-daily-review.html"
    markdown_path = daily_dir / "2026-07-09-daily-review.md"
    html_path.write_text("<h1>review</h1>", encoding="utf-8")
    markdown_path.write_text("# review", encoding="utf-8")

    registry, _ = _registry(tmp_path)
    descriptor = next(
        item
        for item in registry.list(category="daily_review")
        if item.content_path == html_path.resolve()
    )
    resolved_descriptor, canonical = registry.canonical_path(descriptor.artifact_id)

    assert resolved_descriptor.artifact_id == descriptor.artifact_id
    assert canonical == markdown_path.resolve()
    assert registry.get(markdown_path.as_posix()) is None


def test_asset_path_stays_in_registered_artifact_directory(tmp_path: Path) -> None:
    daily_dir = tmp_path / "复盘" / "daily" / "2026-07-09"
    daily_dir.mkdir(parents=True)
    html_path = daily_dir / "2026-07-09-daily-review.html"
    chart_path = daily_dir / "chart.png"
    html_path.write_text("<img src='chart.png'>", encoding="utf-8")
    chart_path.write_bytes(b"png")
    secret = tmp_path / "复盘" / "secret.txt"
    secret.write_text("secret", encoding="utf-8")
    (daily_dir / "escaped.txt").symlink_to(secret)

    registry, _ = _registry(tmp_path)
    descriptor = next(
        item
        for item in registry.list(category="daily_review")
        if item.content_path == html_path.resolve()
    )

    resolved_descriptor, asset = registry.asset_path(descriptor.artifact_id, "chart.png")
    assert resolved_descriptor.artifact_id == descriptor.artifact_id
    assert asset == chart_path.resolve()
    with pytest.raises(PermissionError):
        registry.asset_path(descriptor.artifact_id, "../secret.txt")
    with pytest.raises(PermissionError):
        registry.asset_path(descriptor.artifact_id, "escaped.txt")


def test_daily_agent_markdown_uses_json_as_canonical_source(tmp_path: Path) -> None:
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    markdown = exports / "2026-07-09-daily-agent.md"
    canonical = exports / "2026-07-09-daily-agent.json"
    markdown.write_text("# Daily Agent", encoding="utf-8")
    canonical.write_text('{"date":"2026-07-09"}', encoding="utf-8")

    registry, _ = _registry(tmp_path)
    descriptor = next(
        item
        for item in registry.list(category="daily_agent")
        if item.content_path == markdown.resolve()
    )

    assert descriptor.source_of_truth == (
        "market_feature_store/exports/2026-07-09-daily-agent.json"
    )
    assert registry.canonical_path(descriptor.artifact_id)[1] == canonical.resolve()
