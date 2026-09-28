"""Recompute the two-report Knevo primary-source packet, without network or models.

This checks frozen page hashes, number presence, and accounting identities only.
It does not prove label binding, report authenticity, economic causality, or any
runtime's answer quality. Currency amounts stay in Decimal; monetary output is CNY.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

D = Decimal
EXPENSES = (
    "tax_surcharges",
    "selling",
    "administrative",
    "research_expense",
    "financial_expense",
)
GAINS = (
    "other_income",
    "investment_income",
    "fair_value_income",
    "credit_impairment",
    "asset_impairment",
    "disposal_income",
)


def require(condition: bool, label: str) -> None:
    if not condition:
        raise ValueError(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconcile(company: dict) -> dict:
    statement, observations = company["statement"], company["observations"]
    periods = {}
    for period in ("current", "prior"):
        values = {k: D(row[period]) for k, row in statement.items()}
        gross = values["revenue"] - values["cost"]
        operating = (
            gross
            - sum(values[k] for k in EXPENSES)
            + sum(values.get(k, D(0)) for k in GAINS)
        )
        require(
            operating == values["operating_profit"],
            f"{period}: operating profit mismatch",
        )
        pretax = (
            operating + values["nonoperating_income"] - values["nonoperating_expense"]
        )
        require(pretax == values["pretax_profit"], f"{period}: pretax mismatch")
        net = pretax - values["income_tax"]
        require(net == values["net_profit"], f"{period}: net profit mismatch")
        require(
            net - values["noncontrolling_profit"] == values["attributable_profit"],
            f"{period}: attribution mismatch",
        )
        require(
            D(observations["research_spend"][period])
            == values["research_expense"]
            + D(observations["capitalized_research"][period]),
            f"{period}: research spending mismatch",
        )
        periods[period] = {
            "gross_profit": gross,
            "gross_margin_pct": gross / values["revenue"] * 100,
            "selling_admin_research_ratio_pct": sum(values[k] for k in EXPENSES[1:4])
            / values["revenue"]
            * 100,
            "research_capitalization_pct": D(
                observations["capitalized_research"][period]
            )
            / D(observations["research_spend"][period])
            * 100,
        }
    nonrecurring = D(statement["attributable_profit"]["current"]) - D(
        observations["deducted_profit"]["current"]
    )
    require(
        nonrecurring == D(observations["nonrecurring_net"]["current"]),
        "nonrecurring mismatch",
    )

    def delta(key: str) -> Decimal:
        return D(statement[key]["current"]) - D(statement[key]["prior"])

    bridge = {
        "gross_profit": periods["current"]["gross_profit"]
        - periods["prior"]["gross_profit"]
    }
    bridge.update({k: -delta(k) for k in EXPENSES})
    bridge.update({k: delta(k) for k in GAINS if k in statement})
    bridge.update(
        {
            "nonoperating_income": delta("nonoperating_income"),
            "nonoperating_expense": -delta("nonoperating_expense"),
            "income_tax": -delta("income_tax"),
            "noncontrolling_profit": -delta("noncontrolling_profit"),
        }
    )
    require(
        sum(bridge.values()) == delta("attributable_profit"), "profit bridge mismatch"
    )
    rev0, rev1 = (D(statement["revenue"][p]) for p in ("prior", "current"))
    margin0, margin1 = (
        periods[p]["gross_margin_pct"] / 100 for p in ("prior", "current")
    )
    gross_bridge = {
        "revenue_change_at_prior_margin": (rev1 - rev0) * margin0,
        "margin_change_at_current_revenue": rev1 * (margin1 - margin0),
    }
    require(
        abs(sum(gross_bridge.values()) - bridge["gross_profit"]) < D("0.000001"),
        "gross bridge mismatch",
    )
    cash0, cash1 = (
        D(observations["operating_cashflow"][p]) for p in ("prior", "current")
    )
    result = {
        "code": company["code"],
        "periods": periods,
        "profit_bridge": bridge,
        "attributable_profit_change": delta("attributable_profit"),
        "gross_profit_identity_not_causal_attribution": gross_bridge,
        "nonrecurring_share_pct": nonrecurring
        / D(statement["attributable_profit"]["current"])
        * 100,
        "cashflow": {
            "prior": cash0,
            "current": cash1,
            "change": cash1 - cash0,
            "growth_abs_prior_pct": (cash1 - cash0) / abs(cash0) * 100,
            "sign_transition": f"{'negative' if cash0 < 0 else 'positive'}_to_{'negative' if cash1 < 0 else 'positive'}",
        },
    }
    remaining = observations["remaining_performance_obligations"]
    multiplier = D("100000000") if remaining.get("unit") == "CNY_100_million" else D(1)
    result["remaining_performance_obligations_cny"] = (
        D(remaining["current"]) * multiplier
    )
    schedule = [
        row
        for key, row in observations.items()
        if key.startswith("remaining_obligations_")
    ]
    if schedule:
        require(
            all(row.get("unit") == remaining.get("unit") for row in schedule),
            "remaining obligation unit mismatch",
        )
        require(
            sum(D(row["current"]) for row in schedule) == D(remaining["current"]),
            "remaining obligation schedule mismatch",
        )
    if "inventory_net" in observations:
        for period in ("current", "prior"):
            for prefix in ("inventory", "shipped_goods"):
                require(
                    D(observations[f"{prefix}_gross"][period])
                    - D(observations[f"{prefix}_allowance"][period])
                    == D(observations[f"{prefix}_net"][period]),
                    f"{prefix} balance mismatch",
                )
            require(
                D(observations["inventory_impairment"][period])
                + D(observations["contract_asset_impairment"][period])
                == D(statement["asset_impairment"][period]),
                "impairment categories mismatch",
            )

        def current(key: str) -> Decimal:
            return D(observations[key]["current"])

        def prior(key: str) -> Decimal:
            return D(observations[key]["prior"])

        result["inventory"] = {
            "shipped_goods_share_net_pct": current("shipped_goods_net")
            / current("inventory_net")
            * 100,
            "shipped_goods_share_gross_pct": current("shipped_goods_gross")
            / current("inventory_gross")
            * 100,
            "inventory_net_growth_since_2025_12_31_pct": (
                current("inventory_net") / prior("inventory_net") - 1
            )
            * 100,
            "shipped_goods_net_growth_since_2025_12_31_pct": (
                current("shipped_goods_net") / prior("shipped_goods_net") - 1
            )
            * 100,
        }
        result["software_vat_income_change"] = current(
            "software_vat_refund_income"
        ) - prior("software_vat_refund_income")
    return result


def verify_packet(root: Path) -> dict:
    sources = json.loads((root / "sources.json").read_text())
    facts = json.loads((root / "facts.json").read_text())
    require(facts["unit"] == "CNY", "unexpected unit")
    require(
        facts["current_period"] == "2026-01-01/2026-06-30"
        and facts["prior_period"] == "2025-01-01/2025-06-30",
        "unexpected periods",
    )
    documents = {d["code"]: d for d in sources["documents"]}
    require(
        set(documents) == {c["code"] for c in facts["companies"]},
        "company set mismatch",
    )
    count = 0
    for company in facts["companies"]:
        source = documents[company["code"]]
        require(
            source["published_date"] <= sources["research_cutoff"],
            "publication after cutoff",
        )
        for key in ("excerpts", "query"):
            require(
                sha(root / source[key]["file"]) == source[key]["sha256"],
                f"{key} hash mismatch",
            )
        excerpts = json.loads((root / source["excerpts"]["file"]).read_text())
        require(
            excerpts["code"] == company["code"]
            and excerpts["announcement_id"] == source["announcement_id"],
            "source identity mismatch",
        )
        pages = {
            p["pdf_page"]: p["raw_text"].replace(",", "") for p in excerpts["pages"]
        }
        for row in (*company["statement"].values(), *company["observations"].values()):
            require(
                row.get("unit", "CNY") in ("CNY", "CNY_100_million"),
                "unexpected row unit",
            )
            text = "\n".join(pages[p] for p in row["pages"])
            for period in ("current", "prior"):
                if period in row:
                    # PDF cells wrap within a number; keep boundaries between cells.
                    pattern = (
                        r"(?<![\d.\-])"
                        + r"\s*".join(re.escape(ch) for ch in row[period])
                        + r"(?![\d.])"
                    )
                    require(
                        re.search(pattern, text) is not None,
                        f"{company['code']} {period} amount not found on cited page: {row[period]}",
                    )
                    count += 1
    inputs = {"facts.json", "sources.json"}
    inputs.update(
        d[key]["file"] for d in documents.values() for key in ("excerpts", "query")
    )
    return {
        "scope": "finite offline accounting checks, not economic causality or model acceptance",
        "numeric_page_presence_checks": count,
        "input_hashes": {name: sha(root / name) for name in sorted(inputs)},
        "companies": [reconcile(c) for c in facts["companies"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_packet(args.packet)
    payload = json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n"
    if args.output:
        with args.output.open("x") as handle:
            handle.write(payload)
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
