#!/usr/bin/env python3
"""第一条方法验证闭环：登记 → 历史对照 / 当日观察 → 到期回检 → 报告，再接到日常使用。

只读 methodology_backtest 的标签旁路库，写独立研究收据；不写市场主库、画像或参数。
运行用 .venv-workbench/bin/python。退出码 0 成功、2 输入/数据/完整性问题、3 库锁占用。
前向 capture 只接受机器当前上海日期收盘后的数据，不提供 --now 或补登记逃生口。

能力升级 07 加的接线（全部派生自收据、不存第二份状态）：
- capture 有信号且阶段适用时把观察登记成 checkpoint（object_type=method_observation）；
- recheck 六类分类（支持 / 方法错误 / 数据不足 / 环境变化 / 没有信号 / 非适用阶段）并回写 verdict；
- status 打印立场摘要（历史演练 / 真实前向分列、下一次问题里采用 / 降低 / 排除）；
- match 看一句自然语言会不会命中固定方法；candidate 把匹不上的方法文本存草稿；
- daily 一条命令编排：主库水位领先就重建旁路库 → 到点 capture → 到期 recheck → 刷新摘要。
"""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
import time
from contextlib import contextmanager
from datetime import datetime, time as time_cls, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from intelligence.services.method_validation import (  # noqa: E402
    build_protocol,
    compare,
    list_records,
    load_protocol,
    protocol_id_for,
    read_features,
    read_outcomes,
    read_record,
    register,
    validate_capture,
    write_record,
)
from intelligence.services.method_validation import flywheel  # noqa: E402
from intelligence.services.methodology_backtest.labels import build_labels  # noqa: E402
from intelligence.services.methodology_backtest.outcomes import DEFAULT_HORIZONS, build_outcomes  # noqa: E402
from intelligence.services.methodology_backtest.store import open_labels_db, read_meta  # noqa: E402
from intelligence.userspace import user_space  # noqa: E402
from market_feature_store.db import DB_PATH as CANONICAL_DB_PATH  # noqa: E402
from market_feature_store.db import DatabaseLockedError, is_lock_conflict  # noqa: E402

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_RULE = ROOT / "methodology/rules/dual_red_streak3_continuation.v1.json"
ARM_NAMES = {"universe": "同日板块总体", "dual_red": "当日严格双红", "streak3": "连续至少三日严格双红"}


def current_time() -> datetime:
    return datetime.now(timezone.utc)


def evaluator_code_sha256() -> str:
    """把本次实际执行的应用源码指纹留在收据里，不能用 Git HEAD 冒充未提交代码。"""
    return flywheel.evaluator_code_sha256()


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
    return flywheel.load_observation(study_dir, path, protocol)


def _ledgers(args) -> tuple[Path | None, Path | None]:
    """checkpoint / verdict 台账路径：显式 --checkpoints-path 优先，否则按 --user 走 userspace。"""
    if getattr(args, "no_checkpoint", False):
        return None, None
    explicit = getattr(args, "checkpoints_path", None)
    if explicit:
        cpath = Path(explicit).expanduser()
        return cpath, cpath.with_name("verdicts.jsonl")
    space = user_space(getattr(args, "user", None))
    return space.checkpoints_path, space.verdicts_path


def _refresh(study_dir: Path) -> str:
    return str(flywheel.refresh_standing(study_dir, now=current_time()))


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
    standing = _refresh(Path(args.study_dir))
    _print({"record": str(path), "summary": result["summary"], "coverage": result["coverage"], "standing": standing})
    return 0


def _capture_once(study_dir: Path, labels_db: Path, args) -> dict:
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
            return {"observation": str(existing[0]), "status": "already_captured", "trade_date": day,
                    "members": len(record["payload"]["features"]["rows"]), "checkpoint": None}
        features = read_features(labels_db, protocol, start=day, end=day)
        captured_at = current_time()
        validate_capture(protocol, features, now=captured_at)
        captured_iso = captured_at.astimezone(timezone.utc).isoformat()
        path = write_record(study_dir, "capture", {**_payload(protocol, features), "captured_at": captured_iso})
    checkpoint = None
    cpath, _vpath = _ledgers(args)
    if cpath is not None:
        existing_ck = flywheel.find_observation_checkpoint(cpath, path)
        if existing_ck is None:
            checkpoint = flywheel.register_observation_checkpoint(
                cpath,
                protocol=protocol,
                features=features,
                observation_path=path,
                study_dir=study_dir,
                labels_db=labels_db,
                captured_at=captured_iso,
            )
        else:
            checkpoint = existing_ck
    streak3 = sum(1 for row in features["rows"] if "streak3" in row["arms"])
    return {
        "observation": str(path),
        "status": "captured",
        "trade_date": day,
        "members": len(features["rows"]),
        "streak3": streak3,
        "signal": bool(checkpoint),
        "checkpoint": checkpoint["id"] if checkpoint else None,
        "checkpoint_note": None if checkpoint else "无信号或阶段不适用：只留 capture 记录，不登记待验对象",
    }


