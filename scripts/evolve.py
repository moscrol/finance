#!/usr/bin/env python3
"""evolve —— 可验证·可回溯·可迭代进化的策略流水线（命令触发，不自动定时）。

支持策略 1 / 3 / 4 的确定性无前视生成 + 可回溯记录 + 前瞻收益验证。

典型用法（复盘由你手动口令触发产出当日 fact 层之后）：
  python3 scripts/evolve.py generate --date 2026-06-13                      # 生成当日 策略1/3/4 名单 + 记录
  python3 scripts/evolve.py generate --start 2026-04-08 --end 2026-06-12    # 批量回补
  python3 scripts/evolve.py validate --strategy 1                           # 策略一 T1CORE6 前瞻收益
  python3 scripts/evolve.py validate --strategy 3                           # 策略三 S3_ALL
  python3 scripts/evolve.py validate --strategy 4 --scope OVERLAP           # 策略四 双引擎重叠
  python3 scripts/evolve.py log                                             # 把各策略已算结果写回 进化.md（AUTO 区块）
  python3 scripts/evolve.py suggest                                         # 策略一参数网格回测，给"调参建议"
  python3 scripts/evolve.py audit                                           # 体检：前视/格式/缺数据/参数漂移

口径口径（scope）：
  策略1：ALL / NEWHIGH / T1CORE6（默认 T1CORE6）
  策略3：S3_ALL / S3_FIRST_TOUCH / S3_WINDOW（默认 S3_ALL）
  策略4：S4_ALL / ENGINE_A / ENGINE_B / OVERLAP（默认 S4_ALL）

设计原则：
- 自动链路自包含，不解析人工矩阵 HTML；策略3/4 生成口径直接照搬仓库原始生成脚本的 SQL。
- generate 只用 D0 及以前数据 → 无前视；记录含参数版本 + 数据覆盖 + 每票命中条件 → 可回溯可复现。
- suggest 只产出建议、不改规则 → 防过拟合；改参须人工升 version 并记 params_history.md。
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_feature_store.db import connect  # noqa: E402
from evolution import strategy1, strategy3, strategy4, validate as vmod  # noqa: E402
from evolution import params as evparams  # noqa: E402
from intelligence import userspace  # noqa: E402

EVO = ROOT / "evolution"
RECORDS = EVO / "records"
VALID = EVO / "validation"
SUGG = EVO / "suggestions"
PARAMS_PATH = EVO / "params.json"
DB_PATH = ROOT / "db/market_feature_store.duckdb"
JINHUA = ROOT / "进化.md"
AUTO_START = "<!-- EVOLVE:AUTO-LOG START -->"
AUTO_END = "<!-- EVOLVE:AUTO-LOG END -->"

STRAT_MODS = {"1": strategy1, "3": strategy3, "4": strategy4}
DEFAULT_SCOPE = {"1": "T1CORE6", "3": "S3_ALL", "4": "S4_ALL"}


def resolve_active_user(args):
    """显式 --user > FORESIGHT_USER 环境变量；都没有则返回 None（用共享 baseline）。"""
    raw = getattr(args, "user", None) or os.environ.get(userspace.ENV_USER)
    if not raw or not str(raw).strip():
        return None
    return userspace.resolve_user_id(raw)


def evo_paths(uid):
    """该用户的 evolve 输出路径；无 user 时落共享 baseline（绝不互相覆盖）。"""
    if uid:
        base = EVO / "users" / uid
        return base / "records", base / "validation", base / "suggestions", base / "进化.md"
    return RECORDS, VALID, SUGG, JINHUA


def load_params(uid=None):
    """加载生效参数 = 共享 baseline ⊕ 用户稀疏 overlay。返回 ``(params, meta)``。"""
    overlay_path = userspace.user_space(uid).strategy_params_path if uid else None
    return evparams.load_effective_params(base_path=PARAMS_PATH, overlay_path=overlay_path)


def _print_overlay(uid, pmeta):
    if uid:
        print(f"[user] {uid}")
    if pmeta.get("overlay_applied"):
        print(
            f"[overlay] 策略 overlay v{pmeta.get('overlay_version')} "
            f"覆盖段={pmeta.get('overlay_sections')}"
        )
    for w in pmeta.get("warnings", []):
        print(f"[overlay-warn] {w}")


def _provenance(rec, uid, pmeta):
    """overlay 生效时在记录/验证负载里留痕，保证可回溯。"""
    if uid:
        rec["user"] = uid
    if pmeta.get("overlay_applied"):
        rec["params_overlay_version"] = pmeta.get("overlay_version")
        rec["params_overlay_sections"] = pmeta.get("overlay_sections")
    return rec


def trading_dates(con, start, end):
    return [str(x[0]) for x in con.execute(
        "select trade_date from fact_market_daily where trade_date between ? and ? order by trade_date",
        [start, end]).fetchall()]


def strat_scope(p, strat, scope):
    if scope:
        return scope
    return p.get(f"strategy{strat}", {}).get("scope", DEFAULT_SCOPE[strat])


def get_strat_payload(rec, strat):
    """从记录里取某策略子负载，兼容旧版扁平策略一记录。"""
    if isinstance(rec.get("strategies"), dict):
        return rec["strategies"].get(str(strat))
    if str(strat) == "1" and "picks" in rec:  # 旧版扁平策略一记录
        return rec
    return None


# ---------------------------------------------------------------- generate
def cmd_generate(args):
    uid = resolve_active_user(args)
    p, pmeta = load_params(uid)
    _print_overlay(uid, pmeta)
    records_dir, _, _, _ = evo_paths(uid)
    records_dir.mkdir(parents=True, exist_ok=True)

    # 1) 交易日列表 + 策略一（共用一个只读连接）
    con = connect(read_only=True)
    try:
        dates = [args.date] if args.date else trading_dates(con, args.start, args.end)
        s1_map = {}
        for d in dates:
            s1_map[d] = strategy1.payload_for_date(con, d, p)
    finally:
        con.close()

    # 2) 策略三/四（各自开内存连接 ATTACH 只读，支持 TEMP 表）
    s3_map = strategy3.generate_range(str(DB_PATH), dates, p)
    s4_map = strategy4.generate_range(str(DB_PATH), dates, p)

    written, skipped = 0, 0
    ts = datetime.now().isoformat(timespec="seconds")
    for d in dates:
        strategies = {}
        if s1_map.get(d) is not None:
            strategies["1"] = s1_map[d]
        if d in s3_map:
            strategies["3"] = s3_map[d]
        if d in s4_map:
            strategies["4"] = s4_map[d]
        if not strategies:
            skipped += 1
            print(f"[skip] {d} 无行情数据（复盘可能未生成/未入库）")
            continue
        rec = {
            "date": d,
            "params_version": p["version"],
            "generated_at": ts,
            "strategies": strategies,
        }
        _provenance(rec, uid, pmeta)
        (records_dir / f"{d}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1
        c1 = strategies.get("1", {}).get("counts", {})
        c3 = strategies.get("3", {}).get("counts", {})
        c4 = strategies.get("4", {}).get("counts", {})
        print(f"[ok] {d}  S1[T1CORE6={c1.get('T1CORE6', '-')}] "
              f"S3[ALL={c3.get('S3_ALL', '-')}] "
              f"S4[A={c4.get('ENGINE_A', '-')} B={c4.get('ENGINE_B', '-')} OVL={c4.get('OVERLAP', '-')}]")
    print(f"\n生成完成：写入 {written} 天，跳过 {skipped} 天 → {records_dir}")


def load_records(records_dir=RECORDS):
    out = {}
    if not records_dir.exists():
        return out
    for fp in sorted(records_dir.glob("*.json")):
        out[fp.stem] = json.loads(fp.read_text(encoding="utf-8"))
    return out


# ---------------------------------------------------------------- validate
def cmd_validate(args):
    uid = resolve_active_user(args)
    p, pmeta = load_params(uid)
    _print_overlay(uid, pmeta)
    records_dir, valid_dir, _, _ = evo_paths(uid)
    horizons = p["validation"]["horizons"]
    strat = str(args.strategy or "1")
    if strat not in STRAT_MODS:
        print(f"未知策略 {strat}（只支持 1/3/4）。")
        return
    scope = strat_scope(p, strat, args.scope)
    mod = STRAT_MODS[strat]
    records = load_records(records_dir)
    if not records:
        print("没有生成记录，先跑 generate。")
        return

    picks_by_date = {}
    pick_meta = {}  # (date, code) -> pick dict
    for d, rec in records.items():
        sub = get_strat_payload(rec, strat)
        if not sub:
            continue
        codes, seen = [], set()
        for pk in mod.picks_in_scope(sub, scope):
            c = pk["code"]
            if c in seen:
                continue
            seen.add(c)
            codes.append(c)
            pick_meta[(d, c)] = pk
        if codes:
            picks_by_date[d] = codes
    if not picks_by_date:
        print(f"策略{strat} 口径 {scope}：没有任何名单（可能记录里该策略为空）。")
        return

    con = connect(read_only=True)
    try:
        ret_map, cal = vmod.forward_returns(con, picks_by_date, horizons)
    finally:
        con.close()

    valid_dir.mkdir(parents=True, exist_ok=True)
    detail = []
    for d in sorted(picks_by_date):
        for c in picks_by_date[d]:
            r = ret_map.get((d, c), {})
            pk = pick_meta.get((d, c), {})
            detail.append({
                "date": d, "code": c, "name": pk.get("name"), "sw_l1": pk.get("sw_l1"),
                "scope": pk.get("scope"),
                **{f"t{h}": r.get(h, {}).get("ret_pct") for h in horizons},
                **{f"t{h}_status": r.get(h, {}).get("status") for h in horizons},
            })
    agg = vmod.aggregate(ret_map, picks_by_date, horizons, p)
    payload = {
        "strategy": strat, "scope": scope, "params_version": p["version"],
        "validated_at": datetime.now().isoformat(timespec="seconds"),
        "window": [min(picks_by_date), max(picks_by_date)],
        "n_days": len(picks_by_date), "n_picks": sum(len(v) for v in picks_by_date.values()),
        "aggregate": {f"T+{h}": agg[h] for h in horizons},
        "detail": detail,
    }
    _provenance(payload, uid, pmeta)
    out_fp = valid_dir / f"cumulative-s{strat}-{scope}.json"
    out_fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"策略{strat} 口径 {scope}：{payload['n_days']} 天 / {payload['n_picks']} 名单 "
          f"({payload['window'][0]}~{payload['window'][1]})")
    for h in horizons:
        a = agg[h]
        print(f"  T+{h}: n={a['n']} pending={a['pending']} win={a['win']} "
              f"mean={a['mean']} strong={a['strong']} fail={a['fail']}")
    print(f"→ {out_fp}")


# ---------------------------------------------------------------- log
STRAT_TITLE = {"1": "策略一", "3": "策略三", "4": "策略四"}


def cmd_log(args):
    uid = resolve_active_user(args)
    p, pmeta = load_params(uid)
    _print_overlay(uid, pmeta)
    _, valid_dir, _, jinhua = evo_paths(uid)
    horizons = p["validation"]["horizons"]
    files = sorted(valid_dir.glob("cumulative-s*.json")) if valid_dir.exists() else []
    if not files:
        print("没有验证结果，先跑 validate（--strategy 1/3/4）。")
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        AUTO_START,
        "",
        f"## 【自动进化日志】（参数版本 v{p['version']}，更新于 {ts}）",
        "",
        "> 由 `scripts/evolve.py log` 自动生成/覆盖（命令触发，无前视）；下方按 策略/口径 各一张表。",
        "",
    ]
    for fp in files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        strat = str(data.get("strategy", "1"))
        scope = data.get("scope", "")
        agg = data["aggregate"]
        lines += [
            f"### {STRAT_TITLE.get(strat, '策略'+strat)} · {scope}"
            f"（{data['window'][0]}~{data['window'][1]}，{data['n_days']} 日 / {data['n_picks']} 名单）",
            "",
            "| 视界 | 已到期n | pending | 胜率% | 均值% | 强命中% | 失败% |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for h in horizons:
            a = agg.get(f"T+{h}", {})
            lines.append(f"| T+{h} | {a.get('n')} | {a.get('pending')} | {a.get('win')} "
                         f"| {a.get('mean')} | {a.get('strong')} | {a.get('fail')} |")
        lines.append("")
    lines += [
        "> 累计 ≥10 个交易日后用 `evolve suggest` 看调参建议（仅建议，人工确认后升 params version）。",
        "",
        AUTO_END,
    ]
    block = "\n".join(lines)

    text = jinhua.read_text(encoding="utf-8") if jinhua.exists() else "# 进化.md\n"
    if AUTO_START in text and AUTO_END in text:
        pre = text.split(AUTO_START)[0].rstrip()
        post = text.split(AUTO_END, 1)[1].lstrip("\n")
        new = pre + "\n\n" + block + ("\n\n" + post if post.strip() else "\n")
    else:
        new = text.rstrip() + "\n\n" + block + "\n"
    jinhua.parent.mkdir(parents=True, exist_ok=True)
    jinhua.write_text(new, encoding="utf-8")
    print(f"已写回 进化.md 的 AUTO 区块（{len(files)} 张表：{[fp.name for fp in files]}）。")


# ---------------------------------------------------------------- suggest
def cmd_suggest(args):
    uid = resolve_active_user(args)
    p, pmeta = load_params(uid)
    _print_overlay(uid, pmeta)
    records_dir, _, sugg_dir, _ = evo_paths(uid)
    horizons = p["validation"]["horizons"]
    grid = p["suggest"]["grid"]
    min_n = p["suggest"]["min_samples"]
    con = connect(read_only=True)
    try:
        records = load_records(records_dir)
        if not records:
            print("没有生成记录，先跑 generate。")
            return
        dates = sorted(records)
        results = []
        for k in grid["t1core_size"]:
            for q in grid["quintile"]:
                pv = copy.deepcopy(p)
                pv["strategy1"]["t1core_size"] = k
                pv["strategy1"]["quintile"] = q
                picks_by_date = {}
                for d in dates:
                    rec = strategy1.generate_for_date(con, d, pv)
                    if not rec:
                        continue
                    cs = [pk["code"] for pk in strategy1.picks_in_scope(rec, "T1CORE6")]
                    if cs:
                        picks_by_date[d] = cs
                ret_map, _ = vmod.forward_returns(con, picks_by_date, horizons)
                agg = vmod.aggregate(ret_map, picks_by_date, horizons, pv)
                a5 = agg[5]
                results.append({
                    "t1core_size": k, "quintile": q,
                    "n_t5": a5["n"], "win_t5": a5["win"], "mean_t5": a5["mean"],
                    "strong_t5": a5["strong"], "fail_t5": a5["fail"],
                    "n_picks": sum(len(v) for v in picks_by_date.values()),
                })
    finally:
        con.close()

    cur = (p["strategy1"]["t1core_size"], p["strategy1"]["quintile"])
    mature = [r for r in results if r["n_t5"] and r["n_t5"] >= min_n]
    ranked = sorted(mature, key=lambda r: (-(r["mean_t5"] or -999), -(r["win_t5"] or -999)))
    sugg_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    lines = [
        f"# 调参建议（策略一 T1CORE6）· {ts}",
        "",
        "> 目前只对策略一做网格回测建议；策略三/四参数固定照搬仓库原始口径，如需调参另行人工评估。",
        "",
        f"当前参数：t1core_size={cur[0]}, quintile={cur[1]}（v{p['version']}）。",
        f"样本门槛：T+5 已到期 n >= {min_n} 才纳入比较。共 {len(mature)}/{len(results)} 个组合达标。",
        "",
        "| t1core_size | quintile | T+5_n | 胜率% | 均值% | 强命中% | 失败% | 名单数 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in ranked:
        mark = "  ← 当前" if (r["t1core_size"], r["quintile"]) == cur else ""
        lines.append(f"| {r['t1core_size']} | {r['quintile']} | {r['n_t5']} | {r['win_t5']} | "
                     f"{r['mean_t5']} | {r['strong_t5']} | {r['fail_t5']} | {r['n_picks']} |{mark}")
    rec_line = "样本不足，暂不建议调参。"
    if ranked:
        best = ranked[0]
        if (best["t1core_size"], best["quintile"]) == cur:
            rec_line = "建议：维持当前参数（当前组合在已到期样本上已是最优/并列最优）。"
        else:
            rec_line = (f"建议（待人工确认）：可考虑 t1core_size={best['t1core_size']}, "
                        f"quintile={best['quintile']}（T+5 均值 {best['mean_t5']}% vs 当前组合）。"
                        f"确认后请升 params version 并在 params_history.md 记录依据。")
    lines += ["", "## 结论", "", rec_line, "",
              "> 仅为基于历史已到期样本的网格回测建议，不自动改规则；防止过拟合，务必人工判断后再调。"]
    out = sugg_dir / f"suggestion-{ts}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(rec_line)
    print(f"→ {out}")


# ---------------------------------------------------------------- audit
def cmd_audit(args):
    uid = resolve_active_user(args)
    records_dir, _, _, _ = evo_paths(uid)
    issues = []
    notes = []
    # 1) 研究版生成器前视检测
    gen = ROOT / "research/market-hypothesis/_scripts/strategy1_full_window_0408_0605.py"
    if gen.exists():
        src = gen.read_text(encoding="utf-8", errors="ignore")
        if "rel_strong" in src and "divergence" in src:
            issues.append(f"[前视] {gen.relative_to(ROOT)}: full 判定含 rel_strong（用 divergence_date 次日相对强度），"
                          f"其产出 strategy1-*-selected-detail.csv 不可作点位名单。evolve 生成器已剔除该条件。")
    # 2) selected-detail.csv 含前视列
    sel = ROOT / "research/market-hypothesis/strategy1-0408-0605-selected-detail.csv"
    if sel.exists():
        head = sel.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
        if head and ("pct_0605" in head[0] or "divergence" in head[0] or "ret_to_0605" in head[0]):
            issues.append(f"[前视] {sel.relative_to(ROOT)}: 含 divergence/0605 等未来列，禁止当点位名单。")
    # 3) 人工矩阵 div/span 一致性
    mx = ROOT / "复盘/matrices/strategy1-priority-stock-matrix.html"
    if mx.exists():
        htxt = mx.read_text(encoding="utf-8", errors="ignore")
        nspan = htxt.count('<span class="stock')
        ndiv = htxt.count('<div class="stock')
        if nspan and ndiv:
            notes.append(f"[格式] 人工矩阵同时含 span({nspan}) 与 div({ndiv}) 个个股块；"
                         f"原验证脚本需已打补丁兼容两者（备份 .bak-20260615）。")
    # 4) 生成记录可回溯性 + 多策略覆盖
    records = load_records(records_dir)
    if records:
        bad = [d for d, r in records.items() if "params_version" not in r]
        if bad:
            issues.append(f"[回溯] 以下生成记录缺 params_version：{bad[:10]}")
        cov = {"1": 0, "3": 0, "4": 0}
        for d, r in records.items():
            for s in ("1", "3", "4"):
                sub = get_strat_payload(r, s)
                if sub and sub.get("picks") is not None:
                    cov[s] += 1
        notes.append(f"[覆盖] 生成记录 {len(records)} 天（{min(records)}~{max(records)}）："
                     f"策略一 {cov['1']} 天 / 策略三 {cov['3']} 天 / 策略四 {cov['4']} 天。")
        if cov["3"] == 0:
            notes.append("[覆盖] 暂无策略三记录（重新 generate 以纳入 S3）。")
        if cov["4"] == 0:
            notes.append("[覆盖] 暂无策略四记录（重新 generate 以纳入 S4）。")
    else:
        notes.append("[覆盖] 尚无生成记录（先跑 generate）。")
    # 5) 参数文件完整性（含用户 overlay 合并后）
    try:
        p, pmeta = load_params(uid)
        for key in ("strategy1", "strategy3", "strategy4", "validation", "suggest"):
            if key not in p:
                issues.append(f"[参数] params.json 缺 {key} 段。")
        if pmeta.get("overlay_applied"):
            notes.append(
                f"[overlay] 用户 {uid} 策略 overlay v{pmeta.get('overlay_version')} "
                f"覆盖段={pmeta.get('overlay_sections')}（合并后参数完整）。"
            )
        for w in pmeta.get("warnings", []):
            issues.append(f"[overlay] {w}")
    except Exception as e:
        issues.append(f"[参数] 读取 params.json 失败：{e}")

    print("=== evolve audit ===")
    print(f"问题 {len(issues)} 项：")
    for x in issues:
        print("  -", x)
    print(f"提示 {len(notes)} 项：")
    for x in notes:
        print("  -", x)
    if not issues:
        print("未发现阻断性问题。")


def main():
    ap = argparse.ArgumentParser(description="策略进化流水线 evolve（策略 1/3/4）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="生成 策略1/3/4 名单 + 生成记录")
    g.add_argument("--date")
    g.add_argument("--start")
    g.add_argument("--end")
    g.add_argument("--user", default=None, help="按用户加载策略 overlay 并写入 evolution/users/<id>/")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate", help="对生成记录重算前瞻收益")
    v.add_argument("--strategy", help="1 / 3 / 4（默认 1）")
    v.add_argument("--scope")
    v.add_argument("--user", default=None, help="按用户加载策略 overlay + 用户记录")
    v.set_defaults(func=cmd_validate)

    log_parser = sub.add_parser("log", help="把各策略已算结果写回 进化.md（AUTO 区块）")
    log_parser.add_argument("--user", default=None, help="写回 evolution/users/<id>/进化.md")
    log_parser.set_defaults(func=cmd_log)

    s = sub.add_parser("suggest", help="策略一参数网格回测，产出调参建议（仅建议）")
    s.add_argument("--user", default=None, help="按用户加载策略 overlay + 用户记录")
    s.set_defaults(func=cmd_suggest)

    a = sub.add_parser("audit", help="体检：前视/格式/缺数据/参数漂移")
    a.add_argument("--user", default=None, help="体检该用户的 overlay/记录")
    a.set_defaults(func=cmd_audit)

    args = ap.parse_args()
    if args.cmd == "generate" and not args.date and not (args.start and args.end):
        ap.error("generate 需 --date 或 --start/--end")
    args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
