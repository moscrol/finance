"""Versioned teaching-framework parameter loading.

Parameters are data, not Python constants.  Parsing JSON first and hashing a
canonical representation makes whitespace, key order, and trailing-newline
changes irrelevant while still making every numerical change a new framework
version.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
# v0.2 = slice 1.5：八段词表、按平台参照标注校准的共性区间与转移图（``calibrate-stages`` 的产物，
# 训练期 ≤ 2025-12-31）。v0.1 保留作历史对照，仍可用 ``--params`` 指定。
DEFAULT_PARAMS_PATH = REPO_ROOT / "methodology" / "teaching" / "index_stage_params.v0.2.json"
_HH_MM = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

# These keys are the stable contract consumed by the first teaching slice.
# Builders may add keys in later versions, but a v0.1 file cannot silently
# omit a threshold and fall back to an implementation default.
REQUIRED_KEYS = (
    "framework_version_base",
    "week_ma_col",
    "deviation_bands",
    "volume_level",
    "shrink_day",
    "shrink_streak_min",
    "mainline_amount_stepping_up_days",
    "mainline_share_basis",
    "mainline_definitions",
    "instant_seal_time",
    "rebound_window_days",
    "high_turnover_ratio",
    "amount_unit_policy",
    "top100_n",
    "breadth_min_stocks",
    "index_range_windows",
    "breakout_confirm_days",
    "deviation_streak_min",
    "surge_in_trend",
    "leader_top",
    "transition_policy",
    "ambiguity_memory",
    "min_n",
    # 第十一段「升级 2.0 = 进一步放量 + 指数进一步走强」：新高窗口（写出的候选）、进入谓词用的那一个、双量日环比门槛。
    "index_new_high_windows",
    "upgrade_new_high_window",
    "double_volume_dod_pct",
    # 第十二段「定义不精确、结合特征值来看」：左底向下进入的持续天数与量能口径。
    "left_down_entry",
    # 第九 / 十段：区间涨幅高标链——窗口（平台梯队高度）、取前几（「取前 10」）、配对时看近旁几名。
    "range_leader_windows",
    "range_leader_top",
    "range_leader_context",
    # 第十三段「旧王朝覆灭 → 亏钱效应 → 分离确认 → 新王朝」：王朝取前几（第十段「取前 10」）、读数用的宽队列、
    # 「相对分离」的收益分位门槛、「新高分离」的回看天数。
    "dynasty_top",
    "dynasty_cohort",
    "separation_percentile",
    "separation_new_high_window",
)

# slice 1.5 第二遍（用户「继续按照最优推进」）：阶段不能无转点地跳到不相邻的段（词表「从什么
# 来源状态演变而来」）；歧义日不抹掉来源状态（spec §9.9 的记忆规则）。只实现这一种读法，
# 记在参数里让版本随之变。
SUPPORTED_TRANSITION_POLICY = "entry_or_reachable"
SUPPORTED_AMBIGUITY_MEMORY = "last_valid_stage"

# 创始人 2026-09-07 第八段：「趋势中放量不代表就见顶，也可能是行情升级……这个放量是个因子，
# 有好有坏」。The only implemented role: a written view that scores for no stage.  Recorded
# here so that retiring it as 见顶 evidence shows up in the parameter hash.
SUPPORTED_SURGE_IN_TREND = {"role": "view"}

# 创始人 2026-09-07 第六段：「最高标不要求唯一，可以并列多个」。The only implemented
# reading: tied leaders form one group, and a break day is one where no member of
# yesterday's group is still sealed.  Any other value fails closed so the choice is
# visible in the parameter hash rather than buried in code.
SUPPORTED_LEADER_TOP = {"tie_policy": "group", "break_rule": "all_members_off_table"}


def canonical_json(value: Any) -> str:
    """Return stable JSON suitable for hashing and receipt storage."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_hh_mm(value: Any, path: str) -> None:
    if isinstance(value, str) and ("time" in path.lower() or path.lower().endswith("_at")):
        if not _HH_MM.fullmatch(value):
            raise ValueError(f"{path} 必须是 HH:MM（得到 {value!r}）")
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_hh_mm(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            _validate_hh_mm(item, f"{path}[{idx}]")


def _validate_stage_calibration(params: dict[str, Any]) -> None:
    """``stage_bands`` / ``transition_graph`` are optional (v0.1 files have none) but must be well-formed when present.

    Slice 1.5 (用户 09-07 第十段)：共性区间与转移图由 ``calibrate-stages`` 从平台参照标注算出
    写进参数文件；它们进哈希，改一次 = 新版本。
    """
    from .stage_rules import BAND_VIEWS, STAGES  # local import: stage_rules must not depend on params

    views = {view for view, _ in BAND_VIEWS}
    bands = params.get("stage_bands")
    if bands is not None:
        if not isinstance(bands, dict) or any(stage not in STAGES for stage in bands):
            raise ValueError(f"stage_bands 的键必须是八段之一 {STAGES}")
        for stage, per_view in bands.items():
            if not isinstance(per_view, dict):
                raise ValueError(f"stage_bands[{stage}] 必须是 {{视角: [lo, hi]}}")
            for view, band in per_view.items():
                if view not in views:
                    raise ValueError(f"stage_bands[{stage}] 含未知视角 {view!r}；可用 {sorted(views)}")
                if (
                    not isinstance(band, list) or len(band) != 2
                    or any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in band)
                    or band[0] > band[1]
                ):
                    raise ValueError(f"stage_bands[{stage}][{view}] 必须是 [lo, hi] 且 lo ≤ hi")
    graph = params.get("transition_graph")
    if graph is not None:
        if not isinstance(graph, dict) or any(stage not in STAGES for stage in graph):
            raise ValueError("transition_graph 的键必须是八段之一")
        for stage, targets in graph.items():
            if not isinstance(targets, list) or any(t not in STAGES for t in targets):
                raise ValueError(f"transition_graph[{stage}] 必须是八段名的数组")
    if (bands is None) != (graph is None):
        raise ValueError("stage_bands 与 transition_graph 必须同时给出或同时缺省（同一次校准的产物）")