def cmd_capture(args) -> int:
    result = _capture_once(args.study_dir, args.labels_db, args)
    result["standing"] = _refresh(Path(args.study_dir))
    _print(result)
    return 0


def _recheck_once(study_dir: Path, observation: Path, labels_db: Path, args, *, write_pending: bool = True) -> dict:
    result = flywheel.recheck_observation(
        study_dir, observation, labels_db, now=current_time(), write_pending=write_pending
    )
    cpath, vpath = _ledgers(args)
    verdict = None
    if cpath is not None and vpath is not None and result["classification"] != "pending":
        checkpoint = flywheel.find_observation_checkpoint(cpath, observation)
        if checkpoint is not None:
            verdict = flywheel.record_observation_verdict(vpath, checkpoint, result)
    return {
        "record": result["record_path"],
        "trade_date": result["trade_date"],
        "classification": result["classification"],
        "classification_cn": result["classification_cn"],
        "flags": result["flags"],
        "diffs": result["diffs"],
        "stage_path": result["stage_path"],
        "summary": result["summary"],
        "coverage": result["coverage"],
        "verdict": {"id": verdict["id"], "verdict": verdict["verdict"]} if verdict else None,
        "todo": result["todo"],
    }


def cmd_recheck(args) -> int:
    result = _recheck_once(args.study_dir, args.observation, args.labels_db, args)
    result["standing"] = _refresh(Path(args.study_dir))
    _print(result)
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
        meta = payload.get("flywheel")
        if meta:
            lines.extend([
                "",
                f"回检分类：**{flywheel.CLASSIFICATION_CN.get(meta.get('classification'), meta.get('classification'))}**"
                + (f"（标记：{'、'.join(meta.get('flags') or [])}）" if meta.get("flags") else ""),
            ])
    lines.extend(["", f"原件内容摘要：`{record['content_sha256']}`", ""])
    return "\n".join(lines)


def cmd_report(args) -> int:
    print(render_report(read_record(args.record)))
    return 0


def cmd_status(args) -> int:
    study_dir = Path(args.study_dir)
    if args.refresh:
        _refresh(study_dir)
    standing, fresh = flywheel.load_standing(study_dir)
    if standing is None:
        raise ValueError("没有立场摘要：加 --refresh 先从收据派生一份")
    if args.json:
        _print({**standing, "fresh": fresh})
        return 0
    today = args.today or current_time().astimezone(LOCAL_TZ).date().isoformat()
    print("# 方法立场")
    print()
    for line in flywheel.render_method_lines(standing, current_stage=args.current_stage, today=today):
        print(f"- {line}")
    forward = standing["forward"]
    if forward["pending"]:
        print()
        print("待验对象：")
        for item in forward["pending"]:
            print(f"- {item['trade_date']} 连续组 {item['counts']['streak3']} 个（阶段 {item['stage']}），回检提醒 {item['due']}；{item.get('waiting_for')}")
    if standing.get("history_rehearsal"):
        print()
        print("历史演练信号日逐日（不统称失效）：")
        print()
        print("| 日期 | 阶段 | 总体/双红/连续 | 分类 | 原因 | 未知标签成员 | 缺结果成员 |")
        print("|---|---|---|---|---|---:|---|")
        for row in standing["history_rehearsal"]["signal_day_table"]:
            counts = row["counts"]
            print(
                f"| {row['trade_date']} | {row['stage']} | {counts['universe']}/{counts['dual_red']}/{counts['streak3']} | "
                f"{flywheel.CLASSIFICATION_CN.get(row['classification'], row['classification'])} | {'、'.join(row['reasons']) or '-'} | "
                f"{row['unknown_label_members']} | {','.join(row['missing_members']) or '-'} |"
            )
    if not fresh:
        print()
        print(f"注意：{standing.get('stale_reason')}")
    return 0


