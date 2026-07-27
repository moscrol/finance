"""验收台账的回归测试。

锁住的核心 bug：/api/health 把运行时字段嵌在 ``runtime`` 下，早先版本按顶层读，
于是前置检查对着一个健康的服务报『finance_root 缺失』——一个报错报错了地方的
检查比没有检查更糟，因为它会把部署接缝和题目失败混在一起。
"""

from __future__ import annotations

import hashlib
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
    assert acceptance.classify_failure({"status": "completed"}) == "业务质量"


def test_zero_evidence_degrade_is_quality_not_seam():
    """零证据降级是检索/绑定缺陷（疑似假拒答），不是环境没配好。

    实测 A4「2026-07-23 双红板块有哪些」——库里数据齐全且已核验——runtime
    绑定 0 条证据直接降级拒答。这类失败若归进接缝账，会被误判成"等凭据好了
    就自然好了"，从而永远查不到真正的检索缺陷。
    """
    turn = {
        "status": "completed",
        "degrades": ["证据或语义核验未完全通过，已按证据边界降级。"],
        "evidence_bound": 0,
    }
    assert acceptance.classify_failure(turn) == "业务质量:零证据降级"
    # 绑到证据后又降级是另一回事，不套用零证据结论
    assert acceptance.classify_failure({**turn, "evidence_bound": 6}) == "业务质量"


def test_turn_trace_reads_runtime_field_names():
    """探针字段名必须对齐 runtime 真实返回，否则轨迹恒为空却看不出来。

    锁的是一次真实踩坑：消息体只给 invoked_skill_ids / citations / degrades，
    早先版本读 tools_called，于是看板显示 tools=0 —— 不是真没调工具，是探针
    探错了地方。一个恒为空的观测位比没有观测位更危险。
    """
    fields = acceptance.TurnTrace.__dataclass_fields__
    assert "tools_called" not in fields, "runtime 不返回该字段，别自创"
    for name in (
        "run_id",
        "invoked_skill_ids",
        "citations",
        "degrades",
        "evidence_bound",
        "gaps",
    ):
        assert name in fields, f"缺 {name}：这是判零证据降级的必要字段"


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
        via="codex_exec",
        asked_at=None,
        overwrite=False,
    )
    assert acceptance.cmd_freeze(args) == 0
    assert acceptance.cmd_freeze(args) == 2, "second freeze must be refused"
    args.overwrite = True
    assert acceptance.cmd_freeze(args) == 0


def test_freeze_records_provenance_and_hash(tmp_path, monkeypatch):
    """快照必须记来源与内容哈希。

    codex 走 codex exec 自动跑、knevo 只能人工转贴，两者可信度不同；不记 via
    的话，半年后回看无法分辨基准是机器产的还是人贴的。哈希是防篡改锚。
    """
    monkeypatch.setattr(acceptance, "SNAPSHOT_DIR", tmp_path)
    answer = tmp_path / "ans.md"
    answer.write_text("电网设备 +6.65%", encoding="utf-8")
    args = acceptance.argparse.Namespace(
        case_id="A4-dual-red",
        agent="knevo",
        answer_file=str(answer),
        via="manual_paste",
        asked_at="2026-07-27",
        overwrite=False,
    )
    assert acceptance.cmd_freeze(args) == 0
    saved = json.loads(
        (tmp_path / "A4-dual-red.knevo.json").read_text(encoding="utf-8")
    )
    assert saved["via"] == "manual_paste"
    assert saved["asked_at"] == "2026-07-27"
    assert (
        saved["answer_sha256"]
        == hashlib.sha256("电网设备 +6.65%".encode()).hexdigest()
    )


def test_freeze_rejects_empty_answer(tmp_path, monkeypatch):
    """空答案冻结进去会变成"knevo 也答不出"的假证据。"""
    monkeypatch.setattr(acceptance, "SNAPSHOT_DIR", tmp_path)
    answer = tmp_path / "ans.md"
    answer.write_text("   \n", encoding="utf-8")
    args = acceptance.argparse.Namespace(
        case_id="A4-dual-red",
        agent="knevo",
        answer_file=str(answer),
        via="manual_paste",
        asked_at=None,
        overwrite=False,
    )
    assert acceptance.cmd_freeze(args) == 2


def test_freeze_rejects_unknown_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, "SNAPSHOT_DIR", tmp_path)
    answer = tmp_path / "ans.md"
    answer.write_text("x", encoding="utf-8")
    args = acceptance.argparse.Namespace(
        case_id="A4-dual-red",
        agent="itself",
        answer_file=str(answer),
        via="manual_paste",
        asked_at=None,
        overwrite=False,
    )
    assert acceptance.cmd_freeze(args) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
