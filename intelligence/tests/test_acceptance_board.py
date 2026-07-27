"""验收台账的回归测试。

锁住的核心 bug：/api/health 把运行时字段嵌在 ``runtime`` 下，早先版本按顶层读，
于是前置检查对着一个健康的服务报『finance_root 缺失』——一个报错报错了地方的
检查比没有检查更糟，因为它会把部署接缝和题目失败混在一起。
"""

from __future__ import annotations

import json

import pytest

from intelligence.eval import acceptance

HEALTHY = {
    "status": "healthy",
    "dependencies": {
        "repo_root": True,
        "knowledge_wiki": True,
        "relations": True,
        "market_snapshot": True,
    },
    "runtime": {
        "source_revision": "17e0b21a30182c707a0d204dfff1ed6dcbe53ca0",
        "finance_root": "/Users/a77/finance-workspace-private",
        "agent_runtime": {"backend": "sdk_gpt", "ready": True, "reason": None},
    },
}


def _stub_get(monkeypatch, health: dict, llm: dict) -> None:
    def fake_get(url: str, timeout: float = 30.0):
        if url.endswith("/api/health"):
            return health
        if url.endswith("/api/llm/config"):
            return llm
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(acceptance, "_get", fake_get)


def test_preflight_reads_nested_runtime_fields(monkeypatch):
    """健康服务必须判通过 —— 回归『按顶层读字段』那个 bug。"""
    _stub_get(monkeypatch, HEALTHY, {"ready": True})
    ok, detail = acceptance.preflight("http://stub")
    assert ok, f"healthy service must pass preflight, got: {detail}"
    assert "17e0b21a" in detail
    assert "sdk_gpt" in detail


def test_preflight_flags_missing_credential(monkeypatch):
    """凭据缺失必须被认成接缝问题，并带上 provider 给的 reason。"""
    health = json.loads(json.dumps(HEALTHY))
    health["runtime"]["agent_runtime"] = {
        "backend": "sdk_gpt",
        "ready": False,
        "reason": "openai_api_key_missing",
    }
    _stub_get(monkeypatch, health, {"ready": False})
    ok, detail = acceptance.preflight("http://stub")
    assert not ok
    assert "openai_api_key_missing" in detail
    assert "BYOK" in detail


def test_preflight_flags_broken_dependency(monkeypatch):
    health = json.loads(json.dumps(HEALTHY))
    health["dependencies"]["market_snapshot"] = False
    _stub_get(monkeypatch, health, {"ready": True})
    ok, detail = acceptance.preflight("http://stub")
    assert not ok
    assert "market_snapshot" in detail


def test_preflight_survives_slow_llm_config(monkeypatch):
    """llm/config 恒定阻塞约 6s；超时设置必须容得下，否则会自伤成『不可达』。"""

    def fake_get(url: str, timeout: float = 30.0):
        if url.endswith("/api/health"):
            return HEALTHY
        assert timeout >= 10, f"llm/config timeout too tight: {timeout}"
        return {"ready": True}

    monkeypatch.setattr(acceptance, "_get", fake_get)
    ok, _ = acceptance.preflight("http://stub")
    assert ok


def test_failure_classification_separates_seam_from_quality():
    """接缝失败不该算进题目分数 —— 否则修凭据会被误读成『题目变好了』。"""
    assert acceptance.classify_failure({"status": "timeout"}) == "接缝:超时"
    assert (
        acceptance.classify_failure(
            {"status": "error", "error": "openai_api_key missing"}
        )
        == "接缝:凭据"
    )
    assert (
        acceptance.classify_failure({"status": "error", "error": "urlopen refused"})
        == "接缝:服务/路由"
    )
    assert acceptance.classify_failure({"status": "complete"}) == "业务质量"


def test_cases_file_is_wellformed():
    doc = acceptance.load_cases()
    cases = doc["cases"]
    assert len(cases) == 28
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "case ids must be unique"
    tiers = {c["tier"] for c in cases}
    assert tiers == {"high_freq", "mid_freq", "long_tail"}
    for c in cases:
        assert c.get("pass_rule"), f"{c['id']} 缺 pass_rule：没有通过标准的题不算题"


def test_freeze_refuses_silent_overwrite(tmp_path, monkeypatch):
    """参照快照一旦冻结不得被悄悄重生成 —— 否则被测方兼当出题人。"""
    monkeypatch.setattr(acceptance, "SNAPSHOT_DIR", tmp_path)
    answer = tmp_path / "ans.md"
    answer.write_text("电网设备 +6.65%", encoding="utf-8")
    args = acceptance.argparse.Namespace(
        case_id="A4-dual-red",
        agent="codex",
        answer_file=str(answer),
        overwrite=False,
    )
    assert acceptance.cmd_freeze(args) == 0
    assert acceptance.cmd_freeze(args) == 2, "second freeze must be refused"
    args.overwrite = True
    assert acceptance.cmd_freeze(args) == 0


def test_freeze_rejects_unknown_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, "SNAPSHOT_DIR", tmp_path)
    answer = tmp_path / "ans.md"
    answer.write_text("x", encoding="utf-8")
    args = acceptance.argparse.Namespace(
        case_id="A4-dual-red",
        agent="itself",
        answer_file=str(answer),
        overwrite=False,
    )
    assert acceptance.cmd_freeze(args) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
