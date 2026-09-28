"""参数文件 ``methodology/events/event_reaction_params.v0.1.json`` 的加载与版本号。

``ev_version = <base>+sha256(参数文件 ⊕ 全部日程文件)[:8]``：参数或日程任一字节变，版本变，旧收据不可比。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PARAMS_PATH = REPO_ROOT / "methodology" / "events" / "event_reaction_params.v0.1.json"

REACTION_RULES = ("same_day_or_next", "next_trading_day", "next_trading_day_after_us_date")
SCOPES = ("market", "sector")
PERIOD_KINDS = ("release_month", "title_month", "event_date", "none")


@dataclass(frozen=True)
class EventClassSpec:
    name: str
    scope: str
    scheduled: bool
    reaction_rule: str
    indicators: tuple[str, ...]
    period_kind: str
    reaction_day_confidence: str
    title_any: tuple[str, ...]
    title_all_any: tuple[str, ...]
    title_none: tuple[str, ...]
    event_type_in: tuple[str, ...]
    require_sectors: bool
    editorial_reaction_rule: str | None = None

    @property
    def rule_for_editorial(self) -> str:
        return self.editorial_reaction_rule or self.reaction_rule


@dataclass(frozen=True)
class EventParams:
    path: Path
    schedule_dir: Path
    schedule_files: tuple[Path, ...]
    ev_version: str
    pre_days: int
    post_horizons: tuple[int, ...]
    shape_horizon: int
    shape_threshold_pct: dict[str, float]
    amount_ratio_lookback_days: int
    crowding_lookback_days: int
    crowding_min_obs: int
    min_n: int
    bh_q: float
    cross_section_top_k: int
    lpr_day_of_month: int
    lpr_rule_published_at: str
    classes: dict[str, EventClassSpec] = field(default_factory=dict)

    @property
    def market_classes(self) -> list[str]:
        return [c for c, s in self.classes.items() if s.scope == "market"]

    @property
    def sector_classes(self) -> list[str]:
        return [c for c, s in self.classes.items() if s.scope == "sector"]

    def indicator_to_class(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name, spec in self.classes.items():
            for ind in spec.indicators:
                out[ind] = name
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "ev_version": self.ev_version,
            "schedule_files": [str(p) for p in self.schedule_files],
            "pre_days": self.pre_days,
            "post_horizons": list(self.post_horizons),
            "shape_horizon": self.shape_horizon,
            "shape_threshold_pct": dict(self.shape_threshold_pct),
            "amount_ratio_lookback_days": self.amount_ratio_lookback_days,
            "crowding_lookback_days": self.crowding_lookback_days,
            "crowding_min_obs": self.crowding_min_obs,
            "min_n": self.min_n,
            "bh_q": self.bh_q,
            "cross_section_top_k": self.cross_section_top_k,
            "event_classes": sorted(self.classes),
        }


def _tuple(v: Any) -> tuple[str, ...]:
    if not v:
        return ()
    return tuple(str(x) for x in v)


def _parse_class(name: str, raw: dict[str, Any]) -> EventClassSpec:
    scope = str(raw.get("scope") or "")
    if scope not in SCOPES:
        raise ValueError(f"event_classes.{name}.scope 必须是 {SCOPES}，得到 {scope!r}")
    rule = str(raw.get("reaction_rule") or "")
    if rule not in REACTION_RULES:
        raise ValueError(f"event_classes.{name}.reaction_rule 必须是 {REACTION_RULES}，得到 {rule!r}")
    period_kind = str(raw.get("period_kind") or "none")
    if period_kind not in PERIOD_KINDS:
        raise ValueError(f"event_classes.{name}.period_kind 必须是 {PERIOD_KINDS}，得到 {period_kind!r}")
    ed = raw.get("editorial") or {}
    if not isinstance(ed, dict):
        raise ValueError(f"event_classes.{name}.editorial 必须是对象")
    ed_rule = ed.get("reaction_rule")
    if ed_rule is not None and str(ed_rule) not in REACTION_RULES:
        raise ValueError(f"event_classes.{name}.editorial.reaction_rule 必须是 {REACTION_RULES}，得到 {ed_rule!r}")
    return EventClassSpec(
        name=name,
        scope=scope,
        scheduled=bool(raw.get("scheduled", False)),
        reaction_rule=rule,
        indicators=_tuple(raw.get("indicators")),
        period_kind=period_kind,
        reaction_day_confidence=str(raw.get("reaction_day_confidence") or "normal"),
        title_any=_tuple(ed.get("title_any")),
        title_all_any=_tuple(ed.get("title_all_any")),
        title_none=_tuple(ed.get("title_none")),
        event_type_in=_tuple(ed.get("event_type_in")),
        require_sectors=bool(ed.get("require_sectors", False)),
        editorial_reaction_rule=(str(ed_rule) if ed_rule is not None else None),
    )


def load_params(path: str | Path | None = None, *, schedule_dir: str | Path | None = None) -> EventParams:
    p = Path(path).expanduser() if path else DEFAULT_PARAMS_PATH
    if not p.is_file():
        raise FileNotFoundError(f"参数文件不存在: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("参数文件顶层必须是对象")
    sdir_raw = schedule_dir or raw.get("schedule_dir") or "references/calendars"
    sdir = Path(sdir_raw).expanduser()
    if not sdir.is_absolute():
        sdir = REPO_ROOT / sdir
    files = tuple(sorted(sdir.glob("official_release_schedule.*.json"))) if sdir.is_dir() else ()

    digest = hashlib.sha256(p.read_bytes())
    for f in files:
        digest.update(f.name.encode("utf-8"))
        digest.update(f.read_bytes())
    base = str(raw.get("ev_version_base") or "ev-v0")
    version = f"{base}+{digest.hexdigest()[:8]}"

    horizons = tuple(sorted({int(h) for h in (raw.get("post_horizons") or [3, 5, 10])}))
    if any(h <= 0 for h in horizons):
        raise ValueError("post_horizons 必须是正整数")
    shape_h = int(raw.get("shape_horizon") or 5)
    if shape_h not in horizons:
        raise ValueError(f"shape_horizon={shape_h} 必须在 post_horizons {horizons} 里")
    thresholds = {str(k): float(v) for k, v in (raw.get("shape_threshold_pct") or {}).items()}
    for scope in SCOPES:
        if scope not in thresholds:
            raise ValueError(f"shape_threshold_pct 缺 {scope}")
    classes_raw = raw.get("event_classes") or {}
    if not isinstance(classes_raw, dict) or not classes_raw:
        raise ValueError("event_classes 不能为空")
    classes = {str(n): _parse_class(str(n), c) for n, c in classes_raw.items()}
    lpr_rule = raw.get("lpr_rule") or {}
    return EventParams(
        path=p,
        schedule_dir=sdir,
        schedule_files=files,
        ev_version=version,
        pre_days=int(raw.get("pre_days") or 5),
        post_horizons=horizons,
        shape_horizon=shape_h,
        shape_threshold_pct=thresholds,
        amount_ratio_lookback_days=int(raw.get("amount_ratio_lookback_days") or 20),
        crowding_lookback_days=int(raw.get("crowding_lookback_days") or 60),
        crowding_min_obs=int(raw.get("crowding_min_obs") or 30),
        min_n=int(raw.get("min_n") or 10),
        bh_q=float(raw.get("bh_q") or 0.05),
        cross_section_top_k=int(raw.get("cross_section_top_k") or 5),
        lpr_day_of_month=int(lpr_rule.get("day_of_month") or 20),
        lpr_rule_published_at=str(lpr_rule.get("rule_published_at") or "2019-08-17"),
        classes=classes,
    )
