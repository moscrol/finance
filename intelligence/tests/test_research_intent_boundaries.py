"""研究意图边界（R-20260916-05 真实会话实锤的三类越界）。

三个缺陷都不是「模型答得不好」，而是**运行时把用户的话理解错了**，所以都用
确定性单测钉死，不靠改提示词宣布修好：

1. 用户写了「不要把本次研究登记为长期跟踪」，答案照抄了这句承诺，运行时仍往
   用户目录写了 4 条 checkpoint —— 承诺在文本层，写入在运行时层，两层没连上。
2. 其中一条 due=2027-07-13：观察项里写的是「约 2026-10 月底披露」，被时长解析
   读成「10 个月后」。日历月是时点，不是时长。
3. 同一道题、只有末行排版指令不同，一臂路由成 stock_deep_dive（subject 中际旭创），
   另一臂成 kol_review（subject null）：长研究问题被输入解析当成「粘贴材料」，
   只剩末行格式要求当问题交给路由。

夹具用 R-20260916-05 的冻结题面原文，不重写成更好读的版本 —— 重写过的样本
证明不了线上那条路径。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.ranking_contract import (
    _due_from_watch,
    ingest_flip_conditions,
)
from intelligence.services.track_contract import (
    calendar_month_due,
    ingest_next_watch,
    parse_track_intent,
    persistence_opt_out,
)
from intelligence.services.user_task import split_user_message
from intelligence.tests.test_ranking_contract import ANSWER as RANKING_ANSWER

# R-20260916-05 冻结题面（两臂只差最后一行的组织方式指令）。
_R05_BODY = (
    "请研究中际旭创（300308）：截至2026年9月16日，最近两期已披露的定期报告中，"
    "收入和利润增长是否兑现为经营现金流？应收账款、存货和回款证据支持还是削弱经营质量"
    "改善的判断？请使用实际可获取的公告、财务数据和知识库资料，先说明数据截止期与缺口，"
    "口径不一致不能直接比较，不编造材料没有给出的数据或正常阈值，不提供买卖建议。"
    "输出当前判断、支持证据与关键反证、最值得优先补查的一条证据，以及什么观察会改变判断；"
    "关键数字给出来源和报告期，事实与解释分开。不要把本次研究登记为长期跟踪或投资观点。"
)
_R05_SUMMARY = f"{_R05_BODY}\n请按事实条目逐条整理，再形成判断和下一步。"
_R05_MECHANISM = (
    f"{_R05_BODY}\n请按关键变量之间的传导关系组织，明确主解释、竞争解释、"
    "用于区分的观察变量和适用边界，再形成判断和下一步。"
)

_TRACK_ANSWER = (
    "无上期基线，本期建立基线。\n"
    "毛利率判断：信息不足 [D7]。复核期限：2026-10-16。\n"
    "## 下期关注清单\n"
    "- 若 26Q3 季报应收账款周转天数继续上行，则削弱经营质量改善判断（约2026-10月底披露）\n"
)


# —— 1. 否定意图必须在写入前生效 ————————————————————————————————
def test_opt_out_is_recognised_in_the_frozen_question() -> None:
    assert persistence_opt_out(_R05_SUMMARY)
    assert persistence_opt_out(_R05_MECHANISM)
    assert persistence_opt_out("本次不登记长期跟踪")
    assert persistence_opt_out("别把它写进跟踪清单")
    assert persistence_opt_out("这次不做长期跟踪")


def test_opt_out_does_not_fire_on_ordinary_negations() -> None:
    # 「不」字满天飞的正常研究问题不能被读成退出登记。
    assert not persistence_opt_out("排产不及预期，跟踪一下液冷板块")
    assert not persistence_opt_out("这家公司不赚钱，帮我持续跟踪")
    assert not persistence_opt_out("光伏最近有什么新变化")
    assert not persistence_opt_out("")


def test_negated_track_word_alone_does_not_route_track_contract() -> None:
    # 一句「不登记长期跟踪」反而打开跟踪契约，是纯词面匹配的经典反噬。
    assert not parse_track_intent(_R05_SUMMARY)
    assert not parse_track_intent(_R05_MECHANISM)
    # 真有跟踪诉求时照常路由：表达纪律和持久化是两件事。
    assert parse_track_intent("跟踪一下液冷，但不要登记为长期跟踪")


def test_opt_out_blocks_next_watch_checkpoint_write(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.jsonl"
    written = ingest_next_watch(
        path,
        _TRACK_ANSWER,
        query="跟踪一下中际旭创的经营质量，但不要把本次研究登记为长期跟踪",
        as_of="2026-09-16",
        session_id="run-test",
    )
    assert written == []
    assert not path.exists(), "用户说了不登记就一个字节都不该落盘"


def test_opt_out_blocks_flip_condition_checkpoint_write(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.jsonl"
    written = ingest_flip_conditions(
        path,
        RANKING_ANSWER,
        query="英维克、申菱环境、高澜股份谁更值得优先研究？排个序；不要登记为长期跟踪",
        as_of="2026-09-16",
        session_id="run-test",
    )
    assert written == []
    assert not path.exists()


def test_without_opt_out_the_write_path_still_works(tmp_path: Path) -> None:
    # 反向对照：没有退出声明时行为不变，避免「修好了因为什么都不写了」。
    path = tmp_path / "checkpoints.jsonl"
    written = ingest_next_watch(
        path,
        _TRACK_ANSWER,
        query="中际旭创经营质量跟踪一下",
        as_of="2026-09-16",
        session_id="run-test",
    )
    assert len(written) == 1
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows and rows[0]["source"] == "track_next_watch"


# —— 2. 日历月是时点，不是时长 ————————————————————————————————
def test_calendar_month_is_a_deadline_not_a_duration() -> None:
    # 实际写进用户目录的错误值是 2027-07-13（= 2026-09-16 + 10 个月）。
    assert _due_from_watch("26Q3 季报应收/存货是否收敛，约2026-10月底披露", "2026-09-16") == "2026-10-31"
    assert calendar_month_due("2026年10月中报补充披露") == "2026-10-31"
    assert calendar_month_due("2026-02 的经营数据") == "2026-02-28"
    assert calendar_month_due("下个月看一眼") is None


def test_real_durations_and_explicit_dates_are_unchanged() -> None:
    assert _due_from_watch("铜价周度均价，30 天内", "2026-09-16") == "2026-10-16"
    assert _due_from_watch("3 个月内观察订单", "2026-09-16") == "2026-12-15"
    assert _due_from_watch("公告，2026-10-31 前", "2026-09-16") == "2026-10-31"
    assert _due_from_watch("无时间线索", "2026-09-16") == "2026-10-16"


def test_next_watch_item_due_uses_the_calendar_month(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.jsonl"
    written = ingest_next_watch(
        path,
        _TRACK_ANSWER,
        query="中际旭创经营质量跟踪一下",
        as_of="2026-09-16",
        session_id="run-test",
    )
    assert [row["due"] for row in written] == ["2026-10-31"]


# —— 3. 长研究问题不是「粘贴材料」 ————————————————————————————
def test_long_research_question_is_not_demoted_to_material() -> None:
    for text in (_R05_SUMMARY, _R05_MECHANISM):
        parts = split_user_message(text)
        assert parts.materials == (), "研究问题被当成材料后，路由只能看见末行的排版要求"
        assert "中际旭创" in parts.question
        assert "300308" in parts.question


def test_both_arms_produce_the_same_question_body() -> None:
    # 两臂只该差组织方式那一句；题面主体必须逐字相同，否则比的就不是同一道题。
    summary_q = split_user_message(_R05_SUMMARY).question
    mechanism_q = split_user_message(_R05_MECHANISM).question
    assert summary_q.startswith(_R05_BODY)
    assert mechanism_q.startswith(_R05_BODY)


def test_pasted_document_with_a_trailing_question_still_splits() -> None:
    # 反向对照：真材料（带材料标记）+ 末行短问句，仍按老规则切分。
    doc = (
        "【卖方摘要｜2026-08-28】固态电池：硫化物路线进入中试放量期\n"
        "一、核心观点：公司 A 硫化物电解质中试线 2026 年 8 月投产，规划产能 200 吨/年。\n"
        "二、关键数据：上半年新签订单 12 亿元，同比增长 40%。\n"
        "这篇研报的核心逻辑站得住吗？"
    )
    parts = split_user_message(doc)
    assert len(parts.materials) == 1
    assert parts.materials[0].kind == "pasted_text"
    assert parts.question == "这篇研报的核心逻辑站得住吗？"


# —— QC 补漏（2026-09-17）：三处修补各自的同族输入 ————————————————————
# 第一版只用 R05 原句做夹具；下面这些是「同一条规则、换一种常见写法」时会反向触发的样本。
def test_double_negation_and_questions_are_not_opt_outs() -> None:
    # 「别忘了 / 不要忘记 / 请勿遗漏」是双重否定 = 要登记；「要不要」是提问不是拒绝；
    # 「不要只…」是补充要求。误判成退出会把用户明确要的跟踪静默关掉——比多写一条更糟。
    for text in (
        "别忘了登记跟踪",
        "不要忘记把这个登记为长期跟踪",
        "请勿遗漏登记为跟踪项",
        "要不要登记为长期跟踪？",
        "不确定要不要做长期跟踪",
        "需不需要纳入长期跟踪",
        "不要只登记跟踪，还要给到期日",
    ):
        assert not persistence_opt_out(text), text
        assert parse_track_intent(text), text
    # 真拒绝不受影响，含「还是不要」这种前面带别的字的写法。
    assert persistence_opt_out("还是不要登记为长期跟踪了")
    assert persistence_opt_out("不要忘了，本次不登记长期跟踪")


def test_dont_forget_to_register_still_writes(tmp_path: Path) -> None:
    path = tmp_path / "checkpoints.jsonl"
    written = ingest_next_watch(
        path,
        _TRACK_ANSWER,
        query="别忘了登记中际旭创为长期跟踪",
        as_of="2026-09-16",
        session_id="run-test",
    )
    assert len(written) == 1
    assert path.exists()


def test_calendar_month_rejects_full_dates_and_non_month_numbers() -> None:
    # 「2026年10月15日」是日期不是月；「2026年10亿元」「2026年3季度」里的数字根本不是月份。
    for text in (
        "2026年10月15日披露",
        "2026-10-15 前",
        "2026/10/15",
        "2026年10亿元订单",
        "2026年3季度末",
    ):
        assert calendar_month_due(text) is None, text
    assert calendar_month_due("2026/10 月中") == "2026-10-31"
    assert calendar_month_due("2026年10月底") == "2026-10-31"


def test_next_watch_item_due_parses_chinese_full_date() -> None:
    # 与 ranking_contract._due_from_watch 同口径：中文全日期取当日，不取月末，也不落默认值。
    from intelligence.services.track_contract import _item_due

    assert _item_due("三季报 2026年10月15日披露", "2026-09-16") == "2026-10-15"
    assert _due_from_watch("三季报 2026年10月15日披露", "2026-09-16") == "2026-10-15"
    # 不是月份的数字：默认 +30 天，而不是被读成 10 月底。
    assert _item_due("若 2026年10亿元订单落地", "2026-09-16") == "2026-10-16"
    assert _due_from_watch("若 2026年10亿元订单落地", "2026-09-16") == "2026-10-16"


def test_research_question_with_a_non_question_tail_is_not_demoted() -> None:
    # 末行不是问句时走的是另一条分支（「整块像文档且没有问句 → 全是材料」），
    # 它同样只认「公告 / 研报」这类词，题面会整段变材料、问题直接变空串。
    for tail in ("输出格式：表格。", "字数 800 以内。"):
        parts = split_user_message(f"{_R05_BODY}\n{tail}")
        assert parts.materials == (), tail
        assert "中际旭创" in parts.question, tail


def test_blank_line_before_the_tail_does_not_demote_either() -> None:
    # 空行分段走第三条分支（首/末短段是问题、其余是材料），同一个前提同样缺失。
    for tail in ("请按事实条目逐条整理，再形成判断和下一步。", "输出格式：表格。"):
        parts = split_user_message(f"{_R05_BODY}\n\n{tail}")
        assert parts.materials == (), tail
        assert "中际旭创" in parts.question, tail
        assert tail in parts.question, tail


def test_blank_line_separated_document_plus_question_still_splits() -> None:
    # 反向对照：结构化材料 + 空行 + 短问句，仍按老规则切分。
    doc = (
        "【卖方摘要｜2026-08-28】固态电池：硫化物路线进入中试放量期\n"
        "一、核心观点：公司 A 硫化物电解质中试线 2026 年 8 月投产，规划产能 200 吨/年。\n"
        "二、关键数据：上半年新签订单 12 亿元，同比增长 40%。"
    )
    parts = split_user_message(f"{doc}\n\n这篇研报的核心逻辑站得住吗？")
    assert len(parts.materials) == 1
    assert parts.question == "这篇研报的核心逻辑站得住吗？"


def test_unstructured_pasted_paragraph_without_question_is_still_material() -> None:
    # 反向对照：无结构标记、无问句标记的粘贴段落 + 非问句末行 → 整块材料、问题为空（老规则不变）。
    doc = (
        "某券商研报摘要\n"
        "公司三季度营收同比增长 30%，新签订单 12 亿元，产能利用率提升至 85%。\n"
        "风险提示：下游需求不及预期。"
    )
    parts = split_user_message(doc)
    assert len(parts.materials) == 1
    assert parts.question == ""


# —— 第三道闸（orchestrator 早退）要单独证明：内层两道换成会漏写的假函数，外层仍须挡住 ——
def test_orchestrator_gate_blocks_even_if_inner_ingests_leak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from intelligence.runtime import conversation_orchestrator as co
    from intelligence.services import ranking_contract, track_contract

    path = tmp_path / "checkpoints.jsonl"
    calls: list[str] = []

    def leaky(name: str):
        def _leak(checkpoints_path, *_args, **_kwargs):
            calls.append(name)
            Path(checkpoints_path).write_text("leaked\n", encoding="utf-8")
            return [{"source": name}]

        return _leak

    # 方法体在 pytest 下默认整段跳过（PYTEST_CURRENT_TEST），这里刻意放行，才测得到闸门本身。
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(co.userspace, "user_space", lambda _uid: SimpleNamespace(checkpoints_path=path))
    monkeypatch.setattr(track_contract, "ingest_next_watch", leaky("next_watch"))
    monkeypatch.setattr(ranking_contract, "ingest_flip_conditions", leaky("flip"))
    fake_self = SimpleNamespace(run_store=SimpleNamespace(user_id="qc-real-user"))

    co.TurnOrchestrator._ingest_track_next_watch(
        fake_self,
        query=_R05_SUMMARY,
        answer=_TRACK_ANSWER,
        question_type="theme_track",
        as_of="2026-09-16",
        theme=None,
        session_id="run-qc",
    )
    assert calls == [], "用户说了不登记，orchestrator 层就不该把答案交给任何写入器"
    assert not path.exists()

    # 反向对照：没有退出声明时两个写入器都被调用——闸门不是把整条链关掉了。
    co.TurnOrchestrator._ingest_track_next_watch(
        fake_self,
        query="中际旭创经营质量跟踪一下",
        answer=_TRACK_ANSWER,
        question_type="theme_track",
        as_of="2026-09-16",
        theme=None,
        session_id="run-qc",
    )
    assert calls == ["next_watch", "flip"]
    assert path.exists()
