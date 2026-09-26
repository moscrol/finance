#!/usr/bin/env python3
"""从明确标记的母本生成对外版；不把缺失附件自动改成已提交。"""

from __future__ import annotations
import argparse
import json
import math
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "docs/bp/2026-09-finance-agent-bp.md"
OUT = REPO / "docs/bp/2026-09-finance-agent-bp-对外版.md"
MODEL = REPO / "docs/bp/2026-09-foresight-financial-assumptions.json"
BEGIN, END = "<!-- PUBLIC_BP_BEGIN -->", "<!-- PUBLIC_BP_END -->"


def calculate(m: dict) -> dict:
    """月度等价现金模型。开发费用分阶段，低/高区间不充当已确认报价。"""
    contrib = (
        m["monthly_revenue_per_payer"]
        - m["paid_inference_per_month"]
        - m["free_inference_allocation_per_payer"]
    )
    if contrib <= 0:
        raise ValueError("单用户贡献须为正；否则本可持续线公式不适用")
    fixed = m["fixed_monthly_cost"] + m["compliance_monthly_budget"]
    dev_lo, dev_hi = (
        m["development_later_monthly_low"],
        m["development_later_monthly_high"],
    )
    target = m["founder_pretax_monthly_target"]

    def threshold(data, dev, contribution=contrib):
        if contribution <= 0:
            raise ValueError("敏感性情景的单用户贡献须为正")
        return math.ceil((fixed + data + dev + target) / contribution)

    rows = []
    cumul = [0, 0]
    trough = [0, 0]
    for r in m["months"]:
        revenue = r["payers"] * m["monthly_revenue_per_payer"]
        inference = (
            r["test_users"] * m["paid_inference_per_month"]
            if r["stage"] in ("V1", "V2")
            else r["payers"]
            * (m["paid_inference_per_month"] + m["free_inference_allocation_per_payer"])
        )
        base = m["fixed_monthly_cost"] + inference
        devs = (
            [m["development_early_monthly_budget"]] * 2
            if r["stage"] == "V1"
            else [dev_lo, dev_hi]
        )
        if r["stage"] != "V1":
            base += m["compliance_monthly_budget"] + m["data_monthly_high"]
        expense = [base + d for d in devs]
        net = [revenue - e for e in expense]
        cumul = [c + n for c, n in zip(cumul, net)]
        trough = [min(t, c) for t, c in zip(trough, cumul)]
        rows.append(
            dict(
                **r, revenue=revenue, expense=expense, net=net, cumulative=cumul.copy()
            )
        )

    def pair(values):
        return (
            f"{values[0]:,}"
            if values[0] == values[1]
            else " / ".join(f"{v:,}" for v in values)
        )

    table = "| 月份 | 付费人数 | 收入（元） | 支出（元） | 累计净额（元） |\n|---|---|---|---|---|\n"
    table += "\n".join(
        f"| {r['month']} · {r['stage']} | {r['payers']} | {r['revenue']:,} | {pair(r['expense'])} | {pair(r['cumulative'])} |"
        for r in rows
    )
    cash_lo, cash_hi = [-v for v in trough]
    reserve = [
        math.ceil(v * (1 + m["buffer_percent"] / 100) / 1000) * 1000
        for v in [cash_lo, cash_hi]
    ]
    out = dict(m)
    out.update(
        monthly_contribution=contrib,
        annualized_arpu=12 * m["monthly_revenue_per_payer"],
        alpha_budget_wan=f"{sum(r['expense'][1] for r in rows[:3]) / 10000:.2f}",
        cash_table=table,
        sustainable_low=threshold(m["data_monthly_low"], dev_lo),
        sustainable_data_low_highdev=threshold(m["data_monthly_low"], dev_hi),
        sustainable_data_high_lowdev=threshold(m["data_monthly_high"], dev_lo),
        sustainable_high=threshold(m["data_monthly_high"], dev_hi),
        cash_trough_low=f"{cash_lo:,}",
        cash_trough_high=f"{cash_hi:,}",
        reserve_low_wan=f"{reserve[0] / 10000:.1f}",
        reserve_high_wan=f"{reserve[1] / 10000:.1f}",
        founder_available_low=f"{m['illustrative_month12_payers'] * contrib - fixed - m['data_monthly_high'] - dev_hi:,}",
        founder_available_high=f"{m['illustrative_month12_payers'] * contrib - fixed - m['data_monthly_high'] - dev_lo:,}",
        heavy_usage_low=threshold(
            m["data_monthly_high"],
            dev_lo,
            contrib - (60 - m["paid_inference_per_month"]),
        ),
        heavy_usage_high=threshold(
            m["data_monthly_high"],
            dev_hi,
            contrib - (60 - m["paid_inference_per_month"]),
        ),
        expensive_data_low=threshold(10000, dev_lo),
        expensive_data_high=threshold(10000, dev_hi),
        cash_rows=rows,
    )
    return out


def validate(text: str) -> None:
    for banned in (
        "{{",
        "}}",
        "【待填",
        "【待拍板",
        "/Users/",
        "随本材料提交",
        "随材料提交",
        "<!-- PUBLIC_",
    ):
        if banned in text:
            raise ValueError(f"对外文本存在未处理内容或未经证实的附件承诺：{banned}")
    columns = None
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("|"):
            count = len(re.split(r"(?<!\\)\|", line)) - 2
            if columns is None:
                columns = count
            elif columns != count:
                raise ValueError(f"表格第{n}行列数{count}，应为{columns}")
        else:
            columns = None
    for stage in ("V1 Alpha", "V2 Beta", "V3 订阅验证", "V4 后续发展"):
        if f"| {stage} |" not in text:
            raise ValueError(f"阶段表缺失 {stage}")
    if text.count("<!-- PAGE_BREAK -->") != 7:
        raise ValueError("对外版应有8个明确分页区块")


def build(source: str, model: dict) -> str:
    if source.count(BEGIN) != 1 or source.count(END) != 1:
        raise ValueError("母本须有且仅有一组 PUBLIC 标记")
    if source.index(END) < source.index(BEGIN):
        raise ValueError("PUBLIC 标记顺序错误")
    public = source.split(BEGIN)[1].split(END)[0].strip()
    values = calculate(model)

    def resolve(match):
        key = match.group(1)
        if key not in values:
            raise ValueError(f"未知财务参数：{key}")
        return str(values[key])

    public = re.sub(r"\{\{([a-z0-9_]+)\}\}", resolve, public) + "\n"
    validate(public)
    return public


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    try:
        expected = build(SRC.read_text(), json.loads(MODEL.read_text()))
        if args.check:
            if not OUT.exists() or OUT.read_text() != expected:
                raise ValueError("对外版过期，请先重新生成")
            print("OK: 参数、完整阶段表、8页区块、缺失附件保护、生成内容一致")
        else:
            OUT.write_text(expected)
            print(f"Generated {OUT}; {len(expected)} chars")
    except ValueError as e:
        p.exit(1, f"ERROR: {e}\n")


if __name__ == "__main__":
    main()
