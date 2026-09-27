"""精确比较 ts_code 列时缺交易所后缀：必须拒绝并给提示，不能静默返回零行。

2026-09-21 两次真实模型冒烟各撞一次（`stock_code eq 688256`、`eq 600673`）：库里
存的是 `688256.SH`，精确比较零行，观察文案是「结构化查询无结果」，模型据此写下
「个股最新价量在本地库缺失」——答案诚实，前提是假的。这一刀把静默空结果换成带
重试提示的拒绝；不替模型猜后缀（6 位码到交易所的映射有 B 股等例外，猜错比查空更坏）。
"""
from __future__ import annotations

from datetime import date

import pytest

from intelligence.services.finance_query import (
    FinanceQuerySpec,
    FinanceQueryValidationError,
    QueryFilter,
    _compile_query,
    validation_retry_hint,
)
from intelligence.services.research_contract import InformationCutoff


def _cutoff() -> InformationCutoff:
    return InformationCutoff(date(2026, 9, 18), "requested")


def _spec(value, *, op="eq", field="stock_code", dataset="stock_daily", dimensions=None, metrics=("close",)):
    return FinanceQuerySpec(
        dataset=dataset,
        dimensions=dimensions or ("trade_date", "stock_code"),
        metrics=metrics,
        filters=(QueryFilter(field=field, op=op, value=value),),
    )


def _compile(spec):
    return _compile_query(spec, information_cutoff=_cutoff(), max_rows=50)


@pytest.mark.parametrize(
    ("value", "op"),
    [("600673", "eq"), ("688256", "ne"), (["600673", "000001.SZ"], "in")],
)
def test_exact_code_filter_without_suffix_is_rejected(value, op) -> None:
    spec = _spec(value, op=op)
    with pytest.raises(FinanceQueryValidationError) as excinfo:
        _compile(spec)
    assert "code filter needs a market suffix" in str(excinfo.value)
    hint = validation_retry_hint(spec, excinfo.value)
    assert ".SH" in hint and ".SZ" in hint
    assert "contains" in hint


def test_suffixed_code_still_compiles() -> None:
    compiled = _compile(_spec("600673.SH"))
    assert "stock_ts_code" in compiled.sql


def test_contains_with_a_bare_code_is_untouched() -> None:
    """`contains` 用 6 位码是能命中的正常写法（LIKE '%600673%'），实测有效，不能一起拦。"""

    compiled = _compile(_spec("600673", op="contains"))
    assert "LIKE" in compiled.sql
    assert any("600673" in str(item) for item in compiled.parameters)


def test_sector_code_without_suffix_is_rejected() -> None:
    spec = _spec(
        "990231",
        field="sector_code",
        dataset="sector_daily",
        dimensions=("trade_date", "sector_code"),
        metrics=("amount",),
    )
    with pytest.raises(FinanceQueryValidationError) as excinfo:
        _compile(spec)
    assert ".FP" in validation_retry_hint(spec, excinfo.value)


def test_non_code_text_filter_with_six_digits_is_untouched() -> None:
    """六位数字只有落在 ts_code 列上才是缺后缀；名称等文本列不受影响。"""

    compiled = _compile(_spec("600673", field="stock_name"))
    assert "stock_name" in compiled.sql
    assert "600673" in [str(item) for item in compiled.parameters]
