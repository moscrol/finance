"""细粒度词面路由只认短问句：长材料题必须退回正常 lane，不许被无锚点子串匹配劫走。

坏掉的形态（2026-09-12 实测，生产 2efdff46 与当时 main 均复现）：一道 821 字
（去空白）的纯材料推理题被判成 disclosure_scan，置信度 0.98——「行业」命中在小节
标题（@64）、「公告」命中在材料正文（@72）、「哪些」命中在第 1 题题干（@437），
三个词分散在互不相干的段落，去空白全文无锚点子串匹配照样 AND 成立。

后果不是答得差，而是根本没答：router_skipped → 检索 2ms/0 引用 →
answer_synthesis 的 diagnostic.state="not_requested"（status 却报 "validated"）→
正文被 183 字节扫描存根覆写，answer_status=complete、warnings=[]、llm.used=false。
静默成功，只看 status 的仪表永远绿。

弱点是家族级的：六条细粒度路由（disclosure_scan / trade_advice / kol_review /
comparison_analog / theme_track / quick_fact）都是同一种无锚点词面匹配，自带
examples 全部 8–21 字，却被无长度限制地套在任意长度输入上。修复是在每个词面
判定入口下长度闸（阈值 SSOT：route_table.FINE_GRAINED_ROUTE_MAX_CHARS=160，
去空白后）。

第一版修复只闸了 turn_controller._fine_grained_route_row 一个调用点，decide_turn
端到端仍经 query_understanding.understand_query 产出的 disclosure_scan envelope
（0.98）流进 _deterministic_decision 的兜底分支，照样判成 disclosure_scan。
同一个匹配器的每个调用点都是独立入口——回归锁因此钉三层：裸匹配器、家族入口、
端到端 decide_turn。

仓内冻结题集 24 题全是短问句、一题没命中——这类缺陷靠现有语料扫不出来，只能把
真实事故题钉进测试。事故全记录：
docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok/README.md
"""

from __future__ import annotations

import hashlib
import re

import pytest

from intelligence.services.disclosure_scan_pack import is_disclosure_scan_query
from intelligence.services.query_understanding import understand_query
from intelligence.services.route_table import (
    FINE_GRAINED_ROUTE_MAX_CHARS,
    fine_grained_route_length_ok,
)
from intelligence.services.turn_controller import _fine_grained_route_row, decide_turn


def _stripped_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


# 2026-09-12 T2 事故题逐字节稿（8 题全录）。与冻结批次
# docs/learning/knevo-distill/batches/2026-09-12-three-turns/questions.md 的 T2 段
# 一致（去尾部换行的 SHA-256 见下方断言）；含尾换行的文件稿
# （dda3a7f0d9e3ae3b…）在 recheck 目录。
T2_MATERIAL_QUESTION = """以下是完全虚构的研究案例，不对应现实公司。请只依据给定材料分析，不联网补现实事实；如需假设，请明确列出。

所有金额单位均为亿元。

【行业材料】
客户 R 公告：未来 12 个月计划新增数据中心建设预算 50 亿元，未披露其中供电设备的采购预算，也未披露供应商份额。

【甲公司】
去年总收入 20，数据中心供电相关业务收入 2。
公告获得客户 R 的正式采购订单 1，计划今年、明年各交付 0.5；收入确认仍需满足交付验收条件。
未披露订单毛利率，也未说明该订单是否替代原有业务。
股价近 20 个交易日上涨 32%。

【乙公司】
去年总收入 5，相关业务收入 0.5。
互动平台表示正在向客户 R 送样验证，尚未获得商业订单。
股价近 20 个交易日上涨 3%。

【丙公司】
去年总收入 40，相关业务收入 10。
与客户 R 签署金额 3 的框架协议，但没有最低采购义务，目前尚未实际下单。
股价近 20 个交易日上涨 18%。

三家公司均未提供市值、估值、净利润或订单利润率。

请按以下 8 题逐项回答：

1. 从客户 R 的 50 亿建设预算，到这三家公司的利润增长，中间还需要经过哪些环节？目前哪些环节已有证据，哪些仍是空白？

2. 按“公司受益证据的硬度”给三家公司排序，说明每家的证据最多支持什么结论。

3. 如果改按“潜在业绩弹性”排序，是否仍是同一个顺序？请说明哪些可以比较，哪些还不能确定。

4. 甲公司计划每年交付的订单额，分别占其去年总收入和相关业务收入的多少？这两个比例分别说明什么？能否直接当作新增收入增速或净利润增速？

5. 有人说：“乙涨得最少、体量最小，所以它的预期差最大。”你同意吗？请把这句话中成立的事实、尚未证明的推断分开。

6. 客户建设预算、框架协议、正式订单、收入确认，这四者在本案中应如何处理？哪些金额不能直接相加或相互替代？

7. 如果分别为甲、乙、丙写一句最有力的反方意见，你会写什么？指出什么新增证据能够解除各自的疑点。

8. 如果只能先深入研究一家公司，你选哪家？只允许再查两份材料，你查什么，以及不同查询结果会怎样改变你的判断？
"""


