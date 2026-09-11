"""舆论生命周期阶段（工单 #36 / roadmap G-06）：从研报事件确定性派生「一条逻辑传播到哪一段」。

舆论轨今天有两条线：研报**覆盖密度**（``river.coverage_metrics``：近 90 日 / 累计）与观点事件的
**认同度下限阶梯**（``skills/opinion-cross/scripts/consensus_staging.py``：暗流 → 萌芽 → 第一轮 →
催化共振 → 一致认同，**只升不降**）。两条都不是生命周期——前者是量，后者按定义不能退。
三维对照要的是一条能升也能退的阶段轴。

词表（钦定，进 ``UBIQUITOUS_LANGUAGE.md``「舆论生命周期」）：

| 段 | 含义（只说传播，不说涨跌） | 进入条件（全部从 ``recorded_at <= C`` 的研报事件算） |
|---|---|---|
| 萌芽 | 刚被少数来源覆盖 | ``1 <= count_90d < TH_RESONANCE_SOURCES`` |
| 扩散 | 覆盖在增加 / 维持 | ``count_90d >= TH_RESONANCE_SOURCES`` 且未到拥挤、未退热；30 日斜率进 inputs |
| 拥挤 | 密度到自身历史高位且来源广 | ``count_90d >= TH_CONSENSUS_SOURCES`` 且近 90 日不同报告日 ``>= TH_CONSENSUS_DAYS`` 且 ``count_90d >= 自身历史 p80``（历史 < 60 观测日不判拥挤，停在扩散） |
| 退热 | 从拥挤峰回落 | 近 120 日曾到拥挤，且 30 日斜率连续 ``>= 10`` 个观测日 ``< 0``；或曾拥挤而 ``count_90d = 0`` |
| 证伪（终态） | 逻辑被结构化证伪事件否定 | 存在 ``kind=falsification`` 事件且 ``valid_from <= T``。**今天河里没有这种对象**：本段定义在、读数恒 0；不得从价格推断 |
| unverifiable | 负证据缺失 | ``count_90d = 0`` 且无任何事件；**不叫「无人问津」**（路线图 §5 第 3 题推荐答案） |

三个阈值**从 ``consensus_staging`` 取**，不复制数字：该脚本 import 时会拉 skill 内部依赖，所以用 ``ast``
只读常量，不执行（``load_thresholds``）。``p80`` 从实体自身历史算，不用全市场常数——不同题材覆盖体量差一个量级。

**无状态**：``derive_stage(hits, as_of)`` 每天独立从事件重算；「曾到过拥挤」靠回看事件重算，不存上一天的状态——
这就是「不落状态机」的含义。回填批次（同一 ``created_at`` 日入库 >= 10 份）在 inputs 里点名，斜率读数不可比。

与认同度阶梯的关系：``consensus_staging`` 是「证据至少撑到哪一阶」（下限、单调），本词表是「传播走到哪一段」
（可退）；三维对照**只用本词表**，``opinion_cross`` 技能继续用阶梯，两边不互译、不互相覆盖。
阅读参考映射：暗流 → unverifiable / 萌芽，萌芽 → 萌芽，第一轮 / 催化共振 → 扩散，一致认同 → 拥挤。
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSENSUS_STAGING_PATH = REPO_ROOT / "skills" / "opinion-cross" / "scripts" / "consensus_staging.py"

STAGE_SPROUT = "萌芽"
STAGE_SPREAD = "扩散"
STAGE_CROWDED = "拥挤"
STAGE_COOLING = "退热"
STAGE_FALSIFIED = "证伪"
UNVERIFIABLE = "unverifiable"
STAGES: tuple[str, ...] = (STAGE_SPROUT, STAGE_SPREAD, STAGE_CROWDED, STAGE_COOLING, STAGE_FALSIFIED)
# 粗序（早 / 中 / 晚），供错位标记与题材侧并排；证伪与 unverifiable 不在序上。
STAGE_COARSE: dict[str, str] = {STAGE_SPROUT: "early", STAGE_SPREAD: "mid", STAGE_CROWDED: "late", STAGE_COOLING: "late"}

DERIVATION_RULE = {"name": "opinion_stage", "version": "os-v0"}

WINDOW_DAYS = 90
SLOPE_DAYS = 30
COOLING_STREAK = 10
LOOKBACK_DAYS = 120
MIN_HISTORY_OBS = 60
P80 = 0.8
BACKFILL_BATCH_MIN = 10


# --------------------------------------------------------------------------- #
# 阈值：只读 consensus_staging 的常量，不 import（它会拉 skill 内部依赖）
# --------------------------------------------------------------------------- #
_THRESHOLD_NAMES = ("TH_RESONANCE_SOURCES", "TH_CONSENSUS_SOURCES", "TH_CONSENSUS_DAYS")


def load_thresholds(path: Path | None = None) -> dict[str, int]:
    """从 ``consensus_staging.py`` 的模块级赋值里读三个阈值。找不到任一条即抛错——不静默回落到写死值。"""
    src = (path or CONSENSUS_STAGING_PATH).read_text(encoding="utf-8")
    tree = ast.parse(src)
    found: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in _THRESHOLD_NAMES:
                found[name] = int(ast.literal_eval(node.value))
    missing = [n for n in _THRESHOLD_NAMES if n not in found]
    if missing:
        raise RuntimeError(f"consensus_staging.py 缺阈值 {missing}：舆论阶段词表的阈值真源是它，不在这里补写")
    return found


THRESHOLDS = load_thresholds()
TH_RESONANCE_SOURCES = THRESHOLDS["TH_RESONANCE_SOURCES"]
TH_CONSENSUS_SOURCES = THRESHOLDS["TH_CONSENSUS_SOURCES"]
TH_CONSENSUS_DAYS = THRESHOLDS["TH_CONSENSUS_DAYS"]


# --------------------------------------------------------------------------- #
# 读数对象
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StageReadout:
    as_of: str
    stage: str
    reasons: tuple[str, ...]
    inputs: dict[str, Any]
    derivation_rule: dict[str, str] = field(default_factory=lambda: dict(DERIVATION_RULE))

    @property
    def coarse(self) -> str | None:
        return STAGE_COARSE.get(self.stage)

    @property
    def source_hash(self) -> str:
        body = {"as_of": self.as_of, "stage": self.stage, "inputs": self.inputs, "rule": self.derivation_rule}
        return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of,
            "stage": self.stage,
            "coarse": self.coarse,
            "reasons": list(self.reasons),
            "inputs": self.inputs,
            "derivation_rule": self.derivation_rule,
            "source_hash": self.source_hash,
        }


# --------------------------------------------------------------------------- #
# 事件规整
# --------------------------------------------------------------------------- #
def _d(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


@dataclass(frozen=True)
class _Hit:
    report_date: date
    recorded_at: date | None  # created_at 的日期部分；None = 记录时刻不可判


def normalize_hits(hits: list[dict[str, Any]]) -> list[_Hit]:
    """研报行 → (report_date, recorded_at)。缺 report_date 的行丢弃（没有有效时间就不是事件）。"""
    out: list[_Hit] = []
    for r in hits:
        rd = _d(r.get("report_date"))
        if rd is None:
            continue
        out.append(_Hit(rd, _d(r.get("created_at") if r.get("created_at") is not None else r.get("recorded_at"))))
    out.sort(key=lambda h: h.report_date)
    return out


def visible_hits(hits: list[_Hit], as_of: date, knowledge_cutoff: date) -> list[_Hit]:
    """有效时间 ``report_date <= as_of``，记录时间 ``recorded_at <= C``（记录时刻不可判的行**不算**——不猜）。"""
    return [h for h in hits if h.report_date <= as_of and h.recorded_at is not None and h.recorded_at <= knowledge_cutoff]


def _count_window(hits: list[_Hit], as_of: date, days: int) -> int:
    lo = as_of - timedelta(days=days)
    return sum(1 for h in hits if lo < h.report_date <= as_of)


def _distinct_days_window(hits: list[_Hit], as_of: date, days: int) -> int:
    lo = as_of - timedelta(days=days)
    return len({h.report_date for h in hits if lo < h.report_date <= as_of})


def _quantile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    pos = q * (len(xs) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def backfill_batch_dates(hits: list[_Hit]) -> list[str]:
    """同一 ``created_at`` 日入库 >= BACKFILL_BATCH_MIN 份 → 回填批次；这些日子附近的密度斜率是采集节奏不是舆论。"""
    counts: dict[date, int] = {}
    for h in hits:
        if h.recorded_at is not None:
            counts[h.recorded_at] = counts.get(h.recorded_at, 0) + 1
    return sorted(str(d) for d, n in counts.items() if n >= BACKFILL_BATCH_MIN)


# --------------------------------------------------------------------------- #
# 派生（无状态）
# --------------------------------------------------------------------------- #
def _crowded_on(hits: list[_Hit], day: date, p80: float | None, history_obs: int) -> bool:
    if history_obs < MIN_HISTORY_OBS or p80 is None:
        return False
    c = _count_window(hits, day, WINDOW_DAYS)
    return (
        c >= TH_CONSENSUS_SOURCES
        and _distinct_days_window(hits, day, WINDOW_DAYS) >= TH_CONSENSUS_DAYS
        and c >= p80
    )


def derive_stage(
    raw_hits: list[dict[str, Any]],
    as_of: str,
    *,
    knowledge_cutoff: str | None = None,
    falsification_dates: list[str] | tuple[str, ...] = (),
) -> StageReadout:
    """一条逻辑在 ``as_of`` 这天的传播阶段。纯函数：同一批事件 + 同一天 → 同一读数。"""
    T = date.fromisoformat(as_of)
    C = date.fromisoformat(knowledge_cutoff) if knowledge_cutoff else T
    if C < T:
        raise ValueError(f"knowledge_cutoff={C} 早于 as_of={T}：站在 C 看不见 T")
    all_hits = normalize_hits(raw_hits)
    hits = visible_hits(all_hits, T, C)
    reasons: list[str] = []

    dropped = len([h for h in all_hits if h.report_date <= T]) - len(hits)
    if dropped:
        reasons.append(f"{dropped} 份研报记录时刻晚于 C 或不可判，未计入")

    fals = sorted(d for d in (_d(x) for x in falsification_dates) if d is not None and d <= T)
    count_90d = _count_window(hits, T, WINDOW_DAYS)
    count_90d_prev = _count_window(hits, T - timedelta(days=SLOPE_DAYS), WINDOW_DAYS)
    slope_30 = count_90d - count_90d_prev
    distinct_days = _distinct_days_window(hits, T, WINDOW_DAYS)
    first = hits[0].report_date if hits else None

    # 自身历史：从首次覆盖起逐日 count_90d 序列（含当天）。p80 只在观测日 >= 60 时成立。
    history: list[int] = []
    if first is not None:
        span = (T - first).days
        step = 1 if span <= 800 else max(1, span // 800)  # 极长历史按步长抽样，读数仍确定
        d = first
        while d <= T:
            history.append(_count_window(hits, d, WINDOW_DAYS))
            d += timedelta(days=step)
    history_obs = len(history)
    p80 = _quantile(history, P80) if history_obs >= MIN_HISTORY_OBS else None

    # 近 120 日是否曾到拥挤（含今天之前）；连续为负的斜率天数。
    was_crowded = False
    cooling_streak = 0
    if hits:
        for k in range(0, LOOKBACK_DAYS + 1):
            day = T - timedelta(days=k)
            if day < first:
                break
            if _crowded_on(hits, day, p80, history_obs):
                was_crowded = True
                break
        for k in range(0, COOLING_STREAK):
            day = T - timedelta(days=k)
            s = _count_window(hits, day, WINDOW_DAYS) - _count_window(hits, day - timedelta(days=SLOPE_DAYS), WINDOW_DAYS)
            if s < 0:
                cooling_streak += 1
            else:
                break

    batches = backfill_batch_dates(hits)
    inputs: dict[str, Any] = {
        "count_90d": count_90d,
        "count_90d_prev30": count_90d_prev,
        "slope_30": slope_30,
        "distinct_days_90d": distinct_days,
        "first_coverage_date": str(first) if first else None,
        "history_obs": history_obs,
        "p80_self": p80,
        "was_crowded_120d": was_crowded,
        "cooling_streak": cooling_streak,
        "falsification_dates": [str(d) for d in fals],
        "backfill_batch_dates": batches,
        "thresholds": {"resonance_sources": TH_RESONANCE_SOURCES, "consensus_sources": TH_CONSENSUS_SOURCES, "consensus_days": TH_CONSENSUS_DAYS},
        "knowledge_cutoff": str(C),
        "hits_used": len(hits),
    }
    if batches:
        reasons.append(f"回填批次日 {batches}：其附近 30 日斜率是采集节奏不是舆论，不可比")

    if fals:
        reasons.append(f"存在证伪事件 {inputs['falsification_dates']}，终态")
        return StageReadout(as_of, STAGE_FALSIFIED, tuple(reasons), inputs)
    if count_90d == 0:
        if was_crowded:
            reasons.append("近 90 日无覆盖，但近 120 日曾到拥挤：从峰回落")
            return StageReadout(as_of, STAGE_COOLING, tuple(reasons), inputs)
        reasons.append("近 90 日无覆盖且无证伪事件：负证据缺失，不断言「无人问津」")
        return StageReadout(as_of, UNVERIFIABLE, tuple(reasons), inputs)
    if _crowded_on(hits, T, p80, history_obs):
        reasons.append(f"count_90d={count_90d} >= {TH_CONSENSUS_SOURCES} 且 {distinct_days} 个报告日 >= {TH_CONSENSUS_DAYS} 且 >= 自身 p80={p80}")
        return StageReadout(as_of, STAGE_CROWDED, tuple(reasons), inputs)
    if was_crowded and cooling_streak >= COOLING_STREAK:
        reasons.append(f"曾拥挤且 30 日斜率连续 {cooling_streak} 日 < 0")
        return StageReadout(as_of, STAGE_COOLING, tuple(reasons), inputs)
    if count_90d >= TH_RESONANCE_SOURCES:
        if history_obs < MIN_HISTORY_OBS:
            reasons.append(f"历史观测 {history_obs} 日 < {MIN_HISTORY_OBS}，不判拥挤，停在扩散")
        reasons.append(f"count_90d={count_90d} >= {TH_RESONANCE_SOURCES}，slope_30={slope_30}")
        return StageReadout(as_of, STAGE_SPREAD, tuple(reasons), inputs)
    reasons.append(f"1 <= count_90d={count_90d} < {TH_RESONANCE_SOURCES}")
    return StageReadout(as_of, STAGE_SPROUT, tuple(reasons), inputs)


def derive_stage_series(
    raw_hits: list[dict[str, Any]],
    days: list[str],
    *,
    falsification_dates: list[str] | tuple[str, ...] = (),
) -> list[StageReadout]:
    """多天读数（每天 C = 当天，即「当日带读」口径）。逐天调用 ``derive_stage``，不共享状态。"""
    return [derive_stage(raw_hits, d, knowledge_cutoff=d, falsification_dates=falsification_dates) for d in days]


# --------------------------------------------------------------------------- #
# 错位标记：题材侧 × 舆论侧（题材词表未统一前双模块映射；G-04 落地后并成一张）
# --------------------------------------------------------------------------- #
THEME_STAGE_COARSE: dict[str, dict[str, str]] = {
    # theme_lifecycle 八阶段（模块 theme_lifecycle.py）
    "theme_lifecycle": {
        "新出现": "early", "旧逻辑唤醒": "early", "升温验证": "mid", "加速定价": "late",
        "高位分歧": "late", "二阶段回流": "late", "衰退观察": "late", "证伪退出": "late",
    },
    # theme_lifecycle_timeline 七段（模块 theme_lifecycle_timeline.py）
    "theme_lifecycle_timeline": {
        "酝酿": "early", "首发": "early", "发酵": "mid", "主升": "late", "分歧": "late", "退潮": "late", "回流": "late",
    },
}
THEME_STAGE_MAPPING_VERSION = "tsc-v0"
_COARSE_ORDER = {"early": 0, "mid": 1, "late": 2}


def dislocation(theme_stage: str | None, opinion_stage: str | None, *, theme_module: str = "theme_lifecycle") -> str:
    """``aligned | opinion_leads | opinion_lags | unverifiable``。两侧都映到三档粗序再比；任一侧缺 → unverifiable。"""
    mapping = THEME_STAGE_COARSE.get(theme_module)
    if mapping is None:
        raise ValueError(f"未知题材模块 {theme_module!r}，可选 {sorted(THEME_STAGE_COARSE)}")
    t = mapping.get(theme_stage or "")
    o = STAGE_COARSE.get(opinion_stage or "")
    if t is None or o is None:
        return UNVERIFIABLE
    if _COARSE_ORDER[o] > _COARSE_ORDER[t]:
        return "opinion_leads"
    if _COARSE_ORDER[o] < _COARSE_ORDER[t]:
        return "opinion_lags"
    return "aligned"
