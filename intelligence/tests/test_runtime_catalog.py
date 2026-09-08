"""三张运行底座目录必须与源码一致（终态稿 §6.1 P0 第 5 条，G8）。

红了就跑 ``python3 scripts/gen_runtime_catalog.py`` 并把 ``docs/runtime/*.md`` 一起提交。
这是「文档由源码生成、CI 保鲜」那条纪律在本仓的第一处落点。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = REPO_ROOT / "scripts" / "gen_runtime_catalog.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen_runtime_catalog", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_catalog_is_fresh() -> None:
    generator = _load_generator()
    stale = generator.check(REPO_ROOT / "docs" / "runtime", REPO_ROOT)
    assert stale == [], (
        f"docs/runtime 不新鲜: {stale}；运行 python3 scripts/gen_runtime_catalog.py 后一起提交"
    )


def test_runtime_catalog_is_a_pure_function_of_source() -> None:
    """两次渲染逐字节相同：不写时间戳、不写 revision、发射文件排序去重。"""

    generator = _load_generator()
    assert generator.render_all(REPO_ROOT) == generator.render_all(REPO_ROOT)


def test_event_catalog_covers_every_registered_kind_and_names_emitters() -> None:
    from intelligence.services.episode_event_lanes import (
        DURABLE_EVENT_KINDS,
        LIVE_EVENT_KINDS,
    )

    generator = _load_generator()
    rendered = generator.render_events(REPO_ROOT)
    for kind in DURABLE_EVENT_KINDS | LIVE_EVENT_KINDS:
        assert f"`{kind}`" in rendered, f"事件目录缺 {kind}"
    emitters = generator.emitter_files_by_kind(REPO_ROOT)
    # 三种模型可见载体的发射点都收口在 episode_messages（两条 loop 经它发）。
    for kind in ("prompt_assembled", "model_input", "tool_budget_state"):
        assert emitters[kind] == ["intelligence/services/episode_messages.py"], emitters[kind]