def test_embedded_t2_is_the_incident_question_byte_for_byte() -> None:
    """钉住题面本体：改一个字这里就红，防止「回归测试悄悄测了别的题」。"""
    digest = hashlib.sha256(T2_MATERIAL_QUESTION.rstrip("\n").encode()).hexdigest()
    assert digest == "4fbb588ee75d391221d17df86fc9899559c631ac9634056baa684ef7ddc62e81"
    assert _stripped_len(T2_MATERIAL_QUESTION) == 821
    assert not fine_grained_route_length_ok(T2_MATERIAL_QUESTION)


def test_material_question_is_not_word_matched_into_disclosure_scan() -> None:
    """裸匹配器照样命中（闸不在它身上），家族入口的闸必须把它退回。"""
    assert is_disclosure_scan_query(T2_MATERIAL_QUESTION) is True
    assert _fine_grained_route_row(T2_MATERIAL_QUESTION) is None


def test_material_question_survives_end_to_end_decision() -> None:
    """端到端层：understand_query 的 envelope 路径是匹配器的第二个调用点，
    只闸 _fine_grained_route_row 堵不住（第一版修复就漏在这）。"""
    assert understand_query(T2_MATERIAL_QUESTION).question_type != "disclosure_scan"
    decision = decide_turn(T2_MATERIAL_QUESTION)
    assert decision.question_type != "disclosure_scan"
    # 失败方向：退回正常研究车道，由模型完整作答，而不是模板存根。
    assert decision.lane == "research"


# 六条细粒度路由自带 examples 中能归位的 13 条（全部 ≤21 字，远在闸内）。
# 第 14 条见下方 xfail。
ROUTE_EXAMPLES = [
    ("disclosure_scan", "医药和科技板块有哪些个股有比较利好的公告"),
    ("disclosure_scan", "最近医药有哪些公司出了利好公告"),
    ("disclosure_scan", "电子板块近一周中标或合同公告有哪些"),
    ("trade_advice", "茅台现在该不该买"),
    ("trade_advice", "宁德时代要不要止损"),
    ("kol_review", "这份高盛AI算力研报核心假设站得住吗"),
    ("comparison_analog", "2015互联网泡沫和现在AI行情有什么异同"),
    ("comparison_analog", "液冷历史上有没有类似导入期行业可类比"),
    ("theme_track", "光伏最近一个月有什么新变化"),
    ("theme_track", "动力电池产业链近况跟踪一下"),
    ("quick_fact", "茅台现在股价多少"),
    ("quick_fact", "英伟达市盈率多少倍"),
    ("quick_fact", "300750是哪家公司"),
]


@pytest.mark.parametrize(
    "route_id,query", ROUTE_EXAMPLES, ids=[query for _, query in ROUTE_EXAMPLES]
)
def test_short_route_examples_still_re_home(route_id: str, query: str) -> None:
    """闸不能误伤本职：短意图问句照常各归其位。"""
    assert fine_grained_route_length_ok(query)
    row = _fine_grained_route_row(query)
    assert row is not None and row.route_id == route_id


@pytest.mark.xfail(
    reason=(
        "存量缺陷，与长度闸无关：该 example 与 kol_review 自己的路由 pattern 对不上，"
        "在未改动的生产快照（2efdff46）上同样返回 None。修好 pattern 后此处转 XPASS，"
        "到时移除本标记并把该例并入 ROUTE_EXAMPLES。"
    ),
    strict=True,
)
def test_kol_review_example_preexisting_miss() -> None:
    row = _fine_grained_route_row("但斌说茅台到顶了逻辑有没有漏洞")
    assert row is not None and row.route_id == "kol_review"


@pytest.mark.parametrize(
    "route_id,query", ROUTE_EXAMPLES, ids=[query for _, query in ROUTE_EXAMPLES]
)
def test_padding_past_the_gate_kills_any_fine_grained_route(
    route_id: str, query: str
) -> None:
    """家族级：同样的词面超过阈值后六条路由一律不认——不是只堵 disclosure_scan。"""
    pad = FINE_GRAINED_ROUTE_MAX_CHARS + 1 - _stripped_len(query) - 1
    padded = query + "。" + "垫" * pad
    assert _stripped_len(padded) == FINE_GRAINED_ROUTE_MAX_CHARS + 1
    assert _fine_grained_route_row(padded) is None


def test_gate_threshold_boundary() -> None:
    """阈值语义：去空白后 ≤160 照常词面路由，>160 退回；两个入口同一行为。"""
    base = "医药板块哪些个股有利好公告"  # 三提示词俱备的 13 字最短形态
    at_limit = base + "。" + "垫" * (FINE_GRAINED_ROUTE_MAX_CHARS - _stripped_len(base) - 1)
    over_limit = at_limit + "垫"
    assert _stripped_len(at_limit) == FINE_GRAINED_ROUTE_MAX_CHARS
    assert _stripped_len(over_limit) == FINE_GRAINED_ROUTE_MAX_CHARS + 1
    row = _fine_grained_route_row(at_limit)
    assert row is not None and row.route_id == "disclosure_scan"
    assert _fine_grained_route_row(over_limit) is None
    assert understand_query(at_limit).question_type == "disclosure_scan"
    assert understand_query(over_limit).question_type != "disclosure_scan"
