"""Finite regression checks for the archived primary-report arithmetic probe."""

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import shutil

import pytest

from scripts.review_probes.reconcile_knevo_primary import reconcile, verify_packet

PACKET = (
    Path(__file__).resolve().parents[1]
    / "docs/learning/knevo-distill/batches/2026-09-24-primary-audit"
)


def companies():
    return json.loads((PACKET / "facts.json").read_text())["companies"]


def test_frozen_packet_and_cashflow_signs():
    result = verify_packet(PACKET)
    assert result["numeric_page_presence_checks"] > 100
    assert (
        result["companies"][0]["cashflow"]["sign_transition"] == "positive_to_positive"
    )
    assert (
        result["companies"][1]["cashflow"]["sign_transition"] == "negative_to_positive"
    )
    assert result["companies"][1]["cashflow"]["growth_abs_prior_pct"].quantize(
        Decimal("0.01")
    ) == Decimal("513.86")
    assert result["companies"][1]["inventory"]["shipped_goods_share_net_pct"] < 25
    assert result["companies"][0]["remaining_performance_obligations_cny"] == Decimal(
        "9794000000"
    )
    assert result["companies"][1]["remaining_performance_obligations_cny"] == 0


@pytest.mark.parametrize(
    "key", ["cost", "income_tax", "noncontrolling_profit", "attributable_profit"]
)
def test_statement_mutations_fail(key):
    company = deepcopy(companies()[1])
    company["statement"][key]["current"] = str(
        Decimal(company["statement"][key]["current"]) + 1
    )
    with pytest.raises(ValueError, match="mismatch"):
        reconcile(company)


def test_remaining_obligation_schedule_mutation_fails():
    company = deepcopy(companies()[0])
    company["observations"]["remaining_obligations_2026"]["current"] = "94.16"
    with pytest.raises(ValueError, match="remaining obligation schedule"):
        reconcile(company)


def test_impairment_category_mutation_fails():
    company = deepcopy(companies()[1])
    company["observations"]["inventory_impairment"]["current"] = company["statement"][
        "asset_impairment"
    ]["current"]
    with pytest.raises(ValueError, match="impairment categories"):
        reconcile(company)


@pytest.mark.parametrize(
    "mutation",
    ["wrong_prior", "changed_page", "wrong_identity", "late_source", "wrong_period"],
)
def test_packet_boundaries_fail(tmp_path, mutation):
    packet = tmp_path / "packet"
    shutil.copytree(PACKET, packet)
    facts_path, sources_path = packet / "facts.json", packet / "sources.json"
    facts, sources = (
        json.loads(facts_path.read_text()),
        json.loads(sources_path.read_text()),
    )
    if mutation == "wrong_prior":
        facts["companies"][1]["observations"]["operating_cashflow"]["prior"] = (
            "54000000.00"
        )
        facts_path.write_text(json.dumps(facts))
    elif mutation == "changed_page":
        with (packet / "300604-pages.json").open("a") as handle:
            handle.write(" ")
    elif mutation == "wrong_identity":
        sources["documents"][1]["announcement_id"] = "wrong"
        sources_path.write_text(json.dumps(sources))
    elif mutation == "wrong_period":
        facts["prior_period"] = "2025-01-01/2025-12-31"
        facts_path.write_text(json.dumps(facts))
    else:
        sources["research_cutoff"] = "2026-08-01"
        sources_path.write_text(json.dumps(sources))
    with pytest.raises(ValueError):
        verify_packet(packet)
