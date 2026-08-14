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
from intelligence.eval.acceptance_observations import (
    REFERENCE_ELIGIBILITY_PATH,
    canonical_artifact_hash,
)
from intelligence.eval.acceptance_verdict import VERDICT_OVERLAY_PATH

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


def test_knevo_plan_accounts_for_every_case():
    """每道题要么排进 knevo 提问队列，要么写明为什么不问。

    手工维护这个划分已经漏过两次（A4 漏在两边之外一次，C6/B5 因错误理由被排除
    一次）。参照答案的意义在于覆盖可核对，漏一道就等于悄悄缩小了分母。
    """
    doc = acceptance.load_cases()
    plan = doc["reference_plan"]["knevo"]
    queue = [e["case_id"] for e in plan["queue"]]
    excluded = [cid for g in plan["excluded"] for cid in g["case_ids"]]
    ids = {c["id"] for c in doc["cases"]}

    assert len(queue) == len(set(queue)), "队列里有重复题目，会重复花积分"
    assert not set(queue) & set(excluded), "同一道题既排队又排除"
    assert ids - set(queue) - set(excluded) == set(), "有题目两边都没提到"
    assert (set(queue) | set(excluded)) - ids == set(), "计划里出现了不存在的 case_id"


def test_knevo_prompts_avoid_local_only_vocabulary():
    """自造口径不能直接丢给外部参照考生。

    『双红』是用户自定义口径（pct_chg>0 且 diff_ratio>10 且 amount>500），
    knevo 的两份对照答卷里出现 0 次。带着这个词提问，拿回来的是它临时自造的
    定义 —— 那是词义偏差，会被误读成能力差距。提问必须展开成数值条件。
    """
    plan = acceptance.load_cases()["reference_plan"]["knevo"]
    for entry in plan["queue"]:
        text = entry["prompt"] + "".join(entry.get("followups", []))
        assert "双红" not in text, f"{entry['case_id']} 的提问里残留了本地口径"


def test_must_mention_misses_on_reference_are_documented():
    """参照答案没命中 must_mention 时，必须先判定这是词汇差还是能力差。

    must_mention 用在我们自己的答案上是合理的产品要求；拿去卡外部参照就变成
    『考它是否共享我们的词汇表』—— 和把『双红』丢给它是同一个失败模式，只不过
    这次藏在我们自己的判分字段里。已实测两例：A2 全文 0 次『证伪』但三情景都带了
    数值触发（实质是过的）；A1 缺『反弹阶段』是复盘会的阶段口径。

    所以规则是：新加的 must_mention 词若让某份参照快照落空，要么在
    our_scoring_caveats 里写明理由，要么把词换成领域事实词。静默落空不允许。
    """
    doc = acceptance.load_cases()
    plan = doc["reference_plan"]["knevo"]
    documented = " ".join(plan["our_scoring_caveats"].keys())
    for case in doc["cases"]:
        terms = case.get("must_mention") or []
        if not terms:
            continue
        snap = acceptance.SNAPSHOT_DIR / f"{case['id']}.knevo.json"
        if not snap.exists():
            continue
        answer = json.loads(snap.read_text(encoding="utf-8"))["answer"]
        missed = [t for t in terms if t not in answer]
        if missed:
            assert case["id"] in documented, (
                f"{case['id']} 的 must_mention {missed} 在 knevo 快照里落空，"
                "但 our_scoring_caveats 没写这是词汇差还是能力差"
            )


def test_snapshot_caveats_reference_real_cases():
    """快照使用限制必须挂在真实题目上，否则半年后没人知道它在限制什么。"""
    doc = acceptance.load_cases()
    plan = doc["reference_plan"]["knevo"]
    ids = {c["id"] for c in doc["cases"]}
    for key in plan["snapshot_caveats"]:
        if key.startswith("_"):
            continue
        # 一份快照被两道题共用时，键写成 "A / B"
        named = [p.strip() for p in key.split("/")]
        assert set(named) <= ids, f"snapshot_caveats 键 {key!r} 指向不存在的 case_id"


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


# 2026-08-11 修：原先这里 `monkeypatch.setattr(acceptance, "latest_run", ...)`，
# 但 cmd_board 早已不调 latest_run，改成 select_latest_case_runs(RUNS_DIR, ...)。
# **mock 点随实现重构失效后成了空操作**：board 于是去扫真实的 runs 目录（现有 20 份），
# 断言随之漂移——失败信息看起来像「板子渲染坏了」，其实是测试没钉住输入。
# 现在走公开接口显式指定 run，输入固定、不随目录增长而变。
def test_board_keeps_operational_truth_and_experience_axes_separate(capsys):
    run_path = acceptance.REPO / "intelligence/eval/runs/20260727T032229Z.json"

    assert (
        acceptance.cmd_board(acceptance.argparse.Namespace(run=str(run_path))) == 0
    )
    output = capsys.readouterr().out

    # 断言「三轴各自独立成列」，而不是钉死整行表头。
    # 这条用例的名字说的就是「运行/真值/体验三轴分离」——那才是要守的不变量。
    # 原先钉死 `| 题 | 组 | 运行 | 真值 | 体验 |`，板子后来加了 来源/送达/信息量/
    # 可信度/耗时/绑定证据/说明 七列，表头一变就红，而三轴分离其实完好无损：
    # **过度具体的断言会在无关变更上报警，把真正的回归淹掉**。
    header = next(line for line in output.splitlines() if line.startswith("| 题 |"))
    columns = [cell.strip() for cell in header.strip("|").split("|")]
    for axis in ("运行", "真值", "体验"):
        assert axis in columns, f"{axis} 轴应当是独立一列，实际列为 {columns}"
    assert "**运行口径**" in output
    assert "**真值口径**" in output
    assert "不可判" in output
    assert "不是 28 题产品通过率" in output
    assert "有答案待判" not in output


