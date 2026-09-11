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
    assert "副业" in public and "自媒体" in public
    support = public.split("### 希望社区提供的支持")[1].split(
        "### 进入收费阶段前的准备"
    )[0]
    assert "产品打磨" in support and "一人创业交流" in support
    assert "合规" not in support and "法务" not in support
