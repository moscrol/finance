"""Narrow regression tests for the public BP generator and staged budget."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_bp_public", ROOT / "scripts/build_bp_public.py"
)
bp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bp)


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
