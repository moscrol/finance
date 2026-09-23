#!/usr/bin/env python3
"""302132 回填完整副本演练·外部独立验收（fail-closed 门禁，非报告生成器）。

对象角色（两种用法同一语义）：
- `--production`：**不可变基线**库。演练复验 = 未动的真生产；生产执行后验收 =
  换库前备份文件（路径与 sha 见执行收据 backup 字段）。
- `--clone`：**换库后结果**库。演练 = 演练产物库；生产执行后 = canonical 生产库
  （收据按 `<clone>.repair-backfill-execution.<run_id>.json` 派生）。
- `--expected-production-sha256`：基线 sha（生产执行后 = 换库前生产 sha =
  执行收据 backup.backup_sha256），首尾各核一次（TOCTOU 闭环）。

实际执行的检查（文档只声称实现了的）：

参数格式（先于一切数据访问；格式非法的期望值不能充当判据）：
- --expected-revision 必须 40 位小写 hex；--expected-production-sha256 必须
  64 位小写 hex；apply/verify 两个 run_id 非空且互不相同。

预检（DuckDB connect/ATTACH 之前）：
- production / clone / parquet 均为常规文件且非符号链接；
- `os.path.samefile(production, clone)` 为假——覆盖同路径、符号链接、硬链接
  三种别名；无法判定（文件不存在等）按失败处理；不通过则跳过全部数据检查；
- production 基线 sha 开头核一次（结尾再核一次）。

收据深 schema（apply/verify 两份执行收据 + 其指向的独立子报告；缺字段/类型错/
空值/格式错逐项记 check False，不抛异常逃逸；后续一切访问只建立在验证通过的
结构上）：
- 父收据：kind/run_id/code_revision(40hex 且 == --expected-revision)/
  code_dirty==False/interpreter 非空/trade_date(ISO 真日期且 ==
  spec.window_end)/parent{swapped==True, rc==0(严格 int), run_id 一致}/
  backup{backup_path 非空, backup_sha256 64hex, run_id 一致}/
  child_report_error 键存在且为 null/child_report_path 非空；
- spec：code(股票代码格式且 == CODE 授权对象)/name 非空/四个日期 ISO 真日期且 window_start <
  main_fill_end < window_end、shell_date 界内/spec_version(302132-backfill-
  前缀且前缀后非空)/parquet_sha256(64hex)/gap_parallel、gap_parquet(非空、
  成员全 ISO 真日期、无重复、互不交、界内、不含 shell_date)/
  expected_total_rows(正 int)/stale_technical_dates(成员 ISO 真日期)/
  stale_window_keys(成员恰为二元日期组)/pinned_0911(恰 11 键、数值有限、
  turnover 允许 null)/pinned_technical_0911(恰 4 键、有限数值)/
  pinned_windows_0911(非空、成员恰为 [日期, 有限数, 有限数])/
  expected_window_counts(恰 5/10/20/60 四键、非负 int)/
  expected_technical_count(正 int)；
- 子报告：kind/ok==True（显式成功终态）/mode==本轮/run_id、code_revision、
  interpreter、trade_date 与父收据一致/spec_version==父 spec/code==父 spec/
  parquet_sha256(64hex)==父 spec/parallel_source_md5(32hex)/
  technical_rows==spec.expected_technical_count==technical_staged/
  window_counts==spec.expected_window_counts 且 window_rows==其和/
  protected_slices 恰三键且非负 int；
- 独立子报告文件：存在、可解析、与父收据嵌入 child_report 深比较相等；
- 跨轮绑定：apply/verify 两轮完整授权 spec 深比较相等（无白名单——「同一
  输入、同一合同下的幂等复验」以 spec 全等为前提）；
- 冻结输入身份：**每一轮分别** spec.parquet_sha256 == child.parquet_sha256
  == sha256(--parquet 实际文件)（三向，两轮各自成立）；
- 备份身份：备份文件存在且其 sha256 == 收据记录值；apply 收据的备份 sha 还
  必须 == --expected-production-sha256（备份=基线绑定）；
- --expected-old-receipt 路径=sha256（64hex，可重复）：旧收据逐份存在且哈希
  不变（不传则不声称检查旧收据）。

数据合同（clone vs 基线双向对照 + 独立 oracle；预检/参数/收据 schema 不过不
执行；任何读取/计算异常归入 data_checks_error 结构化 FAIL（rc=2），不裸逃逸）：
- 他股 fact_stock_daily 全列双向零差；目标股窗外无行；保留行（行数 =
  expected_total_rows − 授权键集数）全列（含 updated_at）逐字节相等；
- **并跑源表 fact_stock_daily_hithink 与除权源表 fact_stock_adjustment_hithink
  整表全列双向零差**（合同承诺写入器不触碰；oracle 输入独立性前提）；
- **parallel_source_md5 从基线重算**（与写入器同查询同序列化）并绑定两轮
  子报告记录值；
- 授权键集全字段 oracle：**并跑源行从基线（prod.）读**，parquet 段从冻结
  文件读——输出与结果库源表一起坏不能自证通过；
- 两派生表保护切片全列（含 calculated_at）双向零差；window 黄金三元组；
  expected_window_counts 与黄金三元组派生计数一致；technical 精确日期集且
  expected_technical_count 与市场历推导一致；目标日 technical/window 钉值；
  fact_market_daily 双向零差。

用法（生产执行后）：
python3 scripts/verify_302132_backfill_acceptance.py \
  --production <换库前备份.duckdb> --clone <canonical 生产库> \
  --parquet <冻结 parquet> --run-apply <run_id> --run-verify <run_id> \
  --expected-revision <合入修订 40hex> \
  --expected-production-sha256 <换库前生产 sha=收据 backup sha> \
  [--expected-old-receipt <路径>=<sha256>]... --output <新验收 JSON 路径>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import duckdb

CODE = "302132.SZ"
KIND = "repair-backfill-302132"
SPEC_VERSION_PREFIX = "302132-backfill-"
WINDOW_PERIODS = ("5", "10", "20", "60")
PROTECTED_SLICE_KEYS = ("fact_other", "tech_protected", "win_protected")
PINNED_0911_KEYS = ("stock_name", "close", "pre_close", "pct_chg", "amount",
                    "turnover", "source", "open", "high", "low", "volume")
PINNED_TECHNICAL_KEYS = ("ma26", "std26", "up_value", "deviation_pct")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX32 = re.compile(r"[0-9a-f]{32}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_CODE_RE = re.compile(r"\d{6}\.(SZ|SH|BJ)")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_date(v) -> bool:
    """ISO 格式且为真实日历日（2026-13-40 之类拒绝）。"""
    if not isinstance(v, str) or not _DATE.fullmatch(v):
        return False
    try:
        date.fromisoformat(v)
    except ValueError:
        return False
    return True


def _is_num(v) -> bool:
    """有限数值（JSON 可携带 NaN/Inf；bool 不是数值）。"""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:
        return False


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _validate_receipt(tag: str, r: dict, want_run: str, exp_rev: str) -> list:
    """父收据 + spec + 嵌入子报告的递归深 schema。返回违规字段路径列表（空=通过）。

    约束覆盖：必需键存在、成员类型、ISO 真日期、revision/hash 格式、数值有限
    性、非空集合及其成员、跨字段一致性、子报告显式成功终态（ok is True）。
    """
    bad: list[str] = []

    def req(cond: bool, field: str) -> None:
        if not cond:
            bad.append(field)

    # ── 父收据顶层 ────────────────────────────────────────────────
    req(r.get("kind") == KIND, "kind")
    req(isinstance(r.get("run_id"), str) and bool(r["run_id"])
        and r["run_id"] == want_run, "run_id")
    req(isinstance(r.get("code_revision"), str)
        and bool(_HEX40.fullmatch(r["code_revision"]))
        and r["code_revision"] == exp_rev, "code_revision")
    req(r.get("code_dirty") is False, "code_dirty")
    req(isinstance(r.get("interpreter"), str) and bool(r["interpreter"]),
        "interpreter")
    req(_is_date(r.get("trade_date")), "trade_date")
    par = r.get("parent")
    req(isinstance(par, dict), "parent")
    if isinstance(par, dict):
        req(par.get("swapped") is True, "parent.swapped")
        req(_is_int(par.get("rc")) and par["rc"] == 0, "parent.rc")
        req(par.get("run_id") == r.get("run_id"), "parent.run_id")
    b = r.get("backup")
    req(isinstance(b, dict), "backup")
    if isinstance(b, dict):
        req(isinstance(b.get("backup_path"), str) and bool(b["backup_path"]),
            "backup.backup_path")
        req(isinstance(b.get("backup_sha256"), str)
            and bool(_HEX64.fullmatch(b["backup_sha256"])),
            "backup.backup_sha256")
        req(b.get("run_id") == r.get("run_id"), "backup.run_id")
    req("child_report_error" in r and r["child_report_error"] is None,
        "child_report_error")
    req(isinstance(r.get("child_report_path"), str)
        and bool(r["child_report_path"]), "child_report_path")

    # ── spec（授权合同）───────────────────────────────────────────
    spec = r.get("spec")
    req(isinstance(spec, dict), "spec")
    if isinstance(spec, dict):
        req(isinstance(spec.get("code"), str)
            and bool(_CODE_RE.fullmatch(spec["code"]))
            and spec["code"] == CODE, "spec.code")
        req(isinstance(spec.get("name"), str) and bool(spec["name"]),
            "spec.name")
        for k in ("window_start", "window_end", "main_fill_end", "shell_date"):
            req(_is_date(spec.get(k)), f"spec.{k}")
        if all(_is_date(spec.get(k)) for k in
               ("window_start", "main_fill_end", "window_end")):
            req(spec["window_start"] < spec["main_fill_end"]
                < spec["window_end"], "spec.窗口日期序")
        if all(_is_date(spec.get(k)) for k in
               ("window_start", "main_fill_end", "shell_date")):
            req(spec["window_start"] <= spec["shell_date"]
                <= spec["main_fill_end"], "spec.shell_date:界内")
        if _is_date(spec.get("window_end")):
            req(r.get("trade_date") == spec["window_end"],
                "trade_date==spec.window_end")
        sv = spec.get("spec_version")
        req(isinstance(sv, str) and sv.startswith(SPEC_VERSION_PREFIX)
            and len(sv) > len(SPEC_VERSION_PREFIX), "spec.spec_version")
        req(isinstance(spec.get("parquet_sha256"), str)
            and bool(_HEX64.fullmatch(spec["parquet_sha256"])),
            "spec.parquet_sha256")
        gaps: dict[str, list] = {}
        for k in ("gap_parallel", "gap_parquet"):
            v = spec.get(k)
            req(isinstance(v, list) and bool(v)
                and all(_is_date(d) for d in v), f"spec.{k}")
            if isinstance(v, list) and all(_is_date(d) for d in v):
                req(len(set(v)) == len(v), f"spec.{k}:重复")
                gaps[k] = v
                if _is_date(spec.get("window_start")) \
                        and _is_date(spec.get("main_fill_end")):
                    req(all(spec["window_start"] <= d
                            <= spec["main_fill_end"] for d in v),
                        f"spec.{k}:界内")
        if "gap_parallel" in gaps and "gap_parquet" in gaps:
            req(not (set(gaps["gap_parallel"]) & set(gaps["gap_parquet"])),
                "spec.gap:交集")
            if _is_date(spec.get("shell_date")):
                req(spec["shell_date"] not in
                    (set(gaps["gap_parallel"]) | set(gaps["gap_parquet"])),
                    "spec.shell_date:与gap互斥")
        req(_is_int(spec.get("expected_total_rows"))
            and spec["expected_total_rows"] > 0, "spec.expected_total_rows")
        std = spec.get("stale_technical_dates")
        req(isinstance(std, list) and all(_is_date(d) for d in std),
            "spec.stale_technical_dates")
        swk = spec.get("stale_window_keys")
        req(isinstance(swk, list) and all(
            isinstance(pair, list) and len(pair) == 2
            and all(_is_date(d) for d in pair) for pair in swk),
            "spec.stale_window_keys")
        p9 = spec.get("pinned_0911")
        req(isinstance(p9, dict), "spec.pinned_0911")
        if isinstance(p9, dict):
            req(set(p9) == set(PINNED_0911_KEYS), "spec.pinned_0911:键集")
            if set(PINNED_0911_KEYS) <= set(p9):
                req(isinstance(p9["stock_name"], str)
                    and bool(p9["stock_name"]), "spec.pinned_0911.stock_name")
                req(isinstance(p9["source"], str) and bool(p9["source"]),
                    "spec.pinned_0911.source")
                req(p9["turnover"] is None or _is_num(p9["turnover"]),
                    "spec.pinned_0911.turnover")
                for k in ("close", "pre_close", "pct_chg", "amount",
                          "open", "high", "low", "volume"):
                    req(_is_num(p9[k]), f"spec.pinned_0911.{k}")
        tp = spec.get("pinned_technical_0911")
        req(isinstance(tp, dict), "spec.pinned_technical_0911")
        if isinstance(tp, dict):
            req(set(tp) == set(PINNED_TECHNICAL_KEYS),
                "spec.pinned_technical_0911:键集")
            for k in PINNED_TECHNICAL_KEYS:
                if k in tp:
                    req(_is_num(tp[k]), f"spec.pinned_technical_0911.{k}")
        wp = spec.get("pinned_windows_0911")
        req(isinstance(wp, list) and bool(wp), "spec.pinned_windows_0911")
        if isinstance(wp, list):
            for i, e in enumerate(wp):
                req(isinstance(e, list) and len(e) == 3 and _is_date(e[0])
                    and _is_num(e[1]) and _is_num(e[2]),
                    f"spec.pinned_windows_0911[{i}]")
        ewc = spec.get("expected_window_counts")
        req(isinstance(ewc, dict) and set(ewc) == set(WINDOW_PERIODS),
            "spec.expected_window_counts:键集")
        if isinstance(ewc, dict):
            for k in WINDOW_PERIODS:
                if k in ewc:
                    req(_is_int(ewc[k]) and ewc[k] >= 0,
                        f"spec.expected_window_counts.{k}")
        req(_is_int(spec.get("expected_technical_count"))
            and spec["expected_technical_count"] > 0,
            "spec.expected_technical_count")

    # ── 嵌入子报告（显式成功终态 + 与父/spec 交叉一致）──────────────
    ch = r.get("child_report")
    req(isinstance(ch, dict), "child_report")
    if isinstance(ch, dict):
        req(ch.get("kind") == KIND, "child.kind")
        req(ch.get("ok") is True, "child.ok")
        req(ch.get("mode") == tag, "child.mode")
        req(ch.get("run_id") == r.get("run_id"), "child.run_id")
        req(isinstance(ch.get("code_revision"), str)
            and bool(_HEX40.fullmatch(ch["code_revision"]))
            and ch.get("code_revision") == r.get("code_revision"),
            "child.code_revision")
        req(ch.get("code_dirty") is False, "child.code_dirty")
        req(isinstance(ch.get("interpreter"), str) and bool(ch["interpreter"])
            and ch.get("interpreter") == r.get("interpreter"),
            "child.interpreter")
        req(_is_date(ch.get("trade_date"))
            and ch.get("trade_date") == r.get("trade_date"),
            "child.trade_date")
        req(isinstance(ch.get("spec_version"), str) and bool(ch["spec_version"])
            and isinstance(spec, dict)
            and ch.get("spec_version") == spec.get("spec_version"),
            "child.spec_version")
        req(isinstance(spec, dict)
            and ch.get("code") == spec.get("code"), "child.code")
        req(isinstance(ch.get("parquet_sha256"), str)
            and bool(_HEX64.fullmatch(ch["parquet_sha256"]))
            and isinstance(spec, dict)
            and ch.get("parquet_sha256") == spec.get("parquet_sha256"),
            "child.parquet_sha256")
        req(isinstance(ch.get("parallel_source_md5"), str)
            and bool(_HEX32.fullmatch(ch["parallel_source_md5"])),
            "child.parallel_source_md5")
        tr = ch.get("technical_rows")
        req(_is_int(tr) and tr > 0 and isinstance(spec, dict)
            and tr == spec.get("expected_technical_count"),
            "child.technical_rows")
        req(_is_int(ch.get("technical_staged"))
            and ch["technical_staged"] == tr, "child.technical_staged")
        wc = ch.get("window_counts")
        req(isinstance(wc, dict) and bool(wc) and isinstance(spec, dict)
            and wc == spec.get("expected_window_counts"), "child.window_counts")
        wr = ch.get("window_rows")
        req(_is_int(wr) and wr > 0 and isinstance(wc, dict)
            and all(_is_int(v) for v in wc.values())
            and wr == sum(wc.values()), "child.window_rows")
        ps = ch.get("protected_slices")
        req(isinstance(ps, dict) and set(ps) == set(PROTECTED_SLICE_KEYS)
            and all(_is_int(v) and v >= 0 for v in ps.values()),
            "child.protected_slices")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--production", required=True, help="不可变基线库")
    ap.add_argument("--clone", required=True, help="换库后结果库")
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--run-apply", required=True)
    ap.add_argument("--run-verify", required=True)
    ap.add_argument("--expected-revision", required=True)
    ap.add_argument("--expected-production-sha256", required=True)
    ap.add_argument("--expected-old-receipt", action="append", default=[],
                    metavar="PATH=SHA256")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    out_path = Path(args.output)
    if out_path.exists():
        raise SystemExit(f"验收输出已存在（不可覆盖）: {out_path}")
    checks: list[dict] = []

    def check(name: str, ok: bool, detail="") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def sha_check(name: str, path: Path, want: str) -> str | None:
        """读文件哈希并比对；读异常归入同名 FAIL 检查，不裸逃逸。"""
        try:
            actual = _sha256(path)
        except OSError as exc:
            check(name, False, f"{type(exc).__name__}: {exc}")
            return None
        check(name, actual == want,
              {"expected": str(want)[:16], "actual": actual[:16]})
        return actual

    prod, clone, pq = (Path(args.production), Path(args.clone),
                       Path(args.parquet))

    # ── 参数格式（先于一切数据访问）────────────────────────────────
    check("args_expected_revision_format",
          bool(_HEX40.fullmatch(args.expected_revision)),
          args.expected_revision)
    check("args_expected_production_sha256_format",
          bool(_HEX64.fullmatch(args.expected_production_sha256)))
    check("args_run_ids_distinct_nonempty",
          bool(args.run_apply) and bool(args.run_verify)
          and args.run_apply != args.run_verify,
          {"apply": args.run_apply, "verify": args.run_verify})
    args_ok = all(c["ok"] for c in checks)

    # ── 预检：常规文件 + samefile 别名（含硬链接）────────────────────
    check("inputs_regular_files",
          all(p.is_file() and not p.is_symlink() for p in (prod, clone, pq)),
          [str(p) for p in (prod, clone, pq)
           if not (p.is_file() and not p.is_symlink())])
    try:
        same = os.path.samefile(prod, clone)
    except OSError as exc:
        same, same_err = None, f"{type(exc).__name__}: {exc}"
    else:
        same_err = ""
    check("clone_is_not_production_alias", same is False,
          same_err or {"production": os.path.realpath(prod),
                       "clone": os.path.realpath(clone)})
    preflight_ok = all(c["ok"] for c in checks[-2:])

    sha_check("production_sha256_before", prod, args.expected_production_sha256)

    # ── 收据：读取 + 深 schema + 身份 ──────────────────────────────
    receipts: dict[str, dict] = {}

    def _read_receipt(tag: str, run_id: str) -> None:
        p = Path(str(clone) + f".repair-backfill-execution.{run_id}.json")
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            check(f"receipt_{tag}_readable", False, f"{type(exc).__name__}: {exc}")
            return
        if not isinstance(raw, dict):
            check(f"receipt_{tag}_readable", False, type(raw).__name__)
            return
        check(f"receipt_{tag}_readable", True)
        receipts[tag] = raw

    _read_receipt("apply", args.run_apply)
    _read_receipt("verify", args.run_verify)
    check("receipts_apply_verify_present",
          set(receipts) == {"apply", "verify"}, sorted(receipts))

    schema_ok = set(receipts) == {"apply", "verify"}
    for tag, r in receipts.items():
        want = args.run_apply if tag == "apply" else args.run_verify
        bad = _validate_receipt(tag, r, want, args.expected_revision)
        check(f"receipt_{tag}_schema", not bad, bad[:12])
        schema_ok = schema_ok and not bad

    # 独立子报告文件：存在 + 可解析 + 与父收据嵌入子报告深比较相等
    for tag, r in receipts.items():
        crp = r.get("child_report_path")
        if not (isinstance(crp, str) and crp):
            continue
        try:
            ext = json.loads(Path(crp).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            check(f"receipt_{tag}_child_report_file", False,
                  f"{type(exc).__name__}: {exc}")
            continue
        check(f"receipt_{tag}_child_report_file",
              isinstance(ext, dict) and ext == r.get("child_report"),
              "与父收据嵌入子报告深比较")

    # 备份身份：文件存在 + sha 与收据一致；apply 备份还须 == 基线 sha
    for tag, r in receipts.items():
        b = r.get("backup")
        if not isinstance(b, dict):
            continue
        want = b.get("backup_sha256")
        bp = Path(str(b.get("backup_path", "")))
        if not (isinstance(want, str) and _HEX64.fullmatch(want)):
            check(f"backup_{tag}_identity", False, "收据 backup_sha256 非法")
            continue
        if not bp.is_file():
            check(f"backup_{tag}_identity", False, f"备份不存在: {bp}")
            continue
        sha_check(f"backup_{tag}_identity", bp, want)
    if isinstance(receipts.get("apply", {}).get("backup"), dict):
        check("backup_apply_matches_baseline",
              receipts["apply"]["backup"].get("backup_sha256")
              == args.expected_production_sha256,
              "apply 备份 sha == 基线 sha（换库前生产身份）")

    # 跨轮绑定：两轮完整授权 spec 深比较（无白名单）
    spec_a = receipts.get("apply", {}).get("spec")
    spec_v = receipts.get("verify", {}).get("spec")
    check("spec_alignment_apply_verify",
          isinstance(spec_a, dict) and isinstance(spec_v, dict)
          and spec_a == spec_v,
          "apply/verify 授权 spec 深比较（同输入同合同前提）")

    # 冻结输入身份：每一轮分别 spec == child == 实际文件（三向）
    actual_pq = None
    try:
        actual_pq = _sha256(pq)
        check("parquet_readable", True, actual_pq[:16])
    except OSError as exc:
        check("parquet_readable", False, f"{type(exc).__name__}: {exc}")
    for tag in ("apply", "verify"):
        r = receipts.get(tag, {})
        sp, ch = r.get("spec"), r.get("child_report")
        want = sp.get("parquet_sha256") if isinstance(sp, dict) else None
        ok = (isinstance(sp, dict) and isinstance(ch, dict)
              and isinstance(want, str) and bool(_HEX64.fullmatch(want))
              and ch.get("parquet_sha256") == want
              and actual_pq is not None and actual_pq == want)
        check(f"parquet_identity_{tag}", ok,
              {"spec": str(want)[:16] if isinstance(want, str) else None,
               "actual": actual_pq[:16] if actual_pq else None})

    # ── 旧收据保留（显式参数核验；未传则不声称检查）────────────────────
    for item in args.expected_old_receipt:
        if "=" not in item:
            check("old_receipt_arg_format", False, item)
            continue
        path_s, want_sha = item.rsplit("=", 1)
        op = Path(path_s)
        if not _HEX64.fullmatch(want_sha):
            check(f"old_receipt:{op.name}", False, "期望 sha 非 64hex")
            continue
        if not op.is_file():
            check(f"old_receipt:{op.name}", False, "不存在")
            continue
        sha_check(f"old_receipt:{op.name}", op, want_sha)

    # ── 数据合同（预检/参数/收据 schema 不过不执行，避免假阳性）────────
    spec = receipts.get("apply", {}).get("spec")
    spec_ok = (preflight_ok and args_ok and schema_ok
               and isinstance(spec, dict))
    if spec_ok:
        try:
            _data_checks(check, prod, clone, pq, spec, receipts)
        except Exception as exc:  # 读取/计算异常 → 结构化 FAIL，不裸逃逸
            check("data_checks_error", False, f"{type(exc).__name__}: {exc}")
    else:
        check("data_checks_executed", False,
              "预检/参数/收据 schema 未过，数据检查跳过（不发绿）")

    # ── 尾核：验收结束时基线 sha 仍等于期望（TOCTOU 闭环）─────────────
    sha_check("production_sha256_after", prod, args.expected_production_sha256)

    verdict = "PASS" if all(c["ok"] for c in checks) else "FAIL"
    payload = {"verdict": verdict,
               "expected_revision": args.expected_revision,
               "runs": {"apply": args.run_apply, "verify": args.run_verify},
               "checks": checks,
               "failed": [c["name"] for c in checks if not c["ok"]]}
    fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str)
                 + "\n")
    print(json.dumps({"verdict": verdict, "failed": payload["failed"],
                      "n": len(checks)}, ensure_ascii=False))
    return 0 if verdict == "PASS" else 2


def _data_checks(check, prod: Path, clone: Path, pq: Path,
                 spec: dict, receipts: dict) -> None:
    """数据合同。入口前结构已过深 schema，所有嵌套访问安全。

    oracle 输入纪律（六轮 P1-1）：并跑源行与源指纹一律从基线（prod.）读；
    结果库中的源表另做整表禁止变更比较——输出与源一起坏不能自证通过。
    """
    con = duckdb.connect(str(clone), read_only=True)
    try:
        con.execute(f"ATTACH '{prod}' AS prod (READ_ONLY)")

        def xa(table: str, where: str) -> list[int]:
            cols = [r[1] for r in con.execute(
                f"PRAGMA table_info('{table}')").fetchall()]
            sel = ", ".join(cols)
            fwd = con.execute(
                f"SELECT COUNT(*) FROM (SELECT {sel} FROM prod.{table} {where} "
                f"EXCEPT ALL SELECT {sel} FROM {table} {where})").fetchone()[0]
            rev = con.execute(
                f"SELECT COUNT(*) FROM (SELECT {sel} FROM {table} {where} "
                f"EXCEPT ALL SELECT {sel} FROM prod.{table} {where})"
            ).fetchone()[0]
            return [fwd, rev]

        d0, d1 = spec["window_start"], spec["window_end"]
        write_keys = sorted(set(spec["gap_parallel"]) | set(spec["gap_parquet"])
                            | {spec["shell_date"]})
        marks = ",".join(f"'{d}'" for d in write_keys)
        check("fact_other_stocks_allcols",
              xa("fact_stock_daily", f"WHERE stock_ts_code <> '{CODE}'")
              == [0, 0])
        expected_retained = spec["expected_total_rows"] - len(write_keys)
        before = con.execute(
            f"SELECT * FROM prod.fact_stock_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date NOT IN ({marks}) ORDER BY trade_date").fetchall()
        after = con.execute(
            f"SELECT * FROM fact_stock_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date NOT IN ({marks}) ORDER BY trade_date").fetchall()
        check("retained_rows_full_column_identical",
              before == after and len(after) == expected_retained,
              {"rows": len(after), "expected": expected_retained})
        oor = con.execute(
            f"SELECT COUNT(*) FROM fact_stock_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date NOT BETWEEN '{d0}' AND '{d1}'").fetchone()[0]
        check("target_outside_window_none", oor == 0, oor)

        # 源表禁止变更（整表；合同承诺写入器不触碰这两张输入表）
        check("hithink_source_untouched",
              xa("fact_stock_daily_hithink", "") == [0, 0])
        check("hithink_adjustment_untouched",
              xa("fact_stock_adjustment_hithink", "") == [0, 0])

        # 源指纹：从基线重算（与写入器同查询同序列化），绑定两轮子报告记录值
        prev_row = con.execute(
            "SELECT MAX(trade_date) FROM prod.fact_market_daily "
            "WHERE trade_date < ?", [d0]).fetchone()
        prev_day = str(prev_row[0]) if prev_row and prev_row[0] else None
        if prev_day is None:
            check("parallel_source_md5_binding", False,
                  "基线市场历缺窗口前交易日")
        else:
            src_rows = con.execute(
                "SELECT trade_date, open, high, low, close, volume, turnover "
                "FROM prod.fact_stock_daily_hithink WHERE stock_ts_code=? "
                "AND adjusted='none' AND trade_date BETWEEN ? AND ? "
                "ORDER BY 1",
                [CODE, prev_day, max(spec["gap_parallel"])]).fetchall()
            recomputed = hashlib.md5(json.dumps(
                [tuple(str(c) for c in r) for r in src_rows]).encode()
            ).hexdigest()
            md5s = {t: receipts[t]["child_report"].get("parallel_source_md5")
                    for t in ("apply", "verify")}
            check("parallel_source_md5_binding",
                  recomputed == md5s["apply"] == md5s["verify"],
                  {"recomputed": recomputed, "rows": len(src_rows),
                   "apply": md5s["apply"], "verify": md5s["verify"]})

        # 授权键集全字段 oracle：并跑源行从基线（prod.）读，parquet 段从冻结文件读
        src = {str(r[0]): r[1:] for r in con.execute(f"""
          SELECT trade_date, open, high, low, close, volume, turnover
          FROM prod.fact_stock_daily_hithink
          WHERE stock_ts_code='{CODE}' AND adjusted='none'
          UNION ALL
          SELECT CAST(to_timestamp(date_ms/1000) AS DATE), open_price, high_price,
                 low_price, close_price, volume, turnover
          FROM read_parquet('{pq}')
          WHERE thscode='{CODE}' AND currency='CNY' AND interval='1d'
            AND adjusted='none'""").fetchall()}
        cal = [str(r[0]) for r in con.execute(
            "SELECT DISTINCT trade_date FROM prod.fact_market_daily "
            "WHERE trade_date BETWEEN '2026-06-01' AND ? ORDER BY 1",
            [d1]).fetchall()]
        rows = con.execute(
            f"SELECT trade_date, stock_name, open, high, low, close, pre_close,"
            f" pct_chg, amount, turnover, volume, source FROM fact_stock_daily "
            f"WHERE stock_ts_code='{CODE}' AND trade_date IN ({marks})").fetchall()
        bad = []
        for r in rows:
            d = str(r[0])
            s = src[d]
            pred = cal[cal.index(d) - 1]
            pre = float(Decimal(str(float(src[pred][3]))).quantize(
                Decimal("0.01")))
            pct = float(((Decimal(str(r[5])).quantize(Decimal("0.0001"))
                          / Decimal(str(pre)).quantize(Decimal("0.01")) - 1) * 100
                         ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            amt = float((Decimal(str(float(s[5]))).quantize(Decimal("0.01"))
                         / Decimal(10**8)).quantize(Decimal("0.0001"),
                                                   rounding=ROUND_HALF_UP))
            vol = float((Decimal(str(float(s[4]))).quantize(Decimal("1"))
                         / Decimal(100)).quantize(Decimal("1"),
                                                 rounding=ROUND_HALF_UP))
            exp_label = ("hithink:daily-k-10d:backfill-302132-20260914"
                         if d in spec["gap_parquet"]
                         else "hithink:daily-k:backfill-302132-20260914")
            ok = (r[1] == spec["name"] and r[2] == float(s[0])
                  and r[3] == float(s[1]) and r[4] == float(s[2])
                  and r[5] == float(s[3]) and abs(r[6] - pre) < 1e-9
                  and abs(r[7] - pct) < 1e-9 and abs(r[8] - amt) < 1e-9
                  and r[9] is None and abs(r[10] - vol) < 1e-9
                  and r[11] == exp_label
                  and all(math.isfinite(float(v)) for v in r[2:6]))
            if not ok:
                bad.append(d)
        check("keyset_fullfield_oracle",
              len(rows) == len(write_keys) and not bad,
              {"rows": len(rows), "keys": len(write_keys), "bad": bad[:5]})

        w_t = (f"WHERE stock_ts_code <> '{CODE}' OR trade_date NOT BETWEEN "
               f"'{d0}' AND '{d1}'")
        w_w = (f"WHERE stock_ts_code <> '{CODE}' OR as_of_date NOT BETWEEN "
               f"'{d0}' AND '{d1}'")
        check("technical_protected_allcols",
              xa("feature_stock_technical_daily", w_t) == [0, 0])
        check("window_protected_allcols",
              xa("feature_stock_window", w_w) == [0, 0])
        cal64 = [d for d in cal if d >= d0]
        golden = set()
        for i, a in enumerate(cal64):
            for p_ in (5, 10, 20, 60):
                if i >= p_:
                    golden.add((a, cal64[i - p_], a))
        actual = {(str(r[0]), str(r[1]), str(r[2])) for r in con.execute(
            f"SELECT as_of_date, start_date, end_date FROM feature_stock_window "
            f"WHERE stock_ts_code='{CODE}' AND as_of_date BETWEEN '{d0}' "
            f"AND '{d1}'").fetchall()}
        check("window_golden_triples", actual == golden,
              {"actual": len(actual), "golden": len(golden)})
        idx = {d: i for i, d in enumerate(cal64)}
        golden_counts = {p: 0 for p in WINDOW_PERIODS}
        for a, s, _e in golden:
            golden_counts[str(idx[a] - idx[s])] += 1
        check("expected_window_counts_match_golden",
              golden_counts == spec["expected_window_counts"],
              {"golden": golden_counts, "spec": spec["expected_window_counts"]})
        tech_dates = [str(r[0]) for r in con.execute(
            f"SELECT trade_date FROM feature_stock_technical_daily "
            f"WHERE stock_ts_code='{CODE}' AND trade_date BETWEEN '{d0}' "
            f"AND '{d1}' ORDER BY 1").fetchall()]
        check("technical_exact_set", tech_dates == cal64[25:], len(tech_dates))
        check("expected_technical_count_matches_calendar",
              spec["expected_technical_count"] == len(cal64[25:]),
              {"spec": spec["expected_technical_count"],
               "calendar": len(cal64[25:])})
        tp = spec["pinned_technical_0911"]
        t9 = con.execute(
            f"SELECT ma26, std26, up_value, deviation_pct "
            f"FROM feature_stock_technical_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date='{d1}'").fetchone()
        check("pinned_technical_target_day",
              t9 is not None and all(
                  abs(a - b) < 1e-9 for a, b in zip(
                      t9, (tp["ma26"], tp["std26"], tp["up_value"],
                           tp["deviation_pct"]))), t9)
        w9 = con.execute(
            f"SELECT start_date, interval_gain_pct, avg_amount "
            f"FROM feature_stock_window WHERE stock_ts_code='{CODE}' "
            f"AND as_of_date='{d1}' ORDER BY start_date").fetchall()
        pins = spec["pinned_windows_0911"]
        check("pinned_windows_target_day",
              len(w9) == len(pins) and all(
                  str(r[0]) == p[0] and abs(r[1] - p[1]) < 1e-9
                  and abs(r[2] - p[2]) < 1e-9 for r, p in zip(w9, pins)))
        check("market_daily_untouched", xa("fact_market_daily", "") == [0, 0])
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
