"""Citable succession qualifiers, derived only from the saved query original.

A status must not lose its reason when a writer/reviewer selects just that card.
This is a presentation adapter, not another succession calculator: no DB reads,
state reclassification, look-ahead, or rewriting of legacy artifacts.
"""

from __future__ import annotations

_MEANINGS = {
    "immature": "源峰后不足5交易日，尚不能判成败；无需先回撤确认。",
    "not_observed": "观察满5日，目标在声明窗未触发；非缺数或永久不接力。",
    "missing": "观察满5日，但信号或收益缺数/不确定；非0、非条件失败。",
    "outside_succession_window": "目标首信号不在(源峰,峰后第5交易日]；本口径不入选。",
    "not_supported": "同源峰后5日收益不满足目标>0且来源≤0；非永久失败。",
    "candidate_not_causal": "同源峰后5日目标>0且来源≤0，仅候选；无需回撤确认，非因果。",
}
_RULE = (
    "目标首信号在(源峰,源峰后第5交易日]；两方收益同用源峰后5日，非目标信号后5日；"
    "目标>0且来源≤0为候选；无需源峰回撤确认，不证资金迁移。"
)


def _saved_outcome_dates(row: dict, payload: dict) -> list | None:
    if isinstance(row.get("outcome_dates"), list):
        return row["outcome_dates"]
    # v1 did not save these dates in each pair. Reconstruct only from its frozen
    # calendar, never from start==end (which was an empty-window placeholder),
    # today's canonical DB, weekdays, or the enclosing authorization end.
    calendar = payload.get("calendar_inputs")
    spec = payload.get("spec", {})
    start, end, peak = spec.get("start"), spec.get("end"), row.get("anchor_peak_date")
    if not calendar or not all(isinstance(value, str) for value in (start, end, peak)):
        return None
    days = sorted({
        day for read in calendar for key in ("stock_dates", "market_dates")
        for day in read.get(key, []) if isinstance(day, str) and start <= day <= end
    })
    if peak not in days:
        return None
    return days[days.index(peak) + 1:days.index(peak) + 6]


def succession_atoms(row: dict, payload: dict) -> list[dict]:
    """Each dict is indivisible under _model_blocks' real 240-character budget."""
    version = payload.get("analysis_definition", {}).get("version")
    if version not in {"history-anatomy-v1", "history-anatomy-v1.1"}:
        return [{"succession_status": row.get("succession_status"),
                 "meaning": "未识别的接力定义，不能套用当前口径；请核对原件。"}]
    dates = _saved_outcome_dates(row, payload)
    status = row.get("succession_status")
    atoms = [
        {"succession_status": status,
         "observed_days": len(dates) if dates is not None else None,
         "required_days": row.get("outcome_required_days", 5),
         "meaning": _MEANINGS.get(status, "未知状态，不能判定成败；请核对原件。")},
        {"anchor_peak_date": row.get("anchor_peak_date"), "outcome_dates": dates},
        {"succession_rule": _RULE},
        {"source_peak_status": row.get("source_peak_status"),
         "source_peak_confirmation_date": row.get("source_peak_confirmation_date"),
         "meaning": "峰值确认与接力成熟度独立。"},
    ]
    target_status = row.get("target_signal_status")
    if target_status is None:
        target_status = next((
            item.get("signal_status") for item in payload.get("rows", [])
            if item.get("record_kind") == "launch_signal" and item.get("entity_code") == row.get("entity_code")
        ), None)
    atoms.append({"target_signal_date": row.get("target_signal_date"),
                  "target_signal_status": target_status})
    atoms.append({"lag_trading_days": row.get("lag_trading_days"),
                  "meaning": "lag为空不等于峰未确认；先看接力状态，不倒推原因。"})
    for key in ("start", "end", "succession_known_as_of", "causal_status"):
        if key in row:
            atoms.append({key: row[key]})
    atoms.extend({"succession_evidence": {key: value}, "return_window": "source_peak_next5"}
                 for key, value in row.get("evidence", {}).items())
    return atoms