# 同上：mock 点失效导致这里没传 run，撞上「sidecar 只绑定单个 run」的守卫，
# cmd_board 返回 2 而断言要 0。sidecar 本来就按 run 的 sha256 绑定，
# 显式传 run 才是这条用例真正要测的路径。
def test_board_accepts_only_explicit_hash_bound_sidecars(tmp_path, capsys):
    run_path = acceptance.REPO / "intelligence/eval/runs/20260727T032229Z.json"
    source = {
        "run_path": "intelligence/eval/runs/20260727T032229Z.json",
        "run_sha256": hashlib.sha256(run_path.read_bytes()).hexdigest(),
        "cases_sha256": hashlib.sha256(acceptance.CASES_PATH.read_bytes()).hexdigest(),
        "overlay_sha256": hashlib.sha256(VERDICT_OVERLAY_PATH.read_bytes()).hexdigest(),
    }
    truth = {
        "format_version": 1,
        "artifact_kind": "acceptance_truth_observations",
        "created_at": "2026-07-29T12:00:00Z",
        "source": source,
        "evaluator": {
            "id": "independent-semantic-reviewer",
                "kind": "semantic_model",
                "model": "gpt-5.6-sol",
                "independent": True,
        },
        "rubric_sha256": "a" * 64,
        "case_observations": {
            "C9-citation-integrity": {
                "truth_observations": {
                    "pass_rule": {
                        "state": "fail",
                        "reason": "causal question unanswered",
                        "evidence_refs": ["turn:0"],
                    }
                }
            }
        },
    }
    truth["artifact_sha256"] = canonical_artifact_hash(truth)
    truth_path = tmp_path / "truth.json"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")

    experience = {
        "format_version": 1,
        "artifact_kind": "acceptance_experience_labels",
        "created_at": "2026-07-29T12:00:00Z",
        "source": source,
        "evaluator": {
            "id": "blind-reviewer",
            "kind": "blind_reviewer",
            "independent": True,
        },
        "rubric_sha256": "b" * 64,
        "comparison": {
            "reference_agent": "knevo",
            "reference_eligibility_sha256": hashlib.sha256(
                REFERENCE_ELIGIBILITY_PATH.read_bytes()
            ).hexdigest(),
            "blind_manifest_sha256": "pending",
        },
        "case_observations": {
            "C9-citation-integrity": {
                "experience_verdict": {
                    "eligible": True,
                    "label": "reference",
                    "reason": "more direct",
                    "blinded_pair_id": "pair-c9",
                    "dimensions": ["directness"],
                }
            }
        },
    }
    snapshot = (
        acceptance.REPO
        / "intelligence/eval/cases/reference_snapshots/C9-citation-integrity.knevo.json"
    )
    blind = {
        "format_version": 1,
        "created_at": "2026-07-29T11:55:00Z",
        "pairs": {
            "pair-c9": {
                "case_id": "C9-citation-integrity",
                "left": "workbench",
                "right": "reference",
                "workbench_run_sha256": source["run_sha256"],
                "reference_snapshot_sha256": hashlib.sha256(
                    snapshot.read_bytes()
                ).hexdigest(),
            }
        },
    }
    blind["artifact_sha256"] = canonical_artifact_hash(blind)
    blind_path = tmp_path / "blind.json"
    blind_path.write_text(json.dumps(blind), encoding="utf-8")
    experience["comparison"]["blind_manifest_sha256"] = blind["artifact_sha256"]
    experience["artifact_sha256"] = canonical_artifact_hash(experience)
    experience_path = tmp_path / "experience.json"
    experience_path.write_text(json.dumps(experience), encoding="utf-8")

    args = acceptance.argparse.Namespace(
        run=str(run_path),
        truth_observations=str(truth_path),
        experience_labels=str(experience_path),
        blind_manifest=str(blind_path),
    )
    assert acceptance.cmd_board(args) == 0
    output = capsys.readouterr().out

    c9 = next(line for line in output.splitlines() if line.startswith("| C9-"))
    assert "❌ 失败" in c9
    assert "已盲标(reference)" in c9


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
