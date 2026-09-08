#!/usr/bin/env python3
"""第一条方法验证闭环：登记 → 历史对照 / 当日观察 → 到期回检 → 报告。

只读 methodology_backtest 的标签旁路库，写独立研究收据；不写市场主库、画像或参数。
运行用 .venv-workbench/bin/python。退出码 0 成功、2 输入/数据/完整性问题、3 库锁占用。
前向 capture 只接受机器当前上海日期收盘后的数据，不提供 --now 或补登记逃生口。
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from intelligence.services.method_validation import (  # noqa: E402
    build_protocol,
    compare,
    load_protocol,
    protocol_id_for,
    read_features,
    read_outcomes,
    read_record,
    register,
    validate_capture,
    write_record,
)
from intelligence.userspace import user_space  # noqa: E402
from market_feature_store.db import DatabaseLockedError, is_lock_conflict  # noqa: E402

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_RULE = ROOT / "methodology/rules/dual_red_streak3_continuation.v1.json"
ARM_NAMES = {"universe": "同日板块总体", "dual_red": "当日严格双红", "streak3": "连续至少三日严格双红"}


def current_time() -> datetime:
    return datetime.now(timezone.utc)


def evaluator_code_sha256() -> str:
    """把本次实际执行的应用源码指纹留在收据里，不能用 Git HEAD 冒充未提交代码。"""
    digest = hashlib.sha256()
    files = sorted((ROOT / "intelligence/services/method_validation").glob("*.py"))
    files.append(Path(__file__).resolve())
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _print(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def _payload(protocol: dict, features: dict) -> dict:
    return {
        "protocol_id": protocol["protocol_id"],
        "features": features,
        "evaluator_code_sha256": evaluator_code_sha256(),
    }


@contextmanager
def _capture_lock(study_dir: Path):
    """同实验一次只登记一份当日观察；锁失败就停止，不能继续产生第二份样本。"""
    with (study_dir / ".capture.lock").open("a", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("另一个进程正在登记此实验的观察，请在完成后重试") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _observation(study_dir: Path, path: Path, protocol: dict) -> dict:
    path.resolve().relative_to((study_dir / "capture").resolve())
    record = read_record(path)
    if record["kind"] != "capture" or record["payload"]["protocol_id"] != protocol["protocol_id"]:
        raise ValueError("观察记录不属于当前实验")
    features = record["payload"]["features"]
    if features["protocol_id"] != protocol["protocol_id"] or features["start"] != features["end"]:
        raise ValueError("观察记录的实验标识或日期范围不合法")
    validate_capture(protocol, features, now=datetime.fromisoformat(record["payload"]["captured_at"]))
    return record


def cmd_register(args) -> int:
    root = args.root if args.root else user_space(args.user).root / "method_validation"
    identity = protocol_id_for(
        args.rule, history_start=args.history_start, history_end=args.history_end,
        forward_start=args.forward_start,
    )
    existing = Path(root).expanduser() / identity
    if (existing / "protocol.json").exists():
        protocol = load_protocol(existing)
        _print({"study_dir": str(existing.resolve()), "protocol_id": protocol["protocol_id"],
                "forward_start": protocol["forward_start"]})
        return 0
    protocol = build_protocol(
        args.rule,
        history_start=args.history_start,
        history_end=args.history_end,
        forward_start=args.forward_start,
        now=current_time(),
    )
    study_dir = register(root, protocol)
    _print({"study_dir": str(study_dir), "protocol_id": protocol["protocol_id"], "forward_start": protocol["forward_start"]})
    return 0


def cmd_history(args) -> int:
    protocol = load_protocol(args.study_dir)
    features = read_features(args.labels_db, protocol, **protocol["history"])
    outcomes = read_outcomes(args.labels_db, protocol, features, now=current_time())
    result = compare(protocol, features, outcomes)
    payload = {**_payload(protocol, features), "outcomes": outcomes, "comparison": result}
    path = write_record(args.study_dir, "history", payload)
    _print({"record": str(path), "summary": result["summary"], "coverage": result["coverage"]})
    return 0


def cmd_capture(args) -> int:
    study_dir = args.study_dir
    protocol = load_protocol(study_dir)
    with _capture_lock(study_dir):
        now = current_time()
        day = now.astimezone(LOCAL_TZ).date().isoformat()
        if day < protocol["forward_start"]:
            raise ValueError(f"前向观察从 {protocol['forward_start']} 开始；今天不能提前登记")
        if now.astimezone(LOCAL_TZ).hour < 15:
            raise ValueError("前向观察须在当日 15:00 收盘后登记")
        existing = sorted((study_dir / "capture" / day).glob("*.json"))
        if existing:
            if len(existing) != 1:
                raise ValueError("同日存在多份观察，需先核查原始收据")
            record = _observation(study_dir, existing[0], protocol)
            if record["payload"]["features"]["end"] != day:
                raise ValueError("观察分区与 D0 不一致")
            _print({"observation": str(existing[0]), "status": "already_captured", "trade_date": day})
            return 0
        features = read_features(args.labels_db, protocol, start=day, end=day)
        captured_at = current_time()
        validate_capture(protocol, features, now=captured_at)
        path = write_record(study_dir, "capture", {
            **_payload(protocol, features), "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        })
    _print({"observation": str(path), "status": "captured", "trade_date": day, "members": len(features["rows"])})
    return 0


def cmd_recheck(args) -> int:
    protocol = load_protocol(args.study_dir)
    observation = _observation(args.study_dir, args.observation, protocol)
    features = observation["payload"]["features"]
    outcomes = read_outcomes(args.labels_db, protocol, features, now=current_time())
    result = compare(protocol, features, outcomes)
    payload = {
        **_payload(protocol, features),
        "observation_sha256": observation["content_sha256"],
        "outcomes": outcomes,
        "comparison": result,
    }
    path = write_record(args.study_dir, "recheck", payload)
    _print({"record": str(path), "summary": result["summary"], "coverage": result["coverage"]})
    return 0


def _number(value, suffix="") -> str:
    return "不可计算" if value is None else f"{value:.4f}{suffix}"


def render_report(record: dict) -> str:
    payload = record["payload"]
    features = payload["features"]
    lines = [
        "# 方法验证实验报告",
        "",
        f"实验：`{payload['protocol_id']}`",
        f"类型：`{record['kind']}`；观察日期：{features['start']} 至 {features['end']}。",
        "",
        "本报告为研究读数，尚不具备决策或方法晋升资格。当前标签是历史重建结果，未获严格时间点数据认证。",
        "L2、晚间卖方和晨汇尚待同步；它们不参与此实验。",
    ]
    comparison = payload.get("comparison")
    if comparison is None:
        lines.extend(["", f"已冻结 {len(features['rows'])} 个板块日的输入与分组；尚未读取后续收益。"])
    else:
        summary = comparison["summary"]
        stage_dates = [day for day in comparison["daily"] if day["stage"] in ("主升", "反弹")]
        signal_dates = sum(bool(day["arms"]["streak3"]) for day in stage_dates)
        lines.extend([
            "",
            f"主升/反弹阶段共 {len(stage_dates)} 天，其中 {signal_dates} 天出现连续三日信号。",
            f"三组共同可评估日期：**{summary['paired_dates']}**。同一天的板块数量不增加日期数，日期窗口仍可能重叠。",
            "",
            "| 组别 | 五日平均收益 |",
            "|---|---:|",
        ])
        for arm, title in ARM_NAMES.items():
            lines.append(f"| {title} | {_number(summary.get('means', {}).get(arm), '%')} |")
        lines.extend([
            "",
            f"连续三日相对当日双红：**{_number(summary['streak3_minus_dual_red_pp'], ' 个百分点')}**。",
            f"连续三日相对同期板块总体：**{_number(summary['streak3_minus_universe_pp'], ' 个百分点')}**。",
            "",
            "每个日期先按板块等权，再按日期等权；仅用三组均有成员且基准全部结果完整的共同日期。",
            "五日收益不含信号当日；这是板块研究读数，未扣交易成本，不能直接当作策略净收益。",
            "交易日历沿用现有市场事实表，尚未独立认证交易所日历完整性。",
            "",
            "覆盖与排除状态（完整成员和原因保留在 JSON 原件）：",
            "同一日期可能有多个排除原因，原因计数不能直接相加。",
            "",
            "```json",
            json.dumps(comparison["coverage"], ensure_ascii=False, indent=2, allow_nan=False),
            "```",
            "",
            "日期明细：",
            "",
            "| 日期 | 市场阶段 | 状态 | 原因 |",
            "|---|---|---|---|",
        ])
        for day in comparison["daily"]:
            stage = str(day.get("stage") or "未知").replace("|", "\\|").replace("\n", " ")
            reasons = "、".join(day.get("reasons", [])).replace("|", "\\|")
            lines.append(f"| {day['trade_date']} | {stage} | {day['status']} | {reasons} |")
    lines.extend(["", f"原件内容摘要：`{record['content_sha256']}`", ""])
    return "\n".join(lines)


def cmd_report(args) -> int:
    print(render_report(read_record(args.record)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    reg = commands.add_parser("register", help="冻结三组协议和方法卡，开始新实验")
    reg.add_argument("--rule", type=Path, default=DEFAULT_RULE)
    reg.add_argument("--history-start", required=True)
    reg.add_argument("--history-end", required=True)
    reg.add_argument("--forward-start", required=True)
    reg.add_argument("--user", default=None)
    reg.add_argument("--root", type=Path, help="明确指定离线研究收据目录；默认走用户应用态")
    reg.set_defaults(func=cmd_register)
    for name, title, function in (
        ("history", "运行固定历史窗口三组对照", cmd_history),
        ("capture", "收盘后冻结今天的前瞻观察", cmd_capture),
        ("recheck", "读取冻结成员的后续收益", cmd_recheck),
    ):
        command = commands.add_parser(name, help=title)
        command.add_argument("--study-dir", type=Path, required=True)
        command.add_argument("--labels-db", type=Path, required=True)
        if name == "recheck":
            command.add_argument("--observation", type=Path, required=True)
        command.set_defaults(func=function)
    report = commands.add_parser("report", help="验证原件摘要并渲染中文报告")
    report.add_argument("--record", type=Path, required=True)
    report.set_defaults(func=cmd_report)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except DatabaseLockedError as exc:
        print(f"数据被占用，未继续执行：{exc}", file=sys.stderr)
        return 3
    except duckdb.IOException as exc:
        print(f"读取失败：{exc}", file=sys.stderr)
        return 3 if is_lock_conflict(exc) else 2
    except (ValueError, RuntimeError, OSError, duckdb.Error, KeyError, TypeError) as exc:
        print(f"实验未完成：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
