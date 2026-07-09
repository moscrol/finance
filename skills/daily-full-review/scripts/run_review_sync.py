#!/usr/bin/env python3
"""单日全量复盘 · 模块化同步编排器。

为什么不用 monolith `daily-update`：它把所有同步串在一个进程里，任一重模块
（sector-stocks / limit-heat / stock-daily）静默挂起就拖死整轮且无进度。

本脚本把同步拆成可隔离、可续跑的模块：
- 每个模块单独子进程跑，带超时；一个挂了不拖死整轮。
- 重模块（sector-stocks 续跑、limit-heat 失败题材重试、stock-daily 兜底）内置已验证路径。
- 子进程 stdout 直接继承到终端，看得到 limit-heat 的 chunk 进度。
- 每模块结果（状态/耗时/路径）追加到 state/runlog.md，沉淀顺/坑经验。

只调用已验证的 `python3 -m market_feature_store.cli <sync-*>`，不手搓 SQL。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_feature_store.db import connect  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
RUNLOG = SKILL_DIR / "state" / "runlog.md"
PY = sys.executable
CLI = [PY, "-m", "market_feature_store.cli"]


def _count(table: str, trade_date: str) -> int:
    con = connect(read_only=True)
    try:
        return con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE trade_date = ?", [trade_date]
        ).fetchone()[0]
    finally:
        con.close()


def _sectors_done(trade_date: str) -> tuple[int, int]:
    con = connect(read_only=True)
    try:
        done = con.execute(
            "SELECT COUNT(DISTINCT sector_ts_code) FROM fact_sector_stock_daily WHERE trade_date = ?",
            [trade_date],
        ).fetchone()[0]
        total = con.execute("SELECT COUNT(*) FROM dim_sector").fetchone()[0]
        return done, total
    finally:
        con.close()


def _empty_detail_themes(trade_date: str) -> list[str]:
    """有涨停但明细为空的题材名（需要逐个 --sector 重试）。"""
    con = connect(read_only=True)
    try:
        rows = con.execute(
            """
            SELECT h.sector_name
            FROM fact_theme_limit_heat_daily h
            LEFT JOIN fact_theme_limit_stock_daily s
              ON h.trade_date = s.trade_date AND h.sector_ts_code = s.sector_ts_code
            WHERE h.trade_date = ? AND COALESCE(h.limit_up_count, 0) > 0
            GROUP BY 1
            HAVING COUNT(s.stock_ts_code) = 0
            """,
            [trade_date],
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def narrative_freshness_warnings(trade_date: str) -> list[str]:
    """叙事源（晨汇/卖方观点）时效自检：断更只告警不阻断，同步段不依赖叙事源，
    但生成段的催化归因会因此缺档，提前报出来给用户补料的机会。"""
    try:
        from intelligence.paths import default_paths
        from intelligence.services import catalyst_attribution

        return catalyst_attribution.freshness_problems(default_paths().knowledge_wiki, trade_date)
    except Exception as e:  # noqa: BLE001
        return [f"叙事源时效检查失败: {e}"]


def preflight() -> list[str]:
    """开跑前环境自检：把环境问题在第一时间报清楚，不等跑到一半才发现。

    检查项：CDP proxy 存活、fupanhui 登录态、shared 软链。返回问题列表。"""
    problems: list[str] = []

    shared = ROOT / "shared"
    if not (shared / "feishu_utils.py").exists():
        problems.append(
            "shared 软链缺失或失效: 修复 `ln -sfn ~/.claude/shared shared`"
        )

    from market_feature_store.sources.fupanhui_source import CDP_PROXY
    try:
        with urllib.request.urlopen(f"{CDP_PROXY}/health", timeout=5) as resp:
            health = json.loads(resp.read())
        if not health.get("connected"):
            problems.append(f"CDP proxy 未连上 Chrome ({CDP_PROXY}/health connected=false)")
    except Exception as e:  # noqa: BLE001
        problems.append(
            f"CDP proxy 不可达 ({CDP_PROXY}): {e}; "
            "启动: node ~/.claude/skills/web-access/scripts/cdp-proxy.mjs"
        )
        return problems  # proxy 都不在, 登录态无从检查

    # 登录态检查带上 host：命中的标签页可能还停在 about:blank 或非 fupanhui 页
    # （fresh 标签页刚导航/旧页卡死），此时 localStorage 是别的 origin 的，直接判
    # 「未登录」是误报。host 不对或拿到 'no' 时等页面加载完再复查两次。
    _login_js = (
        "(()=>{try{if(location.host.indexOf('fupanhui.com')<0)return 'wrong-host:'+location.host;"
        "var s=JSON.parse(localStorage.getItem('user-auth-storage')||'{}');"
        "return (s.state&&s.state.token)?'ok':(localStorage.getItem('user_token')?'ok':'no');"
        "}catch(e){return 'no';}})()"
    )
    try:
        from market_feature_store.sources import fupanhui_source as fs
        raw = ""
        for attempt in range(3):
            raw = fs.cdp_eval(_login_js, timeout=30, retries=1)
            if raw == "ok":
                break
            time.sleep(5)
        if raw != "ok":
            problems.append(
                f"fupanhui 未登录或标签页未就绪（检查结果={raw}）: "
                "请确认 Chrome 已登录 fupanhui.com 且标签页可加载后重跑"
            )
    except Exception as e:  # noqa: BLE001
        problems.append(f"fupanhui 登录态检查失败: {e}")

    return problems


def _notify(msg: str) -> None:
    """告警双通道（与 nightly_full_review.sh 的 notify() 同款）：Mac 系统通知必达本机，
    飞书可选；告警自身失败静默，不影响同步流程。"""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{msg}" with title "全量复盘告警" sound name "Basso"'],
            timeout=10, capture_output=True,
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        subprocess.run([PY, str(ROOT / "scripts" / "notify_feishu.py"), msg],
                       timeout=30, capture_output=True)
    except Exception:  # noqa: BLE001
        pass


def run_step(label: str, argv: list[str], timeout: int) -> dict:
    """跑一个子进程模块，stdout 继承到终端（看得到进度），返回结果。"""
    print(f"\n>>> {label}: {' '.join(argv)} (timeout={timeout}s)", flush=True)
    started = time.time()
    status = "ok"
    code: int | None = None
    try:
        proc = subprocess.run(argv, cwd=str(ROOT), timeout=timeout)
        code = proc.returncode
        if code != 0:
            status = "fail"
    except subprocess.TimeoutExpired:
        status = "timeout"
    elapsed = time.time() - started
    print(f"<<< {label}: status={status} code={code} elapsed={elapsed:.1f}s", flush=True)
    return {"label": label, "status": status, "code": code, "elapsed": elapsed}


def sync_sector_stocks(trade_date: str, timeout: int, max_loops: int = 20) -> dict:
    """逐批续跑直到所有板块抓全；默认跳过已抓板块，超时杀掉续下一批。"""
    loops = 0
    while loops < max_loops:
        done, total = _sectors_done(trade_date)
        if total and done >= total:
            return {"label": "sector-stocks", "status": "ok", "code": 0,
                    "elapsed": 0.0, "note": f"{done}/{total} sectors"}
        loops += 1
        res = run_step(
            f"sector-stocks loop{loops} ({done}/{total})",
            CLI + ["sync-sector-stocks", "--trade-date", trade_date, "--limit", "60", "--sleep", "0.05"],
            timeout,
        )
        # 超时/失败也续跑：板块级提交可续，下一轮从断点继续
    done, total = _sectors_done(trade_date)
    status = "ok" if (total and done >= total) else "partial"
    return {"label": "sector-stocks", "status": status, "code": 0, "elapsed": 0.0,
            "note": f"{done}/{total} sectors after {loops} loops"}


def sync_limit_heat(trade_date: str, timeout: int) -> dict:
    """直跑（继承 stdout 看 chunk 进度），完后对失败题材逐个 --sector 重试。"""
    res = run_step(
        "limit-heat",
        CLI + ["sync-limit-heat", "--trade-date", trade_date, "--detail-chunk", "12", "--sleep", "0.05"],
        timeout,
    )
    empties = _empty_detail_themes(trade_date)
    retried = []
    for theme in empties:
        run_step(
            f"limit-heat retry {theme}",
            CLI + ["sync-limit-heat", "--trade-date", trade_date, "--sector", theme,
                   "--detail-chunk", "1", "--sleep", "0.05"],
            timeout,
        )
        retried.append(theme)
    still = _empty_detail_themes(trade_date)
    note = f"heat={_count('fact_theme_limit_heat_daily', trade_date)} " \
           f"stock={_count('fact_theme_limit_stock_daily', trade_date)} " \
           f"retried={len(retried)} still_empty={len(still)}"
    status = res["status"] if not still else "partial"
    return {"label": "limit-heat", "status": status, "code": res["code"],
            "elapsed": res["elapsed"], "note": note}


def sync_stock_daily(trade_date: str, timeout: int) -> dict:
    """单日复盘默认走东财快照（snapshot，快，当日值与 mootdx 一致）；
    失败 → 当日 fallback（sector_stock 聚合）。
    历史多日回填才用 mootdx（逐只慢，走 duckdb-backfill skill）。"""
    res = run_step(
        "stock-daily (snapshot)",
        CLI + ["sync-stock-daily-snapshot", "--trade-date", trade_date, "--page-size", "100"],
        timeout,
    )
    if res["status"] == "ok" and _count("fact_stock_daily", trade_date) > 0:
        return {**res, "label": "stock-daily", "note": "eastmoney snapshot ok"}
    fb = run_step(
        "stock-daily fallback",
        CLI + ["fill-stock-daily-fallback", "--trade-date", trade_date],
        timeout,
    )
    return {"label": "stock-daily", "status": fb["status"], "code": fb["code"],
            "elapsed": res["elapsed"] + fb["elapsed"], "note": "used fill-stock-daily-fallback"}


def build_plan(trade_date: str, timeout: int, heavy_timeout: int):
    return [
        ("db-lock", lambda: run_step("db-lock", [PY, "scripts/check_db_lock.py"], 120)),
        ("sectors", lambda: run_step("sectors", CLI + ["sync-sectors", "--trade-date", trade_date], timeout)),
        ("market-overview", lambda: run_step("market-overview", CLI + ["sync-market-overview", "--trade-date", trade_date, "--days", "60"], timeout)),
        ("market-daily", lambda: run_step("market-daily", CLI + ["sync-market-daily"], timeout)),
        ("index-daily", lambda: run_step("index-daily", CLI + ["sync-index-daily", "--trade-date", trade_date], timeout)),
        ("sw-l1-daily", lambda: run_step("sw-l1-daily", CLI + ["sync-sw-l1-daily", "--trade-date", trade_date, "--days", "20"], timeout)),
        ("market-deviation", lambda: run_step("market-deviation", CLI + ["sync-market-deviation", "--trade-date", trade_date], timeout)),
        ("sector-daily", lambda: run_step("sector-daily", CLI + ["sync-sector-daily", "--trade-date", trade_date, "--days", "25"], timeout)),
        ("sector-stocks", lambda: sync_sector_stocks(trade_date, heavy_timeout)),
        ("limit-heat", lambda: sync_limit_heat(trade_date, heavy_timeout)),
        ("stock-high", lambda: run_step("stock-high", CLI + ["sync-stock-high", "--trade-date", trade_date, "--page-size", "200"], heavy_timeout)),
        ("limit-advance", lambda: run_step("limit-advance", CLI + ["sync-limit-advance", "--trade-date", trade_date, "--min-boards", "2"], timeout)),
        ("stock-daily", lambda: sync_stock_daily(trade_date, heavy_timeout)),
        ("sector-resonance", lambda: run_step("sector-resonance", CLI + ["sync-sector-resonance"], timeout)),
        ("mainline-daily", lambda: run_step("mainline-daily", CLI + ["sync-mainline-daily", "--trade-date", trade_date], timeout)),
        ("theme-flow-daily", lambda: run_step("theme-flow-daily", CLI + ["sync-theme-flow-daily", "--trade-date", trade_date], timeout)),
    ]


def write_runlog(trade_date: str, results: list[dict], gate_ok: bool | None) -> None:
    RUNLOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"\n## {trade_date} | run {ts}", ""]
    lines.append("| 模块 | 状态 | 耗时s | 备注 |")
    lines.append("|---|---|---:|---|")
    for r in results:
        lines.append(f"| {r['label']} | {r['status']} | {r['elapsed']:.0f} | {r.get('note','')} |")
    gate = "COMPLETE" if gate_ok else ("INCOMPLETE" if gate_ok is not None else "未检")
    lines.append(f"| quality-gate | {gate} | - | check_daily_review_data.py |")
    bad = [r["label"] for r in results if r["status"] in {"timeout", "fail", "partial"}]
    if bad:
        lines.append("")
        lines.append(f"> 需关注（坑/未全绿）：{', '.join(bad)}")
    lines.append("")
    with RUNLOG.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"\n[runlog] appended -> {RUNLOG}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="单日全量复盘模块化同步编排器")
    ap.add_argument("--date", required=True, help="交易日 YYYY-MM-DD")
    ap.add_argument("--timeout", type=int, default=300, help="轻模块单次超时秒数, 默认300")
    ap.add_argument("--heavy-timeout", type=int, default=600, help="重模块单次超时秒数, 默认600")
    ap.add_argument("--only", default=None, help="只跑某个模块名（调试用）")
    ap.add_argument("--from-step", default=None, help="从某个模块开始")
    ap.add_argument("--retry-rounds", type=int, default=1,
                    help="整轮末尾对 fail/timeout 模块的补偿重试轮数, 默认1 (0=关闭)")
    ap.add_argument("--skip-preflight", action="store_true",
                    help="跳过开跑前环境自检")
    args = ap.parse_args()

    if not args.skip_preflight:
        problems = preflight()
        if problems:
            print("== preflight 发现环境问题 ==", flush=True)
            for p in problems:
                print(f"  - {p}", flush=True)
            print("(修复后重跑, 或加 --skip-preflight 强制继续)", flush=True)
            return 3
        print("== preflight 通过: CDP proxy / 登录态 / shared 软链 ==", flush=True)
        warnings = narrative_freshness_warnings(args.date)
        if warnings:
            print("== preflight 告警: 叙事源时效（不阻断，但催化归因会缺档） ==", flush=True)
            for w in warnings:
                print(f"  - {w}", flush=True)
        else:
            print("== preflight 通过: 叙事源（晨汇/卖方观点）时效正常 ==", flush=True)

    plan = build_plan(args.date, args.timeout, args.heavy_timeout)
    names = [n for n, _ in plan]
    if args.only:
        if args.only not in names:
            print(f"unknown --only: {args.only}; allowed: {', '.join(names)}")
            return 2
        plan = [(n, f) for n, f in plan if n == args.only]
    elif args.from_step:
        if args.from_step not in names:
            print(f"unknown --from-step: {args.from_step}; allowed: {', '.join(names)}")
            return 2
        plan = plan[names.index(args.from_step):]

    results: list[dict] = []
    for _name, fn in plan:
        results.append(fn())

    # 收尾补偿：CDP 500 等瞬态故障到末尾往往已自愈，统一重跑 fail/timeout 模块
    for round_no in range(1, max(args.retry_rounds, 0) + 1):
        bad_idx = [i for i, r in enumerate(results) if r["status"] in {"fail", "timeout"}]
        if not bad_idx:
            break
        bad_names = [plan[i][0] for i in bad_idx]
        print(f"\n== 收尾重试 第{round_no}轮: {', '.join(bad_names)} ==", flush=True)
        for i in bad_idx:
            res = plan[i][1]()
            res["note"] = (str(res.get("note") or "") + f" [retry r{round_no}]").strip()
            results[i] = res

    # 单模块失败告警：整段 rc 可能仍为 0（闸门通过），但 fail/timeout/partial 模块要即时报出来，
    # 不能只沉在 runlog 里等人翻。告警自身失败不影响同步结果。
    bad = [f"{r['label']}({r['status']})" for r in results if r["status"] in {"fail", "timeout", "partial"}]
    if bad:
        _notify(f"⚠️ 全量复盘 {args.date} 同步段模块未全绿：{', '.join(bad)}；详见 state/runlog.md")

    # 审计
    gate = subprocess.run([PY, "scripts/check_daily_review_data.py", args.date], cwd=str(ROOT))
    gate_ok = gate.returncode == 0

    # 收尾：导出当日增量到 iCloud（小 parquet，几 MB；配合全量基线可还原）。
    # 失败不影响复盘结果，仅告警。
    export_res = run_step(
        "export-increment",
        [PY, str(SKILL_DIR / "scripts" / "export_increment.py"), "--date", args.date],
        args.timeout,
    )
    results.append({**export_res, "label": "export-increment"})

    write_runlog(args.date, results, gate_ok)
    print("\n== 同步段结束 ==", flush=True)
    print("下一步生成段：", flush=True)
    print(f"  python3 -m intelligence.cli daily --date {args.date} --skip-sync --from-step daily-review \\", flush=True)
    print(f"    --summary-json market_feature_store/exports/{args.date}-daily-workflow-summary.json", flush=True)
    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
