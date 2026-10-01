"""模型准入闸（2026-10-01 质检 P0③）：请求的模型与对端实际服务的模型逐回合比对。"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from intelligence.runtime.glm_agent_runtime import GLMModelClient
from intelligence.services import llm_refine
from intelligence.services.agent_runtime import ModelTurn, served_model_mismatch
from intelligence.services.llm_refine import LLMProvider

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("requested", "served", "expected"),
    [
        ("glm-5.3", "glm-5.3", False),
        ("GLM-5.3", "glm-5.3", False),
        ("zhipu/glm-5.3", "glm-5.3", False),  # 路由前缀
        ("glm-5.3-flash:low", "glm-5.3-flash", False),  # 思考强度后缀
        ("gpt-4o", "gpt-4o-2024-08-06", False),  # 对端回带日期快照
        ("glm-5.3", "glm-5.3-flash", True),  # 09-29 的事故：必须判不一致
        ("glm-5.2", "gpt-5.6-sol", True),  # 08-08 的事故
        ("glm-5.3-flash", "glm-5.3", True),
        ("glm-5.3", "", None),  # 中转没回 model 字段：判不了 ≠ 通过
        ("glm-5.3", None, None),
        (None, "glm-5.3", None),
    ],
)
def test_served_model_mismatch(requested, served, expected) -> None:
    assert served_model_mismatch(requested, served) is expected


def test_model_turn_records_requested_and_flags_mismatch() -> None:
    turn = ModelTurn("x", (), "glm", served_model="glm-5.3-flash", requested_model="glm-5.3")
    payload = turn.to_dict()
    assert payload["requested_model"] == "glm-5.3"
    assert payload["served_model_mismatch"] is True
    ok = ModelTurn("x", (), "glm", served_model="glm-5.3", requested_model="glm-5.3").to_dict()
    assert "served_model_mismatch" not in ok
    legacy = ModelTurn("x", ()).to_dict()
    assert "requested_model" not in legacy  # 没请求信息时字段缺席，旧事件形状不变


def _provider(model: str) -> LLMProvider:
    return LLMProvider(name="glm", api_key="k", base_url="https://glm.invalid/v1", model=model)


def test_adapter_stamps_requested_model_and_warns(monkeypatch, caplog) -> None:
    provider = _provider("glm-5.3")
    monkeypatch.setattr(
        llm_refine,
        "chat_with_tools",
        lambda **_kw: ({"content": "ok", "tool_calls": [], "_served_model": "glm-5.3-flash"}, provider, ""),
    )
    monkeypatch.setattr(llm_refine, "writer_model_override", lambda: None)
    with caplog.at_level(logging.WARNING):
        turn = GLMModelClient(providers=(provider,)).complete(messages=[], tools=[], timeout=30)
    assert turn.requested_model == "glm-5.3"
    assert turn.served_model == "glm-5.3-flash"
    assert turn.to_dict()["served_model_mismatch"] is True
    assert "served_model_mismatch" in caplog.text


def test_adapter_requested_model_follows_writer_override(monkeypatch) -> None:
    provider = _provider("glm-5.2")
    seen = {}

    def chat_with_tools(**kwargs):
        seen["model_override"] = kwargs["model_override"]
        return {"content": "ok", "tool_calls": [], "_served_model": "glm-5.3"}, provider, ""

    monkeypatch.setattr(llm_refine, "chat_with_tools", chat_with_tools)
    monkeypatch.setattr(llm_refine, "writer_model_override", lambda: "glm-5.3")
    turn = GLMModelClient(providers=(provider,)).complete(messages=[], tools=[], timeout=30)
    assert seen["model_override"] == turn.requested_model == "glm-5.3"
    assert "served_model_mismatch" not in turn.to_dict()


def _write_events(path: Path, turns: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"kind": "configure", "sequence": 0, "payload": {}}]
    rows += [{"kind": "model_turn", "sequence": i + 1, "payload": t} for i, t in enumerate(turns)]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "check_served_model.py"), *args],
        capture_output=True, text=True, check=False,
    )


def test_cli_exit_codes(tmp_path: Path) -> None:
    good = tmp_path / "good" / "ep1" / "events.jsonl"
    _write_events(good, [{"requested_model": "glm-5.3", "served_model": "glm-5.3", "provider_attempts": 1}])
    assert _cli(str(tmp_path / "good")).returncode == 0

    bad = tmp_path / "bad" / "ep1" / "events.jsonl"
    _write_events(bad, [
        {"requested_model": "glm-5.3", "served_model": "glm-5.3", "provider_attempts": 1},
        {"requested_model": "glm-5.3", "served_model": "glm-5.3-flash", "provider_attempts": 1},
    ])
    result = _cli(str(tmp_path / "bad"))
    assert result.returncode == 1 and "glm-5.3-flash" in result.stderr

    # 旧事件没有 requested_model：用 --expect 指定；判不了的回合 --strict 才拦
    old = tmp_path / "old" / "ep1" / "events.jsonl"
    _write_events(old, [
        {"served_model": "glm-5.3-flash", "provider_attempts": 1},
        {"served_model": "", "provider_attempts": 1},
    ])
    assert _cli(str(tmp_path / "old"), "--expect", "glm-5.3").returncode == 1
    assert _cli(str(tmp_path / "old"), "--expect", "glm-5.3-flash").returncode == 0
    assert _cli(str(tmp_path / "old"), "--expect", "glm-5.3-flash", "--strict").returncode == 2

    (tmp_path / "empty").mkdir()
    assert _cli(str(tmp_path / "empty")).returncode == 3
