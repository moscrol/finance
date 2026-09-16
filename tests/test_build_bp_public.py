"""Narrow regression tests for the public BP generator and staged budget.

⚠ 被测对象 ``scripts/build_bp_public.py`` **尚未提交进仓**（2026-09-06 实测
``git ls-files`` 为空，只在某棵工作树上以未跟踪文件存在）。

本文件原来在**模块级** ``exec_module``，于是在任何干净检出上 pytest
**整个收集阶段直接中断**（是 ERROR 不是 skip，后面所有测试一条都跑不了）。
主树上之所以是绿的，只因为那个未跟踪文件恰好在——那份绿依赖别人没提交的东西，
不能当验收结论。

改成延迟加载 + 缺失即 skip：脚本一旦提交进来，这些用例自动恢复执行。
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_bp_public.py"

pytestmark = pytest.mark.skipif(
    not SCRIPT.exists(),
    reason=f"被测脚本未提交进仓：{SCRIPT.relative_to(ROOT)}（提交后本组用例自动恢复）",
)


if SCRIPT.exists():  # 缺失时不加载：模块级 exec 失败会中断整个收集阶段
    _SPEC = importlib.util.spec_from_file_location("build_bp_public", SCRIPT)
    bp = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(bp)
else:
    bp = None  # 上面的 pytestmark 会把本文件全部 skip，不会走到解引用


@pytest.fixture
def model():
    return json.loads(bp.MODEL.read_text())


def test_staged_development_and_full_test_inference(model):
    values = bp.calculate(model)
    rows = values["cash_rows"]
    assert rows[0]["expense"] == [3200, 3200]
    assert rows[3]["expense"] == [6000, 7000]
    assert rows[5]["expense"] == [9000, 10000]
    assert rows[6]["expense"] == [6260, 7260]
    assert values["cash_trough_low"] == "26,160"
    assert values["cash_trough_high"] == "30,160"
    assert rows[-1]["cumulative"] == [18530, 9530]


def test_contribution_and_thresholds(model):
    values = bp.calculate(model)
    assert values["monthly_contribution"] == 138
    assert values["annualized_arpu"] == 2160
    assert values["sustainable_data_high_lowdev"] == 145
    assert values["sustainable_high"] == 153
    assert values["founder_available_low"] == "14,700"
    assert values["heavy_usage_high"] == 215


def test_later_development_only_changes_later_months(model):
    baseline = bp.calculate(model)
    model["development_later_monthly_high"] = 500
    revised = bp.calculate(model)
    assert revised["cash_rows"][:3] == baseline["cash_rows"][:3]
    assert revised["cash_rows"][3]["expense"][1] == 6500
    assert (
        revised["cash_rows"][-1]["cumulative"][1]
        == baseline["cash_rows"][-1]["cumulative"][1] + 9 * 500
    )
    assert revised["sustainable_high"] == 149


def test_only_public_block_exported(model):
    source = "private before\n" + bp.SRC.read_text() + "\nprivate after"
    public = bp.build(source, model)
    assert "private before" not in public
    assert "private after" not in public
    assert "内部维护约定" not in public
    assert public.count("<!-- PAGE_BREAK -->") == 7


@pytest.mark.parametrize(
    # 下一行的家目录串是脱敏测试的输入夹具：断言生成器会拒绝它、而不是把它写进
    # 对外版。换成派生路径就测不到这条分支。
    "bad", ["【待填：录屏】", "随本材料提交", "{{unknown}}", "/Users/private"]  # path-literal-ok: 脱敏测试夹具
)
def test_missing_artifacts_are_rejected_not_rewritten(model, bad):
    source = bp.SRC.read_text().replace(bp.END, bad + "\n" + bp.END)
    with pytest.raises(ValueError):
        bp.build(source, model)


def test_broken_table_rejected(model):
    source = bp.SRC.read_text().replace(
        "| V4 后续发展 | 12 个月后 |", "| V4 后续发展 |"
    )
    with pytest.raises(ValueError, match="列数"):
        bp.build(source, model)


def test_missing_stage_rejected(model):
    source = bp.SRC.read_text().replace("V4 后续发展", "后续发展")
    with pytest.raises(ValueError, match="阶段表缺失"):
        bp.build(source, model)


def test_duplicate_markers_rejected(model):
    with pytest.raises(ValueError, match="PUBLIC"):
        bp.build(bp.BEGIN + bp.SRC.read_text(), model)


def test_generated_copy_current(model):
    assert bp.OUT.read_text() == bp.build(bp.SRC.read_text(), model)


def test_positioning_and_current_support(model):
    public = bp.build(bp.SRC.read_text(), model)
    assert "认知投降" in public and "认知复利" in public
    # v1.4 经用户授权改为研究主干；“自媒体”不再是必须出现的旧文案。
    assert "副业" in public and "资深投资者" in public
    assert "取证、比较、计算" in public
    assert "学习与判断校准是可选模式，不是使用门槛" in public
    assert public.index("## 1 目标用户") < public.index("### 可选长期积累")
    support = public.split("### 希望社区提供的支持")[1].split(
        "### 进入收费阶段前的准备"
    )[0]
    # v1.6: founder owns first-round recruitment; community supports later validation.
    assert "项目诊断" in support and "一人创业交流" in support
    assert "首轮资深测评由创始人安排" in support
    assert "不是首要请求" in support
    assert "金融合规服务" in support
    assert "资金" not in support and "法务" not in support


def test_demo_is_one_historical_task_not_live_composite(model):
    public = bp.build(bp.SRC.read_text(), model)
    demo = public.split("### 现在能展示什么")[1].split("### Alpha 前")[0]
    assert "2026-09-09" in demo and "M2" in demo
    assert "77 个窗口，71 个缺失、1 个未成熟、5 个有效" in demo
    assert "独立性未建立" in demo
    assert "不冒充产品截图或当前现场执行" in demo
    assert "不拼接其他局部验收" in demo


def test_evidence_and_commercial_boundaries_preserved(model):
    public = bp.build(bp.SRC.read_text(), model)
    for required in (
        "严格按当时所知回放还须有相应内容快照",
        "不是保证模型两次回答一样",
        "当前没有已验证护城河",
        "不证明投资方法有效",
        "3 块不等于 3 个独立个股样本",
        "尚无外部用户和产品收入",
        "尚未生效",
        "本轮扩展产品叙事不自动扩展套餐",
        "真实输出样本",
        "专业评估",
        "商业分发授权",
    ):
        assert required in public
    for obsolete_claim in (
        "通用 AI 助手不记得",
        "通用 Agent 有模型没有框架",
        "大厂不是做不到，是做了会伤",
        "同一天同一对象两次读取结果完全一致",
    ):
        assert obsolete_claim not in public


def test_validation_counts_research_and_optional_calibration_separately(model):
    public = bp.build(bp.SRC.read_text(), model)
    plan = public.split("## 5 验证计划与调整机制")[1].split("## 6 项目预算")[0]
    assert "仅在自愿校准子组计算" in plan
    assert "失败、重试和人工救场不得从分母删除" in plan
    assert "自动存档不算主动保存" in plan
    assert "创始人工时" in plan
    assert "至少半数登记过判断，才考虑扩大" not in plan


def test_public_copy_avoids_internal_jargon(model):
    """对外版不带内部任务编号与运维术语；评审读不懂的词要么释义要么不出现（母本 v1.5）。"""
    public = bp.build(bp.SRC.read_text(), model)
    for jargon in ("M1–M5", "M6/UI", "质量门", "关系包", "六单季实数", "配对效果", "倒签"):
        assert jargon not in public
    assert "内部编号 M2" in public


def test_founder_recruitment_and_later_community_support(model):
    public = bp.build(bp.SRC.read_text(), model)
    acquisition = public.split("### 先自主邀请测评")[1].split("### 单用户收入")[0]
    assert "首轮由创始人邀请资深投资者" in acquisition
    assert "资深用户认可不等于" in acquisition
    assert "再与社区探索" in acquisition
    for obsolete in ("从社区和公开内容招募首批用户", "100 人候补名单", "对接 3–10 名首批体验者"):
        assert obsolete not in public
    form = (ROOT / "docs/bp/2026-09-opc-application-form-answers.md").read_text()
    assert "Foresight v1.7" in form
    assert "首轮资深用户测评我自己安排" in form
    assert "通过 OPC 社区与公开研究内容招募 3–10 人" not in form


def test_collaborative_design_and_ninety_day_plan_are_not_results(model):
    public = bp.build(bp.SRC.read_text(), model)
    assert "提取前置是设计中的可选模式" in public
    for goal in ("你在进步", "它在改进协作", "双方共同积累"):
        assert goal in public
    assert "不是完整跨日闭环已验收" in public
    assert "模型理解问题、决定查什么" in public
    assert "数据库与计算工具负责联立和核算" in public
    for stage in ("第 1–30 天", "第 31–60 天", "第 61–90 天"):
        assert stage in public
    assert "不把日期当上线保证" in public
    assert "算力和模型 API 额度是补充" in public
    assert "破卷" not in public and "knevo" not in public.lower()


def test_domain_methods_and_flow_vision_are_not_validated_results(model):
    public = bp.build(bp.SRC.read_text(), model)
    for required in (
        "观测面就是研究问题的角度",
        "发现规律与验证规律的数据须分开",
        "历史高命中率不能保证泛化",
        "当前没有已验证护城河",
        "长期愿景：人机交互的心流平台",
        "不是心理学心流效果已获证明",
        "当前仍聚焦 A 股研究",
    ):
        assert required in public


def test_enterprise_discovery_precedes_conditional_pilot(model):
    public = bp.build(bp.SRC.read_text(), model)
    enterprise = public.split("### 机构探索：")[1].split("### 进入收费阶段")[0]
    for required in (
        "同时可访谈", "当前无机构订单或收入证明", "不同时开发两套完整平台",
        "验收标准", "数据授权", "权限隔离", "专业评估", "人工审核",
        "首次实施费＋持续订阅", "不计原预算", "不得默认跨客户复用",
    ):
        assert required in enterprise
    assert "个人订阅验证后再评估，单独报价" not in public


def test_red_line_wording(model):
    """对外红线只写「不荐股、不提供个股买卖建议」；不用法规原文动词「预测」认领能力（母本 v1.2 说明）。"""
    public = bp.build(bp.SRC.read_text(), model)
    assert "不荐股" in public and "不提供个股买卖建议" in public
    assert "预测" not in public and "涨跌" not in public
