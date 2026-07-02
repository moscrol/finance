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
_PUSH2_URL = (
    "https://push2.eastmoney.com/api/qt/stock/get"
    "?secid={secid}&fields=f57,f58,f116,f164,f167"
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


def fetch_eastmoney_snapshot(
    ts_code: str, name: str = "", timeout: float = 6.0
) -> ValuationSnapshot | None:
    """Best-effort 东财 push2 快照；网络/字段异常时返回 None，由上层写缺口."""
    try:
        req = urllib.request.Request(
            _PUSH2_URL.format(secid=_secid(ts_code)),
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8")).get("data") or {}
    except Exception:
        return None

    def _num(key: str, scale: float) -> float | None:
        v = data.get(key)
        if not isinstance(v, (int, float)):
            return None
        return round(float(v) / scale, 2)

    snap = ValuationSnapshot(
        ts_code=ts_code,
        name=str(data.get("f58") or name or ts_code),
        total_mv_yi=_num("f116", 1e8),
        pe_ttm=_num("f164", 100.0),
        pb=_num("f167", 100.0),
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


def build_valuation_block(
    target: ValuationSnapshot | None,
    peers: list[ValuationSnapshot],
    fetch_disabled: bool = False,
) -> str:
    """生成 D5 估值数据块（注入 compose）；缺数时仍返回带显式缺口的块."""
    lines = ["## 估值数据块 [D5]（东财快照，硬数据；只给区间不给目标价）"]
    if fetch_disabled:
        lines.append(f"- ⚠估值取数已被 {FETCH_ENV_FLAG}=0 关闭：估值现状/可比带全部为缺口，需说明数据不可得。")
        return "\n".join(lines)
    if target is None:
        lines.append("- ⚠缺目标估值快照：东财接口未取到目标公司 PE/PB/市值，估值现状按缺口处理。")
        return "\n".join(lines)
    mv = f"{target.total_mv_yi} 亿" if target.total_mv_yi is not None else "缺"
    pe = target.pe_ttm if target.pe_ttm is not None else "缺（可能亏损或未取到）"
    pb = target.pb if target.pb is not None else "缺"
    lines.append(
        f"- 目标估值现状：{target.name}（{target.ts_code}）总市值 {mv}，PE(TTM) {pe}，PB {pb}。"
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
            pct = percentile_rank([p.pe_ttm for p in peers], target.pe_ttm)
            pos = f"，目标横截面分位约 {pct}%" if pct is not None else "（目标 PE 缺，无法定位分位）"
            lines.append(f"- 可比 PE(TTM) 估值带：{pe_band[0]} ~ {pe_band[2]}，中位 {pe_band[1]}{pos}。")
        if pb_band:
            lines.append(f"- 可比 PB 估值带：{pb_band[0]} ~ {pb_band[2]}，中位 {pb_band[1]}。")
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
