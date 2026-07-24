"""估值确定性计算（researcher-valuation P2）：可比估值带 + 横截面分位.

对应 skills/researcher-valuation/SKILL.md 契约的第 1/2 段（估值现状、可比估值带）：
- 取数走东财免费快照接口（push2），不依赖 iFinD；同知识库 company-baseline-ingest
  的取数路线（AkShare/东财）。
- 计算层是纯函数：给定目标 + 可比快照，输出估值带（min/中位/max）与横截面分位，
  只给区间不给点位，缺数写显式缺口。
- 历史分位暂缺（东财快照不含历史 PE 序列），块内显式标注为缺口，留给 P3/后续数据源。
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

FETCH_ENV_FLAG = "FINANCE_VALUATION_FETCH"
# push2 主站偶发 502；delay 域名更稳。多端点兜底。
_PUSH2_URLS = (
    "https://push2delay.eastmoney.com/api/qt/stock/get"
    "?secid={secid}&fields=f57,f58,f116,f117,f162,f163,f164,f167",
    "https://push2.eastmoney.com/api/qt/stock/get"
    "?secid={secid}&fields=f57,f58,f116,f117,f162,f163,f164,f167",
)


@dataclass
class ValuationSnapshot:
    ts_code: str
    name: str
    total_mv_yi: float | None = None  # 总市值（亿元）
    pe_ttm: float | None = None
    pb: float | None = None
    source: str = "东财快照"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts_code": self.ts_code,
            "name": self.name,
            "total_mv_yi": self.total_mv_yi,
            "pe_ttm": self.pe_ttm,
            "pb": self.pb,
            "source": self.source,
        }


def fetch_enabled() -> bool:
    return os.environ.get(FETCH_ENV_FLAG, "1").strip().lower() not in {"0", "false", "off"}


def _secid(ts_code: str) -> str:
    raw = str(ts_code).split(".")[0]
    market = "1" if raw.startswith(("6", "5", "9")) else "0"
    return f"{market}.{raw}"


def _scale_num(value: Any, scale: float) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    # 东财偶发直接给已缩放小数；过大才按原始单位缩放
    num = float(value)
    if scale > 1 and abs(num) < scale:
        return round(num, 2)
    return round(num / scale, 2)


def fetch_eastmoney_snapshot(
    ts_code: str, name: str = "", timeout: float = 6.0
) -> ValuationSnapshot | None:
    """Best-effort 东财 push2 快照；网络/字段异常时返回 None，由上层写缺口."""
    data: dict[str, Any] = {}
    for template in _PUSH2_URLS:
        try:
            req = urllib.request.Request(
                template.format(secid=_secid(ts_code)),
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            data = payload.get("data") or {}
            if data:
                break
        except Exception:
            continue
    if not data:
        return None

    # PE: f164=TTM 优先，其次 f163/f162；PB: f167
    pe = _scale_num(data.get("f164"), 100.0)
    if pe is None:
        pe = _scale_num(data.get("f163"), 100.0)
    if pe is None:
        pe = _scale_num(data.get("f162"), 100.0)
    snap = ValuationSnapshot(
        ts_code=ts_code,
        name=str(data.get("f58") or name or ts_code),
        total_mv_yi=_scale_num(data.get("f116"), 1e8),
        pe_ttm=pe,
        pb=_scale_num(data.get("f167"), 100.0),
        source="东财快照",
    )
    if snap.total_mv_yi is None and snap.pe_ttm is None and snap.pb is None:
        return None
    return snap


def _valid(values: list[float | None]) -> list[float]:
    return [float(v) for v in values if v is not None and v > 0]


def peer_band(values: list[float | None]) -> tuple[float, float, float] | None:
    """可比估值带：min / 中位 / max（只给区间不给点位）."""
    clean = sorted(_valid(values))
    if len(clean) < 2:
        return None
    n = len(clean)
    mid = clean[n // 2] if n % 2 else round((clean[n // 2 - 1] + clean[n // 2]) / 2, 2)
    return (clean[0], mid, clean[-1])


def percentile_rank(values: list[float | None], target: float | None) -> float | None:
    """target 在可比集合中的横截面分位（0-100，含并列取 <= 占比）."""
    clean = _valid(values)
    if target is None or target <= 0 or not clean:
        return None
    return round(100.0 * sum(1 for v in clean if v <= target) / len(clean), 1)


def _pb_scenario_anchors(
    target: ValuationSnapshot,
    band: tuple[float, float, float],
) -> tuple[tuple[str, float, float, float | None, float | None], ...] | None:
    """Derive auditable scenario intervals from observed PB anchors only."""

    if target.pb is None or target.pb <= 0:
        return None
    low, median, high = band
    current = min(max(float(target.pb), low), high)
    neutral_low, neutral_high = sorted((current, median))
    intervals = (
        ("保守", low, neutral_low),
        ("中性", neutral_low, neutral_high),
        ("乐观", neutral_high, high),
    )
    rendered = []
    for label, lower, upper in intervals:
        if target.total_mv_yi is None:
            mv_low = mv_high = None
        else:
            mv_low = round(target.total_mv_yi * lower / target.pb, 2)
            mv_high = round(target.total_mv_yi * upper / target.pb, 2)
        rendered.append((label, lower, upper, mv_low, mv_high))
    return tuple(rendered)


def build_valuation_block(
    target: ValuationSnapshot | None,
    peers: list[ValuationSnapshot],
    fetch_disabled: bool = False,
) -> str:
    """生成 D5 估值数据块（注入 compose）；缺数时仍返回带显式缺口的块."""
    lines = ["## 估值数据块 [D5]（估值快照硬数据；只给区间不给目标价）"]
    if fetch_disabled:
        lines.append(f"- ⚠估值取数已被 {FETCH_ENV_FLAG}=0 关闭：估值现状/可比带全部为缺口，需说明数据不可得。")
        return "\n".join(lines)
    if target is None:
        lines.append("- ⚠缺目标估值快照：未取到目标公司 PE/PB/市值，估值现状按缺口处理。")
        return "\n".join(lines)
    mv = f"{target.total_mv_yi} 亿" if target.total_mv_yi is not None else "缺"
    pe = target.pe_ttm if target.pe_ttm is not None else "缺（可能亏损或未取到）"
    pb = target.pb if target.pb is not None else "缺"
    src = target.source or "估值快照"
    lines.append(
        f"- 目标估值现状：{target.name}（{target.ts_code}）总市值 {mv}，PE(TTM) {pe}，PB {pb}（来源：{src}）。"
    )
    if peers:
        pe_band = peer_band([p.pe_ttm for p in peers])
        pb_band = peer_band([p.pb for p in peers])
        peer_desc = "、".join(
            f"{p.name} PE {p.pe_ttm if p.pe_ttm is not None else '缺'}/PB {p.pb if p.pb is not None else '缺'}"
            for p in peers
        )
        lines.append(f"- 可比公司快照（同题材成交前排，共 {len(peers)} 家）：{peer_desc}。")
        if pe_band:
            if target.pe_ttm is not None and target.pe_ttm <= 0:
                pos = "（目标 PE 为负/亏损，不宜用 PE 横截面分位，优先看 PB/PS 与市值）"
            else:
                pct = percentile_rank([p.pe_ttm for p in peers], target.pe_ttm)
                pos = (
                    f"，目标横截面分位约 {pct}%"
                    if pct is not None
                    else "（目标 PE 缺，无法定位分位）"
                )
            lines.append(f"- 可比 PE(TTM) 估值带：{pe_band[0]} ~ {pe_band[2]}，中位 {pe_band[1]}{pos}。")
        if pb_band:
            lines.append(f"- 可比 PB 估值带：{pb_band[0]} ~ {pb_band[2]}，中位 {pb_band[1]}。")
            scenario_anchors = _pb_scenario_anchors(target, pb_band)
            if scenario_anchors:
                rendered_anchors = []
                for label, lower, upper, mv_low, mv_high in scenario_anchors:
                    market_cap = (
                        f"（隐含市值 {mv_low} ~ {mv_high} 亿）"
                        if mv_low is not None and mv_high is not None
                        else ""
                    )
                    rendered_anchors.append(
                        f"{label} {lower} ~ {upper} 倍{market_cap}"
                    )
                lines.append(
                    "- PB 情景计算锚（机械推演，不是目标价；假设净资产不变）："
                    + "；".join(rendered_anchors)
                    + "。情景条件由分析层说明，但不得改写这些数值锚。"
                )
        if not pe_band and not pb_band:
            lines.append("- ⚠可比集有效估值不足 2 家，估值带按缺口处理。")
    else:
        lines.append("- ⚠缺可比集：未取到同题材可比公司快照，可比估值带按缺口处理。")
    lines.append("- ⚠缺历史分位：当前数据源无历史 PE/PS 序列，历史分位按缺口处理，不得编造。")
    lines.append(
        "- 使用要求：估值现状/可比带只引用本块硬数据；隐含预期与情景推演须条件化表述，禁止输出单点目标价。"
    )
    return "\n".join(lines)


def snapshots_for(
    codes: list[tuple[str, str]],
    fetcher: Callable[..., ValuationSnapshot | None] = fetch_eastmoney_snapshot,
) -> list[ValuationSnapshot]:
    out: list[ValuationSnapshot] = []
    for ts_code, name in codes:
        snap = fetcher(ts_code, name)
        if snap is not None:
            out.append(snap)
    return out