def cmd_match(args) -> int:
    match = flywheel.match_query(args.query)
    records = []
    if match is not None:
        records = flywheel.recall_for_query(
            args.query,
            user=args.user,
            users_root=args.users_root,
            current_stage=args.current_stage,
            today=args.today,
        )
    if args.json:
        _print({"query": args.query, "match": match, "records": records})
        return 0
    if match is None:
        print("未命中固定方法（当前只支持双红持续性）；要保存为候选：`candidate --text \"...\"`")
        return 0
    print(f"命中方法 {match['method_id']}（关键词 {', '.join(match['terms'])}）")
    if not records:
        print("该用户目录下没有可读的立场摘要：先 register / history / status --refresh")
    for record in records:
        print()
        for line in record["lines"]:
            print(f"- {line}")
    return 0


def cmd_candidate(args) -> int:
    root = args.root if args.root else user_space(args.user).root / "method_validation"
    match = flywheel.match_query(args.text)
    if match is not None and not args.force:
        _print({"matched_method": match, "saved": None,
                "note": "文本命中固定方法：直接问它即可；确实是另一条方法请加 --force 存草稿"})
        return 0
    path = flywheel.save_candidate(root, args.text, now=current_time())
    _print({"saved": str(path), "status": "candidate_unconfirmed", "matched_method": None,
            "note": "草稿不编译、不进统计；要检验请用 methodology_backtest.py propose 写成规则 JSON"})
    return 0


def _main_watermark(db_path: Path) -> str | None:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
    finally:
        con.close()
    return str(row[0]) if row and row[0] is not None else None


def _labels_watermarks(labels_db: Path) -> dict:
    if not labels_db.is_file():
        return {"labels": None, "outcomes": None}
    con = open_labels_db(labels_db, read_only=True)
    try:
        meta = read_meta(con)
    finally:
        con.close()
    return {
        kind: (meta.get(kind) or {}).get("source_max_trade_date") for kind in ("labels", "outcomes")
    }


def cmd_daily(args) -> int:
    """一条命令把当天该做的都做了；每步都只在条件成立时动作，不成立就把原因写进输出。"""
    study_dir = Path(args.study_dir)
    labels_db = Path(args.labels_db).expanduser()
    db_path = Path(args.db_path).expanduser()
    if not db_path.is_file():
        # fail closed：默认主库路径是按代码根算的，另一棵工作树上不存在；不猜别的库。
        raise ValueError(
            f"主库不存在：{db_path}。用 --db-path 指向 canonical 主库，或设 MARKET_FEATURE_STORE_DB"
        )
    protocol = load_protocol(study_dir)
    now = current_time().astimezone(LOCAL_TZ)
    today = now.date().isoformat()
    report: dict = {"today": today, "now": now.isoformat(timespec="seconds"), "steps": []}

    main_wm = _main_watermark(db_path)
    marks = _labels_watermarks(labels_db)
    report["watermarks"] = {"main": main_wm, **marks}
    rebuilt = False
    if main_wm and (marks["labels"] is None or marks["labels"] < main_wm or marks["outcomes"] is None or marks["outcomes"] < main_wm):
        if args.no_rebuild:
            report["steps"].append({"step": "rebuild", "status": "skipped", "reason": "--no-rebuild；旁路库水位落后主库"})
        else:
            started = time.monotonic()
            # 同一时钟贯穿整次 daily：构建时间戳与 capture / recheck 的时序门用同一个 now。
            build_clock = current_time()
            labels_report = build_labels(db_path, labels_db, now=build_clock)
            outcomes_report = build_outcomes(
                db_path, labels_db, horizons=tuple(DEFAULT_HORIZONS), now=build_clock
            )
            rebuilt = True
            marks = _labels_watermarks(labels_db)
            report["watermarks"].update(marks)
            report["steps"].append({
                "step": "rebuild", "status": "done", "seconds": round(time.monotonic() - started, 1),
                "labels_rows": labels_report.row_count, "outcomes_rows": outcomes_report.row_count,
                "label_version": labels_report.label_version,
            })
    else:
        report["steps"].append({"step": "rebuild", "status": "skipped", "reason": "旁路库水位已与主库一致"})

    if today < protocol["forward_start"]:
        report["steps"].append({"step": "capture", "status": "skipped", "reason": f"前向起点 {protocol['forward_start']} 未到"})
    elif now.time() < time_cls(15):
        report["steps"].append({"step": "capture", "status": "skipped", "reason": "未到 15:00 收盘"})
    elif marks["labels"] != today:
        report["steps"].append({"step": "capture", "status": "skipped", "reason": f"旁路库水位 {marks['labels']} ≠ 今天（主库 {main_wm}）：当日复盘尚未落库"})
    else:
        try:
            result = _capture_once(study_dir, labels_db, args)
            report["steps"].append({"step": "capture", "status": result["status"], **{k: v for k, v in result.items() if k != "status"}})
        except (ValueError, RuntimeError) as exc:
            report["steps"].append({"step": "capture", "status": "refused", "reason": str(exc)})

    rechecks = []
    settled = {
        read_record(path)["payload"].get("observation_sha256")
        for path in list_records(study_dir, "recheck")
        if (read_record(path)["payload"].get("flywheel") or {}).get("classification") not in (None, "pending")
    }
    for observation in list_records(study_dir, "capture"):
        record = read_record(observation)
        if record["content_sha256"] in settled:
            continue
        try:
            result = _recheck_once(study_dir, observation, labels_db, args, write_pending=False)
            rechecks.append({"observation": str(observation), **result})
        except (ValueError, RuntimeError) as exc:
            rechecks.append({"observation": str(observation), "classification": "unverifiable", "reason": str(exc)})
    report["steps"].append({"step": "recheck", "status": "done" if rechecks else "nothing_due", "results": rechecks})
    report["standing"] = _refresh(study_dir)
    report["rebuilt"] = rebuilt
    standing, _fresh = flywheel.load_standing(study_dir)
    report["selection"] = standing["selection"] if standing else None
    _print(report)
    return 0


