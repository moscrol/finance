"""方法飞轮接线（能力升级任务包 07）：把冻结的方法验证收据接到日常入口与下一次问题。

三件事，全部只读收据、确定性派生，**不存第二份状态**：

1. **立场（standing）**：从 protocol / history / capture / recheck 记录算出方法此刻的位置——
   历史演练读数、真实前向待验对象、每次回检的分类、下一次问题里该 adopt / downgrade /
   exclude / candidate。与 ``methodology_backtest.lifecycle`` 同一哲学：状态是收据算出来的，
   没有收据就没有状态。106MB 的历史原件不在消费路径上读：CLI 写完收据就刷新一份**按输入
   指纹命名**的摘要 ``standing/<fingerprint>.json``（指纹 = 全部收据文件名 + 协议摘要 + 本模块
   版本的 SHA-256）。消费方按目录列表算指纹取摘要，指纹不符只报「摘要过期」。
2. **自然语言 → 固定方法**：关键词匹配（双红）。匹不上的方法文本存 ``candidates/<sha>.json``
   草稿，不编译；通用编译不在本刀。
3. **观察对象登记**：capture 时把有信号且阶段适用的 D0 登记成 checkpoint（``object_type=
   method_observation``、``metric.type=method_validation``）；到期由夜间 ``checkpoint recheck``
   通过 resolver 走原协议 recheck，分类回写 verdict。

分类六选一：``supported`` / ``method_error`` / ``data_insufficient`` / ``environment_change`` /
``no_signal`` / ``stage_not_applicable``，未到期为 ``pending``；执行偏离（回检早于到期、信号日
漏登记）单独标记。所有读数保持 ``research_only``，不出胜率、不构成买卖建议。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from intelligence.services import checkpoints

from .protocol import (
    ARMS,
    BOUNDARY,
    RULE_NAME,
    canonical_bytes,
    clock_now,
    digest,
    iso_date,
)
from .store import (
    list_records,
    list_studies,
    load_protocol,
    publish_json,
    read_record,
    replace_json,
    write_record,
)
from .study import compare, read_market_stages, read_outcomes, validate_capture

FLYWHEEL_VERSION = "standing-v1"
METHOD_ID = "dual_red_streak3_continuation.v1"
METHOD_TITLE = "连续三日严格双红（主升 / 反弹）板块的五日持续性"
HORIZON = 5
CATEGORY = "方法验证·双红持续性"
SOURCE = "method_validation"
OBJECT_TYPE = "method_observation"
METRIC_TYPE = "method_validation"
THEMES = ("双红", "连续双红", "板块持续性")
QUERY_TERMS = ("双红", "dual_red", "dual red")
CLASSIFICATIONS = (
    "supported",
    "method_error",
    "data_insufficient",
    "environment_change",
    "no_signal",
    "stage_not_applicable",
    "pending",
)
CLASSIFICATION_CN = {
    "supported": "支持假设",
    "method_error": "方法错误（假设未成立）",
    "data_insufficient": "数据不足",
    "environment_change": "环境变化",
    "no_signal": "没有信号",
    "stage_not_applicable": "非适用阶段",
    "pending": "未到期",
}
DECISIONS = ("adopt", "downgrade", "exclude", "candidate")
DECISION_CN = {
    "adopt": "采用（仅作观察透镜）",
    "downgrade": "降低权重（仅作观察提示）",
    "exclude": "排除",
    "candidate": "候选（样本不足）",
}
HISTORY_LABEL = "历史演练（重建标签，非实时前瞻）"
FORWARD_LABEL = "真实前向（收盘后提前登记，到期回检）"
DISCLAIMER = "研究读数：不出胜率、不构成买卖建议；样本不足时只描述不判定。"
_PACKAGE = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE.parents[2]


# --------------------------------------------------------------------------- #
# 通用
# --------------------------------------------------------------------------- #
def evaluator_code_sha256() -> str:
    """本次实际执行的应用源码指纹（包内 *.py + 分析师 CLI），不能用 Git HEAD 冒充未提交代码。"""
    files = sorted(_PACKAGE.glob("*.py"))
    cli = _REPO_ROOT / "scripts" / "method_validation.py"
    if cli.is_file():
        files.append(cli)
    hasher = hashlib.sha256()
    for path in files:
        hasher.update(str(path.relative_to(_REPO_ROOT)).encode())
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def _diffs(day: dict) -> dict:
    means = day.get("means") or {}
    s3, dr, un = (means.get(name) for name in ARMS[::-1])  # streak3, dual_red, universe
    if not all(_finite(v) for v in (s3, dr, un)):
        return {"streak3_minus_dual_red_pp": None, "streak3_minus_universe_pp": None}
    return {
        "streak3_minus_dual_red_pp": s3 - dr,
        "streak3_minus_universe_pp": s3 - un,
    }


def classify_day(day: dict, applicable_stages: list) -> str:
    """把 ``compare()`` 的一条日期读数归到六类之一（不把它们统称失效）。"""
    if day.get("status") == "paired":
        diffs = _diffs(day)
        values = list(diffs.values())
        if all(_finite(v) for v in values) and all(v > 0 for v in values):
            return "supported"
        return "method_error"
    reasons = set(day.get("reasons") or [])
    if "no_sector_labels" in reasons or "missing_calendar" in reasons:
        return "data_insufficient"
    stage = day.get("stage")
    if "stage_not_applicable" in reasons or (
        stage is not None and stage not in applicable_stages
    ):
        return "stage_not_applicable"
    if "no_event" in reasons:
        return "no_signal"
    if "pending" in reasons:
        return "pending"
    return "data_insufficient"


def classify_forward(day: dict, stage_path: dict, protocol: dict) -> tuple[str, list]:
    """前向回检分类 + 环境标记。

    ``stage_path`` 是 D+1..D+5 的 market_stage；任一日离开协议适用集合即 ``environment_change``：
    方法没有拿到它的环境，这类日子既不算方法错也不算支持。
    """
    primary = classify_day(day, protocol["market_stages"])
    flags: list[str] = []
    window = [stage for _, stage in sorted(stage_path.items())]
    if primary in ("supported", "method_error"):
        if not window or len(window) < HORIZON:
            flags.append("environment_unknown")
        elif any(stage not in protocol["market_stages"] for stage in window):
            primary = "environment_change"
    return primary, flags


# --------------------------------------------------------------------------- #
# 收据摘要
# --------------------------------------------------------------------------- #
def _counts(day: dict) -> dict:
    arms = day.get("arms") or {}
    return {name: len(arms.get(name) or []) for name in ARMS}


def summarize_history(protocol: dict, payload: dict, *, record_sha: str) -> dict:
    """把一份 history 收据压成不含成员明细的摘要（信号日逐日保留原因）。"""
    comparison = payload["comparison"]
    features = payload["features"]
    stages = protocol["market_stages"]
    daily = comparison["daily"]
    applicable = [day for day in daily if day.get("stage") in stages]
    signal_days = [day for day in applicable if (day.get("arms") or {}).get("streak3")]
    table = []
    categories: Counter = Counter()
    for day in signal_days:
        members = day.get("members") or []
        unknown = sum(
            1
            for member in members
            if any(str(r).startswith("unknown_") for r in member.get("exclusion_reasons") or [])
        )
        missing = sorted(
            member["entity_id"]
            for member in members
            if member.get("outcome_status") == "missing"
        )
        classification = classify_day(day, stages)
        categories[classification] += 1
        table.append(
            {
                "trade_date": day["trade_date"],
                "stage": day.get("stage"),
                "counts": _counts(day),
                "status": day.get("status"),
                "reasons": list(day.get("reasons") or []),
                "classification": classification,
                "unknown_label_members": unknown,
                "missing_members": missing,
                "diffs": _diffs(day) if day.get("status") == "paired" else None,
            }
        )
    labels_meta = features["metadata"]["labels"]
    summary = comparison["summary"]
    return {
        "label": HISTORY_LABEL,
        "record_sha256": record_sha,
        "evaluator_code_sha256": payload.get("evaluator_code_sha256"),
        "window": dict(protocol["history"]),
        "calendar_dates": comparison["coverage"]["calendar_dates"],
        "applicable_days": len(applicable),
        "signal_days": len(signal_days),
        "paired_dates": summary["paired_dates"],
        "means": summary["means"],
        "streak3_minus_dual_red_pp": summary["streak3_minus_dual_red_pp"],
        "streak3_minus_universe_pp": summary["streak3_minus_universe_pp"],
        "coverage_exclusions": comparison["coverage"]["exclusions"],
        "signal_day_categories": dict(categories),
        "signal_day_table": table,
        "labels": {
            key: labels_meta.get(key)
            for key in ("label_version", "source_max_trade_date", "computed_at")
        },
        "point_in_time": features["metadata"].get("point_in_time"),
        "limitations": list(comparison.get("limitations") or []),
    }


def _capture_summary(protocol: dict, record: dict, path: Path) -> dict:
    features = record["payload"]["features"]
    rows = features["rows"]
    stage = next((row.get("stage") for row in rows if row.get("stage") is not None), None)
    counts = {name: sum(1 for row in rows if name in row["arms"]) for name in ARMS}
    unknown = sum(
        1
        for row in rows
        if any(str(r).startswith("unknown_") for r in row.get("exclusion_reasons") or [])
    )
    applicable = stage in protocol["market_stages"]
    return {
        "trade_date": features["start"],
        "captured_at": record["payload"].get("captured_at"),
        "observation_sha256": record["content_sha256"],
        "observation_path": str(path),
        "stage": stage,
        "stage_applicable": applicable,
        "counts": counts,
        "unknown_label_members": unknown,
        "has_signal": bool(counts["streak3"]) and applicable,
        "streak3_members": sorted(row["entity_id"] for row in rows if "streak3" in row["arms"]),
        "due": observation_due(features["start"]),
        "labels": {
            key: features["metadata"]["labels"].get(key)
            for key in ("label_version", "source_max_trade_date", "computed_at")
        },
    }


def _recheck_summary(protocol: dict, record: dict, path: Path) -> dict:
    payload = record["payload"]
    day = payload["comparison"]["daily"][0]
    meta = payload.get("flywheel") or {}
    classification = meta.get("classification")
    flags = list(meta.get("flags") or [])
    if classification not in CLASSIFICATIONS:
        classification = classify_day(day, protocol["market_stages"])
        if classification in ("supported", "method_error"):
            flags.append("environment_unknown")
    return {
        "trade_date": payload["features"]["start"],
        "observation_sha256": payload.get("observation_sha256"),
        "record_sha256": record["content_sha256"],
        "record_path": str(path),
        "recorded_day": path.parent.name,
        "classification": classification,
        "flags": flags,
        "status": day.get("status"),
        "reasons": list(day.get("reasons") or []),
        "means": day.get("means"),
        "diffs": _diffs(day) if day.get("status") == "paired" else None,
        "stage": day.get("stage"),
        "stage_path": meta.get("stage_path"),
        "outcomes_watermark": payload["outcomes"]["metadata"]["outcomes"].get(
            "source_max_trade_date"
        ),
    }


# --------------------------------------------------------------------------- #
# 立场派生 / 摘要缓存
# --------------------------------------------------------------------------- #
def fingerprint(study_dir) -> str:
    """全部收据文件名 + 协议摘要 + 本模块版本 → 输入指纹（目录列表即可算，不读正文）。"""
    directory = Path(study_dir)
    protocol = load_protocol(directory)
    names = sorted(
        f"{kind}/{path.parent.name}/{path.name}"
        for kind in ("history", "capture", "recheck")
        for path in list_records(directory, kind)
    )
    return digest(
        {
            "version": FLYWHEEL_VERSION,
            "protocol_id": protocol["protocol_id"],
            "records": names,
        }
    )


def _latest_history(directory: Path) -> Path | None:
    records = list_records(directory, "history")
    return records[-1] if records else None


def derive_standing(study_dir, *, now: datetime | None = None) -> dict:
    """读全部收据算出立场（会读大文件；消费方走 ``load_standing``）。"""
    directory = Path(study_dir)
    protocol = load_protocol(directory)
    current = clock_now(now)
    history = None
    latest = _latest_history(directory)
    if latest is not None:
        record = read_record(latest)
        history = summarize_history(protocol, record["payload"], record_sha=record["content_sha256"])
    captures = [
        _capture_summary(protocol, read_record(path), path)
        for path in list_records(directory, "capture")
    ]
    rechecks = [
        _recheck_summary(protocol, read_record(path), path)
        for path in list_records(directory, "recheck")
    ]
    latest_by_observation: dict[str, dict] = {}
    for item in rechecks:
        key = item["observation_sha256"] or item["trade_date"]
        prev = latest_by_observation.get(key)
        if prev is None or (item["recorded_day"], item["record_sha256"]) > (
            prev["recorded_day"],
            prev["record_sha256"],
        ):
            latest_by_observation[key] = item
    pending, settled = [], []
    for capture in captures:
        latest_recheck = latest_by_observation.get(capture["observation_sha256"])
        entry = {**capture, "recheck": latest_recheck}
        if latest_recheck is None or latest_recheck["classification"] == "pending":
            if capture["has_signal"]:
                entry["waiting_for"] = (
                    f"{capture['trade_date']} 之后第 {HORIZON} 个交易日收盘、旁路库水位到位后回检"
                )
                pending.append(entry)
            else:
                entry["classification"] = (
                    "stage_not_applicable" if not capture["stage_applicable"] else "no_signal"
                )
                settled.append(entry)
        else:
            entry["classification"] = latest_recheck["classification"]
            settled.append(entry)
    counts = Counter(item["classification"] for item in settled)
    deviations = []
    for item in rechecks:
        if item["classification"] == "pending":
            deviations.append(
                {
                    "kind": "recheck_before_maturity",
                    "trade_date": item["trade_date"],
                    "recorded_day": item["recorded_day"],
                    "note": "回检早于到期，只留 pending 读数，不算结果",
                }
            )
    method_card = protocol["method_card"]
    standing = {
        "schema_version": 1,
        "flywheel_version": FLYWHEEL_VERSION,
        "fingerprint": fingerprint(directory),
        "generated_at": current.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "study_dir": str(directory),
        "method": {
            "id": METHOD_ID,
            "title": METHOD_TITLE,
            "rule_name": RULE_NAME,
            "protocol_id": protocol["protocol_id"],
            "hypothesis": method_card["hypothesis"],
            "applicable_stages": list(protocol["market_stages"]),
            "observation_order": list(method_card["observation_order"]),
            "invalidation_conditions": list(method_card["invalidation_conditions"]),
            "source": method_card["source"],
            "forward_start": protocol["forward_start"],
            "history_window": dict(protocol["history"]),
            "label_version": protocol["label_version"],
        },
        "boundary": dict(BOUNDARY),
        "history_rehearsal": history,
        "forward": {
            "label": FORWARD_LABEL,
            "captures": captures,
            "pending": pending,
            "settled": settled,
            "counts": dict(counts),
            "first_real_cycle_completed": any(
                item["classification"] in ("supported", "method_error", "environment_change")
                for item in settled
            ),
        },
        "execution_deviations": deviations,
    }
    standing["selection"] = decide(standing)
    canonical_bytes(standing)
    return standing


def refresh_standing(study_dir, *, now: datetime | None = None) -> Path:
    """派生立场并以输入指纹为名发布摘要；同输入同内容（generated_at 除外，不参与指纹）。"""
    standing = derive_standing(study_dir, now=now)
    # 摘要是按输入指纹命名的缓存：同指纹重算只会差 generated_at，原地替换而不是拒绝。
    return replace_json(
        Path(study_dir) / "standing" / f"{standing['fingerprint']}.json", standing
    )


def load_standing(study_dir) -> tuple[dict | None, bool]:
    """按当前指纹取摘要；没有匹配的返回最近一份并标 stale；一份都没有返回 (None, False)。"""
    directory = Path(study_dir)
    parent = directory / "standing"
    if not parent.is_dir():
        return None, False
    current = fingerprint(directory)
    exact = parent / f"{current}.json"
    if exact.is_file() and not exact.is_symlink():
        standing = json.loads(exact.read_text(encoding="utf-8"))
        standing["stale"] = False
        return standing, True
    candidates = sorted(
        (path for path in parent.glob("*.json") if not path.is_symlink()),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        return None, False
    standing = json.loads(candidates[-1].read_text(encoding="utf-8"))
    standing["stale"] = True
    standing["stale_reason"] = "收据有更新，立场摘要未刷新：运行 method_validation.py status --refresh"
    return standing, False


# --------------------------------------------------------------------------- #
# 选择梯子
# --------------------------------------------------------------------------- #
def decide(standing: dict, *, current_stage: str | None = None) -> dict:
    """下一次问题里该怎么用这条方法。确定性梯子，不是统计结论。"""
    history = standing.get("history_rehearsal") or {}
    forward = standing.get("forward") or {}
    counts = forward.get("counts") or {}
    reasons: list[str] = []
    stages = standing["method"]["applicable_stages"]
    hist_for = hist_against = 0
    paired = int(history.get("paired_dates") or 0)
    d1, d2 = history.get("streak3_minus_dual_red_pp"), history.get("streak3_minus_universe_pp")
    if paired and _finite(d1) and _finite(d2):
        if d1 > 0 and d2 > 0:
            hist_for = 1
            reasons.append(
                f"历史演练 {paired} 个共同日：连续组相对当日双红 {d1:+.2f}pp、相对总体 {d2:+.2f}pp，方向支持假设"
            )
        else:
            hist_against = 1
            reasons.append(
                f"历史演练 {paired} 个共同日：连续组相对当日双红 {d1:+.2f}pp、相对总体 {d2:+.2f}pp，不支持「连续更强」"
            )
    elif history:
        reasons.append("历史演练没有可配对的共同日，方向无法判断")
    else:
        reasons.append("尚无历史演练收据")
    supported = int(counts.get("supported") or 0)
    errors = int(counts.get("method_error") or 0)
    env = int(counts.get("environment_change") or 0)
    insufficient = int(counts.get("data_insufficient") or 0)
    if supported or errors:
        reasons.append(f"真实前向已结算：支持 {supported} 次、方法错误 {errors} 次")
    if env:
        reasons.append(f"真实前向 {env} 次遇到环境变化（观察窗内阶段离开适用集合），不计入正反")
    if insufficient:
        reasons.append(f"真实前向 {insufficient} 次数据不足，不计入正反")
    evidence_for = hist_for + supported
    evidence_against = hist_against + errors
    samples = paired + supported + errors
    if current_stage is not None and current_stage not in stages:
        decision = "exclude"
        reasons.insert(0, f"当前阶段「{current_stage}」不在适用集合 {stages}：环境不适用")
    elif evidence_against >= 2 and evidence_for == 0:
        decision = "exclude"
        reasons.append("反证累计两次以上且无支持：排除，直到新窗口重新验证")
    elif evidence_against > evidence_for:
        decision = "downgrade"
        reasons.append("反证多于支持：只作观察提示，不据此给板块排序")
    elif evidence_for > evidence_against and samples >= 3:
        decision = "adopt"
        reasons.append("支持多于反证且样本≥3：可作观察透镜，仍不出胜率")
    else:
        decision = "candidate"
        reasons.append("样本不足以分辨方向：保留为候选，只描述不判定")
    if paired < 20:
        reasons.append(f"共同日 {paired} < 协议 min_n 20：不出胜率")
    return {
        "decision": decision,
        "decision_cn": DECISION_CN[decision],
        "evidence_for": evidence_for,
        "evidence_against": evidence_against,
        "samples": samples,
        "current_stage": current_stage,
        "reasons": reasons,
        "disclaimer": DISCLAIMER,
    }


# --------------------------------------------------------------------------- #
# 渲染（给 [M] 块 / memory_lookup 证据 / 日报）
# --------------------------------------------------------------------------- #
def _fmt_pp(value: Any) -> str:
    return f"{value:+.2f}pp" if _finite(value) else "不可计算"


def render_method_lines(
    standing: dict,
    *,
    current_stage: str | None = None,
    today: str | None = None,
) -> list[str]:
    method = standing["method"]
    selection = decide(standing, current_stage=current_stage) if current_stage else standing["selection"]
    history = standing.get("history_rehearsal")
    forward = standing.get("forward") or {}
    lines = [
        f"方法「{method['title']}」（{method['id']}，协议 {method['protocol_id'][:8]}…）：{method['hypothesis']}",
        f"适用阶段 {'/'.join(method['applicable_stages'])}；观察顺序 {' → '.join(method['observation_order'])}",
    ]
    if history:
        cats = history.get("signal_day_categories") or {}
        cat_text = "、".join(
            f"{CLASSIFICATION_CN.get(k, k)} {v} 天" for k, v in sorted(cats.items())
        )
        lines.append(
            f"[{HISTORY_LABEL}] {history['window']['start']}→{history['window']['end']}："
            f"适用阶段 {history['applicable_days']} 天，信号 {history['signal_days']} 天，可配对 {history['paired_dates']} 天；"
            f"连续组相对当日双红 {_fmt_pp(history['streak3_minus_dual_red_pp'])}、相对总体 {_fmt_pp(history['streak3_minus_universe_pp'])}"
        )
        if cat_text:
            lines.append(f"[历史演练] 信号日逐日：{cat_text}（不统称失效）")
    else:
        lines.append(f"[{HISTORY_LABEL}] 尚无收据")
    pending = forward.get("pending") or []
    counts = forward.get("counts") or {}
    if pending:
        waits = "；".join(
            f"{item['trade_date']} 连续组 {item['counts']['streak3']} 个板块，等 {item['due']} 前后回检"
            for item in pending[:3]
        )
        lines.append(f"[{FORWARD_LABEL}] 待验 {len(pending)} 个：{waits}")
    if counts:
        lines.append(
            "[真实前向] 已结算："
            + "、".join(f"{CLASSIFICATION_CN.get(k, k)} {v}" for k, v in sorted(counts.items()))
        )
    if not pending and not counts:
        lines.append(
            f"[{FORWARD_LABEL}] 起点 {method['forward_start']}，尚无真实观察；上面的读数全部来自历史演练"
        )
    if today:
        today_capture = next(
            (item for item in forward.get("captures") or [] if item["trade_date"] == today),
            None,
        )
        if today_capture is None:
            lines.append(f"今日（{today}）尚未登记观察")
        elif today_capture["has_signal"]:
            lines.append(
                f"今日（{today}）信号：连续组 {today_capture['counts']['streak3']} 个板块（阶段 {today_capture['stage']}）"
            )
        else:
            lines.append(
                f"今日（{today}）无信号（阶段 {today_capture['stage']}，连续组 {today_capture['counts']['streak3']} 个）"
            )
    lines.append(f"本次选择：{selection['decision_cn']}——" + "；".join(selection["reasons"]))
    if standing.get("stale"):
        lines.append(f"注意：{standing.get('stale_reason')}")
    lines.append(DISCLAIMER)
    return lines


# --------------------------------------------------------------------------- #
# 自然语言 → 方法；候选草稿
# --------------------------------------------------------------------------- #
def match_query(query: str) -> dict | None:
    text = str(query or "").lower()
    hits = [term for term in QUERY_TERMS if term in text]
    if not hits:
        return None
    return {"method_id": METHOD_ID, "title": METHOD_TITLE, "terms": hits}


def resolve_root(user: str | None = None, users_root: str | Path | None = None) -> Path:
    if users_root is not None:
        return Path(users_root).expanduser() / "method_validation"
    from intelligence import userspace

    return userspace.user_space(user).root / "method_validation"


def recall_for_query(
    query: str,
    *,
    user: str | None = None,
    users_root: str | Path | None = None,
    current_stage: str | None = None,
    today: str | None = None,
) -> list[dict]:
    """问题命中方法时返回该用户全部实验的立场读数（每实验一条），否则 []。

    只读该用户目录下的摘要：别的用户、别的目录的收据不会进来。
    """
    match = match_query(query)
    if match is None:
        return []
    root = resolve_root(user, users_root)
    out = []
    for study_dir in list_studies(root):
        try:
            standing, _fresh = load_standing(study_dir)
        except ValueError:
            continue
        if standing is None:
            continue
        lines = render_method_lines(standing, current_stage=current_stage, today=today)
        out.append(
            {
                "method_id": standing["method"]["id"],
                "title": standing["method"]["title"],
                "protocol_id": standing["method"]["protocol_id"],
                "decision": (
                    decide(standing, current_stage=current_stage)["decision"]
                    if current_stage
                    else standing["selection"]["decision"]
                ),
                "detail": "\n".join(lines),
                "lines": lines,
                "locator": str(study_dir / "standing" / f"{standing['fingerprint']}.json"),
                "date": str(standing.get("generated_at") or "")[:10] or None,
                "stale": bool(standing.get("stale")),
                "matched_terms": match["terms"],
            }
        )
    return out


def save_candidate(root, text: str, *, now: datetime | None = None, note: str = "") -> Path:
    """匹不上固定方法的自然语言方法：存草稿，不编译、不进任何统计。"""
    body = str(text or "").strip()
    if not body:
        raise ValueError("候选方法文本不能为空")
    current = clock_now(now)
    content = {
        "schema_version": 1,
        "kind": "method_candidate",
        "text": body,
        "status": "candidate_unconfirmed",
        "matched_method": None,
        "note": note
        or "通用编译不在本刀；要检验请用 methodology_backtest.py propose 把谓词写成规则 JSON",
    }
    content_id = digest(content)
    payload = {
        **content,
        "content_sha256": content_id,
        "recorded_at": current.astimezone(timezone.utc).isoformat(timespec="seconds"),
    }
    target = Path(root).expanduser() / "candidates" / f"{content_id}.json"
    if target.exists():
        return target
    return publish_json(target, payload)


def list_candidates(root) -> list[dict]:
    parent = Path(root).expanduser() / "candidates"
    if not parent.is_dir():
        return []
    out = []
    for path in sorted(parent.glob("*.json")):
        if path.is_symlink():
            continue
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


# --------------------------------------------------------------------------- #
# 观察对象 ↔ checkpoint
# --------------------------------------------------------------------------- #
def observation_due(trade_date: str, horizon: int = HORIZON) -> str:
    """回检提醒日 = D0 之后第 ``horizon`` 个工作日（节假日以交易日历为准，回检自己判到期）。"""
    day = date.fromisoformat(iso_date(trade_date))
    steps = 0
    while steps < horizon:
        day += timedelta(days=1)
        if day.weekday() < 5:
            steps += 1
    return day.isoformat()


def load_observation(study_dir, observation_path, protocol: dict) -> dict:
    """读并校验一份观察记录属于本实验（与 CLI 同一条门）。"""
    path = Path(observation_path)
    path.resolve().relative_to((Path(study_dir) / "capture").resolve())
    record = read_record(path)
    if record["kind"] != "capture" or record["payload"]["protocol_id"] != protocol["protocol_id"]:
        raise ValueError("观察记录不属于当前实验")
    features = record["payload"]["features"]
    if features["protocol_id"] != protocol["protocol_id"] or features["start"] != features["end"]:
        raise ValueError("观察记录的实验标识或日期范围不合法")
    validate_capture(
        protocol, features, now=datetime.fromisoformat(record["payload"]["captured_at"])
    )
    return record


def observation_claim(protocol: dict, features: dict) -> str:
    rows = features["rows"]
    counts = {name: sum(1 for row in rows if name in row["arms"]) for name in ARMS}
    stage = next((row.get("stage") for row in rows if row.get("stage") is not None), "未知")
    return (
        f"{features['start']} 方法观察：连续三日严格双红 {counts['streak3']} 个板块"
        f"（当日双红 {counts['dual_red']}，同日总体 {counts['universe']}，阶段 {stage}）；"
        f"第 {HORIZON} 个交易日后按原协议回检连续组五日均值是否高于当日双红组与总体"
        f"（研究读数，不构成买卖建议）"
    )


def register_observation_checkpoint(
    checkpoints_path,
    *,
    protocol: dict,
    features: dict,
    observation_path,
    study_dir,
    labels_db,
    captured_at: str,
) -> dict | None:
    """有信号且阶段适用的 D0 才登记；否则返回 None（无信号如实留在 capture 记录里）。"""
    rows = features["rows"]
    stage = next((row.get("stage") for row in rows if row.get("stage") is not None), None)
    streak3 = [row["entity_id"] for row in rows if "streak3" in row["arms"]]
    if not streak3 or stage not in protocol["market_stages"]:
        return None
    _path, record = checkpoints.register_checkpoint(
        checkpoints_path,
        claim=observation_claim(protocol, features),
        due=observation_due(features["start"]),
        category=CATEGORY,
        source=SOURCE,
        themes=list(THEMES),
        metric={
            "type": METRIC_TYPE,
            "study_dir": str(Path(study_dir).resolve()),
            "observation": str(Path(observation_path).resolve()),
            "labels_db": str(Path(labels_db).expanduser().resolve()),
        },
        framework_version=f"{METHOD_ID}@{protocol['protocol_id'][:12]}",
        object_type=OBJECT_TYPE,
        ts=captured_at,
    )
    return record


def find_observation_checkpoint(checkpoints_path, observation_path) -> dict | None:
    records, _warn = checkpoints.load_checkpoints(checkpoints_path)
    target = str(Path(observation_path).resolve())
    for record in reversed(records):
        metric = record.get("metric") or {}
        if metric.get("type") == METRIC_TYPE and metric.get("observation") == target:
            return record
    return None


def verdict_for(classification: str) -> tuple[str, float | None, str]:
    """分类 → checkpoint verdict。数据不足 / 环境变化 / 未到期都是 unverifiable：不进分母。"""
    if classification == "supported":
        return "hit", 1.0, "连续组五日均值高于当日双红组与总体"
    if classification == "method_error":
        return "miss", 0.0, "连续组五日均值未同时高于当日双红组与总体：假设未成立"
    return "unverifiable", None, CLASSIFICATION_CN.get(classification, classification)


def record_observation_verdict(
    verdicts_path, checkpoint: dict, result: dict, *, checked_at: str | None = None
) -> dict:
    verdict, score, reason = verdict_for(result["classification"])
    observed = {
        "classification": result["classification"],
        "flags": result.get("flags") or [],
        "diffs": result.get("diffs"),
        "means": result.get("means"),
        "stage_path": result.get("stage_path"),
        "record": result.get("record_path"),
    }
    degradation = None
    if verdict == "unverifiable":
        degradation = {
            "attempted": [{"source": "method_validation:recheck", "status": result["classification"]}],
            "gap": CLASSIFICATION_CN.get(result["classification"], result["classification"]),
            "impact": "不计入命中率分母；环境变化 / 数据不足的日子不检验假设",
            "fallback": "无替代源：只认原协议旁路库与冻结成员",
            "todo": list(result.get("todo") or []),
            "owed_source": SOURCE,
        }
    _path, record = checkpoints.record_verdict(
        verdicts_path,
        id=str(checkpoint["id"]),
        verdict=verdict,
        score=score,
        observed=observed,
        data_source=SOURCE,
        reason=reason,
        degradation=degradation,
        auto=True,
        checked_at=checked_at,
    )
    return record


# --------------------------------------------------------------------------- #
# 前向回检（CLI 与夜间 resolver 共用）
# --------------------------------------------------------------------------- #
def recheck_observation(
    study_dir,
    observation_path,
    labels_db,
    *,
    now: datetime | None = None,
    write_pending: bool = True,
) -> dict:
    """按原协议读冻结成员的后续结果，分类，写 recheck 收据（可选不写 pending）。

    抛 ``ValueError`` 表示旁路库水位 / 版本不满足（未到收盘、水位回退等），由调用方降级。
    """
    directory = Path(study_dir)
    protocol = load_protocol(directory)
    observation = load_observation(directory, observation_path, protocol)
    features = observation["payload"]["features"]
    outcomes = read_outcomes(labels_db, protocol, features, now=now)
    comparison = compare(protocol, features, outcomes)
    day = comparison["daily"][0]
    calendar = outcomes["calendar"]
    d0 = features["start"]
    window = [d for d in calendar if d > d0][:HORIZON]
    stage_path: dict = {}
    if window:
        stage_path = read_market_stages(labels_db, protocol, start=window[0], end=window[-1])
        stage_path = {d: stage_path.get(d) for d in window}
    classification, flags = classify_forward(day, stage_path, protocol)
    result = {
        "protocol_id": protocol["protocol_id"],
        "trade_date": d0,
        "observation_sha256": observation["content_sha256"],
        "classification": classification,
        "classification_cn": CLASSIFICATION_CN[classification],
        "flags": flags,
        "status": day["status"],
        "reasons": list(day["reasons"]),
        "means": day["means"],
        "diffs": _diffs(day) if day["status"] == "paired" else None,
        "stage_path": stage_path,
        "summary": comparison["summary"],
        "coverage": comparison["coverage"],
        "record_path": None,
        "todo": [],
    }
    if classification == "pending":
        result["todo"] = [
            f"等 {d0} 之后第 {HORIZON} 个交易日收盘并重建旁路库 outcomes 后重跑 recheck"
        ]
        if not write_pending:
            return result
    payload = {
        "protocol_id": protocol["protocol_id"],
        "features": features,
        "evaluator_code_sha256": evaluator_code_sha256(),
        "observation_sha256": observation["content_sha256"],
        "outcomes": outcomes,
        "comparison": comparison,
        "flywheel": {
            "version": FLYWHEEL_VERSION,
            "classification": classification,
            "flags": flags,
            "stage_path": stage_path,
        },
    }
    result["record_path"] = str(write_record(directory, "recheck", payload))
    return result


def resolve_observation(study_dir, observation_path, labels_db, *, now: datetime | None = None) -> dict:
    """夜间 resolver 入口：到期才写收据，未到期只回报 pending；写完刷新立场摘要。"""
    result = recheck_observation(
        study_dir, observation_path, labels_db, now=now, write_pending=False
    )
    if result["record_path"]:
        refresh_standing(study_dir, now=now)
    return result


# --------------------------------------------------------------------------- #
# 日常入口简报
# --------------------------------------------------------------------------- #
def daily_brief(
    *,
    user: str | None = None,
    users_root: str | Path | None = None,
    today: str | None = None,
    checkpoints_path: str | Path | None = None,
    verdicts_path: str | Path | None = None,
) -> dict:
    """日报用的方法飞轮段：只读摘要与 checkpoint 台账，没有实验时如实说没有。"""
    root = resolve_root(user, users_root)
    today = today or clock_now().date().isoformat()
    studies = list_studies(root)
    if not studies:
        return {
            "available": False,
            "root": str(root),
            "today": today,
            "reason": "该用户目录下没有方法验证实验（register 后出现）",
            "studies": [],
        }
    verdict_map: dict[str, dict] = {}
    checkpoint_rows: list[dict] = []
    if checkpoints_path is not None:
        checkpoint_rows, _ = checkpoints.load_checkpoints(checkpoints_path)
        if verdicts_path is not None:
            verdicts, _ = checkpoints.load_verdicts(verdicts_path)
            for item in verdicts:
                verdict_map[str(item["id"])] = item
    out = []
    for study_dir in studies:
        try:
            standing, fresh = load_standing(study_dir)
        except ValueError as exc:
            out.append({"study_dir": str(study_dir), "error": str(exc)})
            continue
        if standing is None:
            out.append(
                {
                    "study_dir": str(study_dir),
                    "error": "没有立场摘要：运行 method_validation.py status --refresh",
                }
            )
            continue
        forward = standing["forward"]
        today_capture = next(
            (item for item in forward["captures"] if item["trade_date"] == today), None
        )
        pending = []
        for item in forward["pending"]:
            checkpoint = next(
                (
                    row
                    for row in checkpoint_rows
                    if (row.get("metric") or {}).get("observation") == item["observation_path"]
                ),
                None,
            )
            latest = verdict_map.get(str(checkpoint.get("id"))) if checkpoint else None
            pending.append(
                {
                    "trade_date": item["trade_date"],
                    "streak3": item["counts"]["streak3"],
                    "stage": item["stage"],
                    "due": item["due"],
                    "waiting_for": item.get("waiting_for"),
                    "checkpoint_id": checkpoint.get("id") if checkpoint else None,
                    "latest_verdict": (latest or {}).get("verdict"),
                }
            )
        out.append(
            {
                "study_dir": str(study_dir),
                "method": standing["method"]["title"],
                "method_id": standing["method"]["id"],
                "protocol_id": standing["method"]["protocol_id"],
                "forward_start": standing["method"]["forward_start"],
                "fresh": fresh,
                "stale_reason": standing.get("stale_reason"),
                "today": (
                    {
                        "captured": today_capture is not None,
                        "has_signal": bool(today_capture and today_capture["has_signal"]),
                        "stage": today_capture["stage"] if today_capture else None,
                        "streak3": today_capture["counts"]["streak3"] if today_capture else None,
                        "streak3_members": today_capture["streak3_members"] if today_capture else [],
                    }
                ),
                "pending": pending,
                "settled_counts": forward["counts"],
                "first_real_cycle_completed": forward["first_real_cycle_completed"],
                "history": (
                    {
                        "paired_dates": standing["history_rehearsal"]["paired_dates"],
                        "signal_days": standing["history_rehearsal"]["signal_days"],
                        "streak3_minus_dual_red_pp": standing["history_rehearsal"][
                            "streak3_minus_dual_red_pp"
                        ],
                        "streak3_minus_universe_pp": standing["history_rehearsal"][
                            "streak3_minus_universe_pp"
                        ],
                        "signal_day_categories": standing["history_rehearsal"][
                            "signal_day_categories"
                        ],
                    }
                    if standing.get("history_rehearsal")
                    else None
                ),
                "selection": standing["selection"],
                "lines": render_method_lines(standing, today=today),
            }
        )
    return {"available": True, "root": str(root), "today": today, "studies": out}


def render_brief_lines(brief: dict) -> list[str]:
    """日报 markdown 行（确定性；无实验时一行说明）。"""
    if not brief or not brief.get("available"):
        reason = (brief or {}).get("reason") or "方法飞轮未启用"
        return [f"- {reason}"]
    lines: list[str] = []
    for study in brief["studies"]:
        if study.get("error"):
            lines.append(f"- {study['study_dir']}：{study['error']}")
            continue
        today = study["today"]
        if not today["captured"]:
            today_text = f"今日（{brief['today']}）未登记观察（前向起点 {study['forward_start']}；需收盘后旁路库水位到位）"
        elif today["has_signal"]:
            today_text = (
                f"今日信号：连续组 {today['streak3']} 个板块（阶段 {today['stage']}）："
                + "、".join(today["streak3_members"][:8])
            )
        else:
            today_text = f"今日无信号（阶段 {today['stage']}，连续组 {today['streak3']} 个）"
        lines.append(f"- **{study['method']}**（{study['method_id']}）")
        lines.append(f"  - {today_text}")
        if study["pending"]:
            for item in study["pending"]:
                tag = f"｜checkpoint {item['checkpoint_id']}" if item["checkpoint_id"] else ""
                lines.append(
                    f"  - 待验：{item['trade_date']} 连续组 {item['streak3']} 个，回检提醒 {item['due']}（以交易日历为准）{tag}"
                )
        else:
            lines.append("  - 待验对象：无")
        if study["settled_counts"]:
            lines.append(
                "  - 真实前向已结算："
                + "、".join(
                    f"{CLASSIFICATION_CN.get(k, k)} {v}"
                    for k, v in sorted(study["settled_counts"].items())
                )
            )
        history = study.get("history")
        if history:
            lines.append(
                f"  - 历史演练：信号 {history['signal_days']} 天 / 可配对 {history['paired_dates']} 天；"
                f"连续组相对当日双红 {_fmt_pp(history['streak3_minus_dual_red_pp'])}、相对总体 {_fmt_pp(history['streak3_minus_universe_pp'])}"
            )
        lines.append(f"  - 下一次问题里：{study['selection']['decision_cn']}")
        if study.get("stale_reason"):
            lines.append(f"  - 注意：{study['stale_reason']}")
    lines.append(f"- {DISCLAIMER}")
    return lines


def _stage_pattern() -> re.Pattern:
    return re.compile(r"(主升|反弹|横盘|顶部横盘|底部横盘|下跌|探底)")


def stage_from_text(text: str) -> str | None:
    """从一段盘面文字里取 canonical 阶段词（给消费方传 current_stage 用；取不到返回 None）。"""
    found = _stage_pattern().findall(str(text or ""))
    if not found:
        return None
    # 更具体的词优先（顶部横盘 > 横盘）。
    return max(found, key=len)