def validate_params(params: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ValueError("参数文件根必须是 JSON object")
    missing = [key for key in REQUIRED_KEYS if key not in params]
    if missing:
        raise ValueError(f"参数文件缺少必需字段: {', '.join(missing)}")
    version = params["framework_version_base"]
    if not isinstance(version, str) or not version.startswith("tf-v"):
        raise ValueError("framework_version_base 必须是形如 tf-v0.1 的字符串")
    if not isinstance(params["rebound_window_days"], int) or params["rebound_window_days"] <= 0:
        raise ValueError("rebound_window_days 必须是正整数")
    if not isinstance(params["top100_n"], int) or params["top100_n"] <= 0:
        raise ValueError("top100_n 必须是正整数")
    if not isinstance(params["mainline_definitions"], list) or not params["mainline_definitions"]:
        raise ValueError("mainline_definitions 必须是非空数组")
    if params["high_turnover_ratio"] is not None and (
        not isinstance(params["high_turnover_ratio"], (int, float)) or params["high_turnover_ratio"] <= 0
    ):
        raise ValueError("high_turnover_ratio 必须是正数或 null")
    if not isinstance(params["shrink_day"], dict) or "basis" not in params["shrink_day"]:
        raise ValueError("shrink_day 必须包含 basis")
    # 创始人 2026-09-07 第十段：「20 日均量，量能比吧」——量能三档的尺子是 当日成交额 / 20 日
    # 均量 × 100（复盘会同一口径），不再是环比。100–120 温和放量、> 120 暴量。
    level = params["volume_level"]
    if not isinstance(level, dict) or level.get("basis") != "amount_vs_ma20_pct":
        raise ValueError("volume_level.basis 目前只支持 amount_vs_ma20_pct（当日成交额 / 20 日均量 × 100）")
    surge_from = level.get("surge_from_pct")
    if not isinstance(surge_from, (int, float)) or isinstance(surge_from, bool) or surge_from <= 0:
        raise ValueError("volume_level.surge_from_pct 必须是正数（量能比百分数，暴量下界）")
    lower = level.get("moderate_from_pct")
    if not isinstance(lower, (int, float)) or isinstance(lower, bool) or lower >= surge_from:
        raise ValueError("volume_level.moderate_from_pct 必须是小于 surge_from_pct 的数（温和放量下界）")
    if not isinstance(params["breadth_min_stocks"], int) or params["breadth_min_stocks"] <= 0:
        raise ValueError("breadth_min_stocks 必须是正整数")
    windows = params["index_range_windows"]
    if (
        not isinstance(windows, list)
        or not windows
        or any(not isinstance(n, int) or isinstance(n, bool) or n <= 0 for n in windows)
        or len(set(windows)) != len(windows)
    ):
        raise ValueError("index_range_windows 必须是互不重复的正整数数组（区间涨幅 / 振幅 / 偏离度变化的窗口天数）")
    high_windows = params["index_new_high_windows"]
    if (
        not isinstance(high_windows, list)
        or not high_windows
        or any(not isinstance(n, int) or isinstance(n, bool) or n <= 0 for n in high_windows)
        or len(set(high_windows)) != len(high_windows)
    ):
        raise ValueError("index_new_high_windows 必须是互不重复的正整数数组（指数收盘新高的回看天数）")
    upgrade_window = params["upgrade_new_high_window"]
    if not isinstance(upgrade_window, int) or isinstance(upgrade_window, bool) or upgrade_window not in high_windows:
        raise ValueError("upgrade_new_high_window 必须是 index_new_high_windows 里的一个窗口（2.0 进入谓词用哪一个新高）")
    dod = params["double_volume_dod_pct"]
    if not isinstance(dod, (int, float)) or isinstance(dod, bool) or dod <= 0:
        raise ValueError("double_volume_dod_pct 必须是正数（双量日的成交额环比门槛，每日复盘口径 10）")
    rl_windows = params["range_leader_windows"]
    if (
        not isinstance(rl_windows, list)
        or not rl_windows
        or any(not isinstance(n, int) or isinstance(n, bool) or n <= 0 for n in rl_windows)
        or len(set(rl_windows)) != len(rl_windows)
    ):
        raise ValueError("range_leader_windows 必须是互不重复的正整数数组（区间涨幅高标的窗口天数，平台梯队高度 20 / 60 / 90 / 120）")
    rl_top, rl_context = params["range_leader_top"], params["range_leader_context"]
    if not isinstance(rl_top, int) or isinstance(rl_top, bool) or rl_top <= 0:
        raise ValueError("range_leader_top 必须是正整数（创始人第十段「取前 10」）")
    if not isinstance(rl_context, int) or isinstance(rl_context, bool) or rl_context < rl_top:
        raise ValueError("range_leader_context 必须是 ≥ range_leader_top 的整数（判断递进 / 突入时看的近旁名次）")
    dyn_top, dyn_cohort = params["dynasty_top"], params["dynasty_cohort"]
    if not isinstance(dyn_top, int) or isinstance(dyn_top, bool) or dyn_top <= 0:
        raise ValueError("dynasty_top 必须是正整数（一波里区间涨幅前几算王朝，第十段「取前 10」）")
    if not isinstance(dyn_cohort, int) or isinstance(dyn_cohort, bool) or dyn_cohort < dyn_top:
        raise ValueError("dynasty_cohort 必须是 ≥ dynasty_top 的整数（读数用的宽队列）")
    sep_pct = params["separation_percentile"]
    if not isinstance(sep_pct, (int, float)) or isinstance(sep_pct, bool) or not (0 < float(sep_pct) < 1):
        raise ValueError("separation_percentile 必须在 (0, 1) 内（覆灭窗里收益分位 ≥ 此值算「相对分离」）")
    sep_win = params["separation_new_high_window"]
    if not isinstance(sep_win, int) or isinstance(sep_win, bool) or sep_win <= 0:
        raise ValueError("separation_new_high_window 必须是正整数（覆灭窗内创几日新高算「新高分离」）")
    from .stage_rules import LEFT_DOWN_VOLUME_RULES  # local import: stage_rules must not depend on params

    entry = params["left_down_entry"]
    if (
        not isinstance(entry, dict)
        or not isinstance(entry.get("persist_days"), int) or isinstance(entry.get("persist_days"), bool) or entry["persist_days"] < 1
        or entry.get("volume") not in LEFT_DOWN_VOLUME_RULES
        or not isinstance(entry.get("gap_through_ma_day1", False), bool)
        or set(entry) - {"persist_days", "volume", "gap_through_ma_day1"}
    ):
        raise ValueError(
            f"left_down_entry 必须是 {{persist_days: ≥1 的整数, volume: {LEFT_DOWN_VOLUME_RULES}, gap_through_ma_day1?: bool}}"
            "（gap_through_ma_day1 = 首次下穿当天开盘已在周均之下时立刻算进入，第十三段「跳空低开跌破」的可选读法）"
        )
    if params["leader_top"] != SUPPORTED_LEADER_TOP:
        raise ValueError(f"leader_top 目前只支持 {SUPPORTED_LEADER_TOP}（最高标并列成组、全员断板才算断板）")
    if params["surge_in_trend"] != SUPPORTED_SURGE_IN_TREND:
        raise ValueError(f"surge_in_trend 目前只支持 {SUPPORTED_SURGE_IN_TREND}（趋势中放量只作视角，不作任何一段的证据）")
    # 可选旋钮：靠区间证据切换阶段所需的领先分数（1 = 无滞回）。2026-09-07 在训练期未通过
    # （k=2/3 训练期一致率 32% → 22–24%），默认 1；等全量参照历史再校准。
    margin = params.get("stage_switch_margin", 1)
    if not isinstance(margin, int) or isinstance(margin, bool) or margin < 1:
        raise ValueError("stage_switch_margin 必须是 ≥ 1 的整数（1 = 无滞回）")
    if params["transition_policy"] != SUPPORTED_TRANSITION_POLICY:
        raise ValueError(f"transition_policy 目前只支持 {SUPPORTED_TRANSITION_POLICY!r}（不可达的段当日只有进入证据才能胜出）")
    if params["ambiguity_memory"] != SUPPORTED_AMBIGUITY_MEMORY:
        raise ValueError(f"ambiguity_memory 目前只支持 {SUPPORTED_AMBIGUITY_MEMORY!r}（歧义日保留最近有效阶段作来源；缺口日才断链）")
    # 创始人 2026-09-07 第七段：「上穿要配合放量……或者上穿后三天内放量」「三天吧」（持续走高 /
    # 逐渐走低 / 回归周均 的连续天数门槛）。
    for key in ("breakout_confirm_days", "deviation_streak_min"):
        if not isinstance(params[key], int) or isinstance(params[key], bool) or params[key] <= 0:
            raise ValueError(f"{key} 必须是正整数（交易日数）")
    _validate_stage_calibration(params)
    _validate_hh_mm(params["instant_seal_time"], "instant_seal_time")
    return params


def load_params(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the parameter document from disk."""

    source = Path(path).expanduser() if path else DEFAULT_PARAMS_PATH
    if not source.is_file():
        raise FileNotFoundError(f"教学框架参数文件不存在: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"参数文件不是有效 JSON: {source}: {exc}") from exc
    return validate_params(data)


def parameter_hash(params_or_path: dict[str, Any] | str | Path | None = None) -> str:
    """SHA-256 of canonical parameter JSON (full hex digest)."""

    params = (
        load_params(params_or_path)
        if params_or_path is None or isinstance(params_or_path, (str, Path))
        else validate_params(params_or_path)
    )
    return hashlib.sha256(canonical_json(params).encode("utf-8")).hexdigest()


def framework_version(params_or_path: dict[str, Any] | str | Path | None = None) -> str:
    """Return the framework namespace used in teaching rows and receipts."""

    params = (
        load_params(params_or_path)
        if params_or_path is None or isinstance(params_or_path, (str, Path))
        else validate_params(params_or_path)
    )
    return f"{params['framework_version_base']}+{parameter_hash(params)[:8]}"
