from __future__ import annotations

from intelligence.eval.tool_payload import attribute_failed_fact
from intelligence.services.tool_payload import field_names_from_rows, tool_payload_meta


def test_tool_payload_meta_hashes_dataset_and_field_names_not_values() -> None:
    first = tool_payload_meta(
        dataset="sector_daily",
        caliber="fact_sector_daily",
        field_names=("sector_name", "amount"),
    )
    second = tool_payload_meta(
        dataset="sector_daily",
        caliber="fact_sector_daily",
        field_names=("sector_name", "amount"),
    )
    assert first == second
    dataset, caliber, names, digest = first
    assert dataset == "sector_daily"
    assert caliber == "fact_sector_daily"
    assert names == ("sector_name", "amount")
    assert len(digest) == 64
    # Same names, different values would not exist here — the helper never
    # sees row bodies. Changing names must change the digest.
    other = tool_payload_meta(
        dataset="sector_daily",
        field_names=("sector_name", "pct_chg"),
    )
    assert other[3] != digest


def test_empty_rows_keep_requested_field_names() -> None:
    names = field_names_from_rows((), requested=("trade_date", "total_amount"))
    assert names == ("trade_date", "total_amount")
    dataset, _, payload_names, digest = tool_payload_meta(
        dataset="market_daily",
        field_names=names,
    )
    assert dataset == "market_daily"
    assert payload_names == ("trade_date", "total_amount")
    assert digest


def test_missing_dataset_and_names_become_unknown() -> None:
    dataset, caliber, names, digest = tool_payload_meta()
    assert dataset == "unknown"
    assert caliber == ""
    assert names == ("unknown",)
    assert len(digest) == 64


def test_absolute_paths_are_stripped_from_persisted_tokens() -> None:
    dataset, _, names, _ = tool_payload_meta(
        dataset="/Users/a77/secret.duckdb",  # path-literal-ok: 脱敏夹具，断言产出不含家目录
        field_names=("/home/foo/col", "amount"),  # path-literal-ok: 同上
    )
    assert dataset == "unknown"
    assert names == ("amount",)
    assert all("/Users/" not in item and "/home/" not in item for item in names)


def test_row_keys_win_over_requested_names() -> None:
    names = field_names_from_rows(
        ({"trade_date": "2026-07-23", "amount": 1},),
        requested=("trade_date", "return_pct"),
    )
    assert names == ("trade_date", "amount")


def test_failed_fact_is_synthesize_when_field_was_fetched() -> None:
    assert (
        attribute_failed_fact(
            expected_field="close",
            expected_dataset="stock_daily",
            tool_results=[
                {
                    "dataset": "stock_daily",
                    "caliber": "fact_stock_daily",
                    "payload_field_names": ["trade_date", "close"],
                }
            ],
        )
        == "synthesize"
    )


def test_failed_fact_is_retrieve_when_dataset_differs() -> None:
    """A5 shape: same column name on the wrong table is still retrieve."""
    assert (
        attribute_failed_fact(
            expected_field="储能.limit_up_count",
            expected_dataset="fact_theme_limit_heat_daily",
            tool_results=[
                {
                    "dataset": "mainline_sector_daily",
                    "caliber": "fact_mainline_sector_daily",
                    "payload_field_names": ["sector_name", "limit_up_count"],
                }
            ],
        )
        == "retrieve"
    )


def test_failed_fact_is_unknown_without_payload_meta() -> None:
    assert (
        attribute_failed_fact(
            expected_field="close",
            expected_dataset="stock_daily",
            tool_results=[{"ok": True, "tool": "finance_query"}],
        )
        == "unknown"
    )
