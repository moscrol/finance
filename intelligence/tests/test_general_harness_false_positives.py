"""通用 harness 不该拦住合规内容。

分工：领域 harness（数字/公司/日期是否有出处）是放大器，必须严；通用 harness
（标题措辞、句子编号、解析格式）只该保证「不夹带未绑定断言」，不该管文风。

实测 run_20260731_100030_961776 —— 第一次跑出 validated_synthesis 的那轮 —— 通用
harness 报了两类误报：

1. 标题「继续下跌情景：触发条件、支持证据与观察窗口」判 error「包含未绑定的事实性
   内容」。这个标题是本轮契约要求覆盖的输出描述**逐字照抄**，被字符级正则因为含
   「跌」判掉：系统要求模型覆盖它，模型照做，门禁再把它毙了。
2. 「其中三环集团」判 error「增加证据外公司」。证据原文就是「三环集团拟最高10亿元
   回购股份」，只是公司名正则向左把「其中」一起吞了。

同一轮里 7 条「增加证据外数字」是**真的**（模型编了 4253、2000、1.8 等），那是领域
harness 在正确工作，不在本次放宽范围内。
"""
from __future__ import annotations

import re

from intelligence.services.answer_model import (
    _NUMBER_RE,
    _company_is_known,
    _heading_requires_fact_binding,
    _normalize_number_token,
)

EVIDENCE = (
    "近20家A股上市公司盘后披露回购或增持计划公告 三环集团拟最高10亿元回购股份；"
    "2026-07-30：指数 -0.62%；成交 23425.75 亿；上涨 1768 家；涨停/跌停 52/74。"
)
CORPUS = re.sub(r"\s+", "", EVIDENCE)
NUMBERS = frozenset(
    _normalize_number_token(token) for token in _NUMBER_RE.findall(CORPUS)
)


def _fact_like(heading: str) -> bool:
    return _heading_requires_fact_binding(
        heading,
        allowed_text=CORPUS,
        allowed_numbers=NUMBERS,
    )


# --- 标题：只拦夹带，不拦措辞 ---------------------------------------------


def test_a_heading_summarising_bound_evidence_is_not_smuggling() -> None:
    """「放量下跌」正是已绑定 claim 的忠实概括，不是新断言。"""
    assert _fact_like("核心矛盾：放量下跌与外部利好的博弈") is False


def test_a_number_that_is_in_evidence_may_appear_in_a_heading() -> None:
    assert _fact_like("跌停 74 家") is False


def test_an_unbound_assertion_in_a_heading_is_still_rejected() -> None:
    """这条是这道门禁存在的理由，不能因为放宽而失效。"""
    assert _fact_like("利润已翻倍") is True


def test_a_number_absent_from_evidence_is_still_rejected() -> None:
    assert _fact_like("涨停 111 家创年内新高") is True


def test_narrative_headings_stay_advisory() -> None:
    assert _fact_like("为什么会跑偏") is False


def test_without_a_corpus_the_previous_behaviour_is_kept() -> None:
    """没有语料的调用方（旧签名）行为不变。"""
    assert _heading_requires_fact_binding("核心矛盾：放量下跌与外部利好的博弈") is True


# --- 公司名：容忍被吞进来的虚词，不容忍新公司 -----------------------------


def test_a_swallowed_prefix_does_not_make_a_known_company_new() -> None:
    assert _company_is_known("其中三环集团", CORPUS) is True


def test_the_plain_company_name_still_matches() -> None:
    assert _company_is_known("三环集团", CORPUS) is True


def test_a_company_absent_from_evidence_is_still_reported() -> None:
    assert _company_is_known("宁德时代集团", CORPUS) is False


def test_stripping_a_prefix_may_not_manufacture_a_match() -> None:
    """剥完必须仍是个像样的名字，不能靠剥字凑出证据里的子串。"""
    assert _company_is_known("和某某银行", CORPUS) is False