def _add_ledger_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("--user", default=None, help="checkpoint 台账所属用户（默认 FORESIGHT_USER 或 default）")
    command.add_argument("--checkpoints-path", default=None, help="显式 checkpoints.jsonl 路径（verdicts.jsonl 同目录）")
    command.add_argument("--no-checkpoint", action="store_true", help="不登记 / 不回写 checkpoint 台账")


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
        ("capture", "收盘后冻结今天的前瞻观察（有信号则登记待验对象）", cmd_capture),
        ("recheck", "读取冻结成员的后续收益并分类（支持 / 方法错误 / 数据不足 / 环境变化…）", cmd_recheck),
    ):
        command = commands.add_parser(name, help=title)
        command.add_argument("--study-dir", type=Path, required=True)
        command.add_argument("--labels-db", type=Path, required=True)
        if name == "recheck":
            command.add_argument("--observation", type=Path, required=True)
        if name in ("capture", "recheck"):
            _add_ledger_args(command)
        command.set_defaults(func=function)
    report = commands.add_parser("report", help="验证原件摘要并渲染中文报告")
    report.add_argument("--record", type=Path, required=True)
    report.set_defaults(func=cmd_report)

    status = commands.add_parser("status", help="立场摘要：历史演练 / 真实前向 / 待验对象 / 下一次选择")
    status.add_argument("--study-dir", type=Path, required=True)
    status.add_argument("--refresh", action="store_true", help="先从收据重新派生摘要（会读历史原件）")
    status.add_argument("--current-stage", default=None, help="传入当前大盘阶段以套环境门（如 下跌）")
    status.add_argument("--today", default=None, help="覆盖「今日」（默认机器上海日期）")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    match = commands.add_parser("match", help="一句自然语言会命中哪条固定方法、模型会看到什么")
    match.add_argument("--query", required=True)
    match.add_argument("--user", default=None)
    match.add_argument("--users-root", default=None, help="测试用：覆盖用户根目录")
    match.add_argument("--current-stage", default=None)
    match.add_argument("--today", default=None)
    match.add_argument("--json", action="store_true")
    match.set_defaults(func=cmd_match)

    candidate = commands.add_parser("candidate", help="匹不上固定方法的自然语言方法：存草稿，不编译")
    candidate.add_argument("--text", required=True)
    candidate.add_argument("--user", default=None)
    candidate.add_argument("--root", type=Path, default=None)
    candidate.add_argument("--force", action="store_true", help="文本命中固定方法也照样存草稿")
    candidate.set_defaults(func=cmd_candidate)

    daily = commands.add_parser("daily", help="每日编排：重建旁路库（水位落后时）→ 收盘 capture → 到期 recheck → 刷新摘要")
    daily.add_argument("--study-dir", type=Path, required=True)
    daily.add_argument("--labels-db", type=Path, required=True)
    daily.add_argument("--db-path", type=Path, default=Path(str(CANONICAL_DB_PATH)), help="主库（只读）")
    daily.add_argument("--no-rebuild", action="store_true", help="旁路库落后也不重建（只看不动）")
    _add_ledger_args(daily)
    daily.set_defaults(func=cmd_daily)
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
