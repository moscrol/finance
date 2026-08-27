"""V10 探针电池：全 mock HTTP，禁真联网，禁默认 8792。

题池用 tmp 内联 JSON，不读仓内 held-out 文件。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts import run_probe_battery as battery  # noqa: E402


def _inline_pool() -> dict:
    return {
        "id": "inline-mock",
        "questions": [
            {
                "id": "q1",
                "theme": "甲题材",
                "kind": "concept",
                "question": "甲题材现在怎么走",
            }
        ],
    }


def _episode(*, structural_title: bool = False) -> dict:
    title = "相关实体" if structural_title else "一句话"
    detail = "[[乙]]" if structural_title else "封测龙头做先进封装"
    return {
        "events": [
            {
                "kind": "tool_result",
                "payload": {
                    "tool": "kb_search",
                    "telemetry": {
                        "delivered_chars": 800,
                        "detail_chars": 2000,
                        "hit_count": 4,
                        "pointer_dropped": 1,
                        "reexcerpted": [True, False, True, False],
                    },
                },
            }
        ],
        "outcome": {
            "evidence": [
                {
                    "title": title,
                    "detail": detail,
                    "reexcerpted": not structural_title,
                },
                {
                    "title": "相关概念",
                    "detail": "[[丙]]",
                    "reexcerpted": False,
                },
            ]
        },
    }


def test_base_url_is_required_and_has_no_8792_default() -> None:
    parser = battery.build_parser()
    action = next(item for item in parser._actions if "--base-url" in item.option_strings)
    assert action.required is True
    assert action.default in {None, argparse.SUPPRESS}
    with pytest.raises(SystemExit):
        parser.parse_args(["--user", "probe"])


def test_http_refuses_under_pytest() -> None:
    with pytest.raises(RuntimeError, match="拒绝真联网"):
        battery.http_json("GET", "http://127.0.0.1:9/api/health")


def test_inspect_episode_rates_and_missing_is_none() -> None:
    metrics = battery.inspect_episode(_episode())
    assert metrics["reexcerpted_rate"] == pytest.approx(0.5)
    assert metrics["body_header_rate"] == pytest.approx(0.5)
    assert metrics["pointer_dropped_values"] == [1]
    assert metrics["telemetry"]["delivered_chars"] == [800]
    empty = battery.inspect_episode({"events": [], "outcome": {"evidence": []}})
    assert empty["reexcerpted_rate"] is None
    assert empty["body_header_rate"] is None


def test_body_header_rate_zero_when_all_structural() -> None:
    """正文头钉：全是结构节 title 时比率必须是 0。判定恒 True → 本条红。"""

    metrics = battery.inspect_episode(_episode(structural_title=True))
    assert metrics["body_header_rate"] == 0.0
    assert metrics["evidence"][0]["body_header"] is False
    assert metrics["evidence"][1]["body_header"] is False


def test_run_battery_mocks_http_and_reads_parameterized_runs(
    tmp_path: Path,
) -> None:
    runs = tmp_path / "runs"
    run_id = "run_20260822_000000_1"
    episode_dir = runs / run_id
    episode_dir.mkdir(parents=True)
    (episode_dir / "continuous-episode.json").write_text(
        json.dumps(_episode(), ensure_ascii=False),
        encoding="utf-8",
    )
    calls: list[tuple[str, str]] = []

    def fake_http(method: str, url: str, payload: dict | None = None, **_: object) -> object:
        calls.append((method, url))
        if url.endswith("/api/conversations") and method == "POST":
            assert payload == {"title": "甲题材现在怎么走", "user": "probe-x"}
            return {"conversation_id": "conv_1"}
        if url.endswith("/messages") and method == "POST":
            assert payload == {
                "content": "甲题材现在怎么走",
                "user": "probe-x",
                "skill_mode": "auto",
            }
            return {"run_id": run_id}
        if "messages?user=" in url:
            return [
                {
                    "role": "assistant",
                    "status": "completed",
                    "content": "公开答案",
                }
            ]
        raise AssertionError(url)

    report = battery.run_battery(
        base_url="http://127.0.0.1:8899",
        user="probe-x",
        pool=_inline_pool(),
        users_dir=tmp_path / "users",
        runs_dir=runs,
        timeout=5,
        poll_seconds=0,
        http=fake_http,
        sleeper=lambda _: None,
    )
    assert [item[0] for item in calls] == ["POST", "POST", "GET"]
    assert "8792" not in "".join(item[1] for item in calls)
    row = report["questions"][0]
    assert row["status"] == "completed"
    assert row["run_id"] == run_id
    assert row["reexcerpted_rate"] == pytest.approx(0.5)
    assert row["body_header_rate"] == pytest.approx(0.5)
    assert report["summary"]["n"] == 1
    assert report["summary"]["completed"] == 1
    assert "1" in report["summary"]["pointer_dropped_distribution"]
    text = battery.render_markdown(report)
    assert "reexcerpted" in text
    assert "body_header" in text


def test_load_pool_rejects_forbidden_and_too_small(tmp_path: Path) -> None:
    path = tmp_path / "pool.json"
    path.write_text(
        json.dumps(
            {
                "id": "bad",
                "questions": [
                    {
                        "id": "x",
                        "theme": "封测",
                        "kind": "stock",
                        "question": "长电科技怎么看",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="held-out 禁题"):
        battery.load_pool(path)
    tiny = tmp_path / "tiny.json"
    tiny.write_text(json.dumps({"id": "t", "questions": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="≥8"):
        battery.load_pool(tiny)
