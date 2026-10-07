"""教学标签的 **PIT 身份**:这条读数最早什么时候可知。

## 要解决的问题

旁路库原本只有 ``computed_at``(最后一次重算是什么时候)。重建走
``DELETE`` 全表再整批重插,于是**每一行历史的 ``computed_at`` 都被刷成本次构建时间**。
河的 PIT 闸(``river._enforce_cutoff``)按 ``recorded_at <= knowledge_cutoff`` 过滤,
而教学对象的 ``recorded_at`` 取的就是 ``computed_at``。

后果实测过:``trade_date=2026-01-12`` 的教学对象 ``recorded_at=2026-09-07``,
``knowledge_cutoff=2026-01-12`` 时**整条教学轨退化成 ``Gap(pit_filtered)``**。
也就是说——**在任何严格的历史切片上,教学标签一条都看不见**。
而「在时间长河里回放历史找规律」本质就是历史切片。

**闸是对的,不能动。**库里确实没有证据表明那天就知道这条读数。缺的是那个证据本身。

## 这里加的东西

``first_known_at``:这条读数**最早可知**的时刻。河改读它做 ``recorded_at``。

两种来源,**优先级从高到低**:

1. **交易日收盘**(``KNOWABLE_AT_CLOSE``)——只给有证据表明其算法是「前缀稳定」的标签:
   用截至当天的序列算出的当天值,与用完整序列算出的当天值相同。这种标签在当天收盘后
   即可算出,所以 ``first_known_at = 该交易日收盘``。**必须有证据才能进这张表。**

2. **沿用上一次**(carry-forward)——其余标签。重建时若某行内容(``value_num`` /
   ``value_text``)与上次相同,**保留它原来的 ``first_known_at``**,不再刷新。
   第一次构建时 = 构建时刻。

   这不能让它们在历史切片上可见(第一次构建就晚于历史日,本来也不该可见),
   但至少**停止了每次重建都把戳记往后推**,时间戳从此单调且诚实:
   「我们最早是什么时候看到这个值的」。

## 为什么不给所有标签都盖「交易日收盘」

因为那正是 2026-10-07 补证包证伪掉的那句话。它对 432 个交易日逐日比较
「完整序列算出的当天值」与「截至当天序列算出的当天值」,**18 个字段不一致**:
``chan_stroke_dir`` / ``chan_stroke_day`` / ``chan_stroke_count`` 各 186 天、
``chan_pivot_strokes`` 108 天、``chan_fractal`` 29 天,以及旧分型式背离
``macd_*_hist`` / ``macd_*_dif`` / ``days_since_macd_*_div``。

这份检查不支持把所有字段都视为当时可知；零差异结论也仅适用于已检查的标签与输入。

笔的方向会被后来的行情改写——那是缠论的定义使然,不是 bug。但一个会被改写的值
**不能**声称「那天就知道」。所以默认是保守的:没有证据 ⇒ 不进 ``KNOWABLE_AT_CLOSE``
⇒ 在历史切片上**继续**看不见。这是 fail-closed,和河的闸一个方向。
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Mapping, Sequence

#: A 股收盘 15:00 Asia/Shanghai = 07:00 UTC。旁路库的 TIMESTAMP 无时区,统一存 UTC。
#: 这是市场事实,不是谁的判断。但它**只对「当天收盘价就能算出」的标签成立**——
#: 龙虎榜(盘后 18:00 之后)、封单明细之类有发布延迟的输入**不适用**,
#: 这也是它们不在 ``KNOWABLE_AT_CLOSE`` 里的原因之一。
MARKET_CLOSE_UTC = time(7, 0)

#: 进这张表的唯一条件:**有证据**表明该标签的算法前缀稳定,且其输入在当天收盘即可得。
#: 每一条都必须在 ``KNOWABLE_AT_CLOSE_EVIDENCE`` 里写明证据,否则导入期断言会炸。
KNOWABLE_AT_CLOSE: frozenset[str] = frozenset({
    "tf.macd_bottom_div_observe",
    "tf.macd_bottom_div_confirm",
    "tf.macd_bottom_div_failed",
    "tf.macd_top_div",
})

#: 证据登记。两类都要有:**实测**(别人跑出来的数)和**读码**(机制上为什么成立)。
KNOWABLE_AT_CLOSE_EVIDENCE: dict[str, str] = {
    "tf.macd_bottom_div_observe": (
        "实测:2026-10-07 补证包 data/structure_prefix_check.json,432 个交易日完整序列 vs "
        "截至当天序列,该字段 0 处不一致(同批检查里 chan_stroke_dir 等 18 个字段有不一致)。"
        "读码:structure.py:83-112 事件记在 b+k 日,有 if b+k >= n: continue 守卫,只读 close[..i]。"
        "输入为收盘价,当日收盘即可算。"
    ),
    "tf.macd_bottom_div_confirm": "同 tf.macd_bottom_div_observe:同一份前缀检查 0 不一致,同一段算法。",
    "tf.macd_bottom_div_failed": "同 tf.macd_bottom_div_observe:同一份前缀检查 0 不一致,同一段算法。",
    "tf.macd_top_div": (
        "同 tf.macd_bottom_div_observe:同一份前缀检查 0 不一致,同一段算法。"
        "注意与 tf.macd_top_div_hist / tf.macd_top_div_dif 区分——那两个是旧分型式口径,"
        "在同一份检查里分别有 4 天 / 2 天不一致,**不在**本表内。"
    ),
}

#: 同一份前缀检查里**确认会改写历史**的字段。它们永远不得进 ``KNOWABLE_AT_CLOSE``;
#: 列在这里是为了让「为什么没加它」有据可查,而不是看起来像漏了。
KNOWN_HISTORY_REWRITING: dict[str, int] = {
    "tf.chan_stroke_dir": 186, "tf.chan_stroke_day": 186, "tf.chan_stroke_count": 186,
    "tf.chan_pivot_strokes": 108, "tf.chan_fractal": 29, "tf.chan_third_buy": 6,
    "tf.chan_pivot_zg": 6, "tf.chan_pivot_zd": 6, "tf.macd_top_div_hist": 4,
    "tf.chan_pivot_pos": 3, "tf.macd_top_div_dif": 2, "tf.days_since_macd_top_div": 2,
    "tf.macd_bottom_div_hist": 2, "tf.chan_third_sell": 2,
    "tf.chan_stroke_top_divergence": 1, "tf.macd_bottom_div_dif": 1,
    "tf.days_since_macd_bottom_div": 1, "tf.chan_stroke_bottom_divergence": 1,
}

LabelKey = tuple[str, str, Any, str]


def _assert_registry_is_backed() -> None:
    missing = sorted(KNOWABLE_AT_CLOSE - set(KNOWABLE_AT_CLOSE_EVIDENCE))
    if missing:
        raise AssertionError(
            f"{missing} 进了 KNOWABLE_AT_CLOSE 但没写证据。声称『当天就可知』需要证据——"
            "前缀一致性实测 + 算法只读历史的读码依据,两样都要。"
        )
    stale = sorted(set(KNOWABLE_AT_CLOSE_EVIDENCE) - KNOWABLE_AT_CLOSE)
    if stale:
        raise AssertionError(f"证据表里 {stale} 已不在 KNOWABLE_AT_CLOSE,请删掉,免得下一个人以为还在。")
    overlap = sorted(KNOWABLE_AT_CLOSE & set(KNOWN_HISTORY_REWRITING))
    if overlap:
        raise AssertionError(
            f"{overlap} 同时出现在 KNOWABLE_AT_CLOSE 和 KNOWN_HISTORY_REWRITING。"
            "一个会被后来行情改写的值不能声称那天就知道——补证包的前缀检查已证明它会变。"
        )


_assert_registry_is_backed()


def close_of(trade_date: Any) -> datetime:
    """该交易日的收盘时刻(naive UTC),即这类标签最早可知的时刻。"""

    if isinstance(trade_date, datetime):
        trade_date = trade_date.date()
    if not isinstance(trade_date, date):
        trade_date = date.fromisoformat(str(trade_date)[:10])
    return datetime.combine(trade_date, MARKET_CLOSE_UTC)


def previous_first_known(
    con: Any, *, where: str = "TRUE", params: Sequence[Any] = ()
) -> dict[LabelKey, tuple[Any, Any, Any]]:
    """重建前读下旧行:键 → ``(value_num, value_text, first_known_at)``。

    必须在 ``DELETE`` **之前**调用——这正是原来丢掉戳记的地方。
    表不存在或没有该列(旧库)时返回空 dict,调用方退化成「全部当新行」。
    """

    try:
        rows = con.execute(
            "SELECT entity_type, entity_id, trade_date, label, value_num, value_text, first_known_at "
            f"FROM history_teaching_labels WHERE {where}",
            list(params),
        ).fetchall()
    except Exception:  # noqa: BLE001 — 旧库没有这张表 / 这一列:当作没有历史戳记
        return {}
    return {(r[0], r[1], r[2], r[3]): (r[4], r[5], r[6]) for r in rows}


def first_known_at(
    *,
    label: str,
    entity_type: str,
    entity_id: str,
    trade_date: Any,
    value_num: Any,
    value_text: Any,
    previous: Mapping[LabelKey, tuple[Any, Any, Any]],
    build_time: datetime,
) -> datetime:
    """这条读数最早可知的时刻。见模块文档的两级优先。"""

    if label in KNOWABLE_AT_CLOSE:
        return close_of(trade_date)
    prior = previous.get((entity_type, entity_id, trade_date, label))
    if prior is not None and prior[2] is not None and prior[0] == value_num and prior[1] == value_text:
        # 内容没变 ⇒ 我们并不是「今天才知道」的,保留原戳记。
        got = prior[2]
        stamp = got if isinstance(got, datetime) else datetime.fromisoformat(str(got))
    else:
        stamp = build_time
    # TIMESTAMP 存 naive UTC；不能直接剥掉 +08:00 等偏移，那会改变真实可知时刻。
    return stamp.astimezone(timezone.utc).replace(tzinfo=None) if stamp.tzinfo else stamp


def horizon_note(label: str) -> str:
    """给收据/报错用的一句话:这个标签的 PIT 身份是怎么来的。"""

    if label in KNOWABLE_AT_CLOSE:
        return "knowable_at_close(有前缀一致性证据)"
    if label in KNOWN_HISTORY_REWRITING:
        return f"build_time(该字段在前缀检查中有 {KNOWN_HISTORY_REWRITING[label]} 天不一致,不能声称当日可知)"
    return "build_time(未提交前缀一致性证据;历史切片上不可见,这是 fail-closed)"


__all__ = [
    "MARKET_CLOSE_UTC", "KNOWABLE_AT_CLOSE", "KNOWABLE_AT_CLOSE_EVIDENCE",
    "KNOWN_HISTORY_REWRITING", "close_of", "previous_first_known",
    "first_known_at", "horizon_note",
]
