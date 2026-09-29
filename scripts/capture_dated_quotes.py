#!/usr/bin/env python3
"""采一份「收盘后封存的腾讯报价」——合同 1（2026-09-29 用户接受）名称来源的生产件。

为什么
------
``scripts/audit_dated_quote_capture.py`` 负责验、``skills/duckdb-backfill/scripts/
attach_capture_names.py`` 负责用，但仓里一直没有「采」的那一步：新股（如 920201.BJ）
在同花顺桥里没有此前的名字，没有当日封存捕获就只能被 ``InvalidStockName`` 拦下。

这份脚本只做采集与封存，不碰任何数据库写入：

1. **只能采当天、只能在收盘后**：目标日必须等于北京时间今天，且此刻 ≥ 15:00。历史日
   没有合规来源就是没有——不能拿今天的报价去冒充过去某天的名字。
2. **先探后封**：第一轮逐批请求整个声明范围，用验证器同一套 ``parse_quotes`` 逐行判定；
   停牌（报价时间戳不是今天收盘后）、代码不存在、字段不自洽的代码记进 ``excluded``
   并写明原因，**不进入封存范围**（验证器对范围内任何一条坏报价都会整份拒绝）。
3. **封存**：第二轮只请求合格代码，原样落盘响应字节（``batch-0001.raw``…），逐批记
   sha256；若某批在封存轮里又出现不合格行，剔除该代码后整批重取（最多 3 次）。
4. **自验**：写完立刻用 ``audit_capture`` 重放整份捕获；通过后文件改 0444、目录 0555，
   打印 receipt sha256（``attach_capture_names`` 可钉住它）。目录已存在一律拒跑。

用法::

    # 收盘后（≥15:00 CST）
    .venv-workbench/bin/python scripts/capture_dated_quotes.py \\
        --from-duckdb db/market_feature_store.duckdb --extra-codes 920201.BJ \\
        --out-dir db/quote-captures/tencent/2026-09-29

    # 任意时刻只探不封（不写文件），用来检查范围与接口
    ... --probe

退出码：0 成功；2 拒跑/失败（没有留下半份捕获——失败时目录会被整体移到 ``*.failed-*``）。
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable, Iterable
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_dated_quote_capture import CODE, QUOTE, audit_capture, parse_quotes  # noqa: E402

CST = ZoneInfo("Asia/Shanghai")
NAME_SOURCE = "tencent:captured-dated-quote"
ENDPOINT = "https://qt.gtimg.cn/q="
DEFAULT_BATCH = 60
SEAL_ATTEMPTS = 3

# fetch(symbols) -> (http_status, raw_bytes)
Fetcher = Callable[[list[str]], tuple[int, bytes]]


class CaptureRefused(RuntimeError):
    """前置条件不满足或无法得到一份可验证的捕获；不会留下可被误用的目录。"""


def symbol_of(code: str) -> str:
    plain, market = code.split(".")
    return market.lower() + plain


def code_of(symbol: str) -> str:
    return symbol[2:] + "." + symbol[:2].upper()


def http_fetch(symbols: list[str], *, timeout: float = 15.0, retries: int = 3) -> tuple[int, bytes]:
    request = urllib.request.Request(ENDPOINT + ",".join(symbols),
                                     headers={"User-Agent": "Mozilla/5.0"})
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return int(response.status), response.read()
        except Exception as exc:  # 网络抖动：退避重试，最终失败交给调用方
            last = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise CaptureRefused(f"fetch failed after {retries + 1} attempts: {type(last).__name__}: {last}")


def classify(raw: bytes, requested: Iterable[str], trade_date: date) -> tuple[dict[str, bytes], dict[str, str]]:
    """把一批响应拆成逐只：合格行（原样字节）与不合格原因。用验证器同一口径判定。"""
    requested = list(requested)
    good: dict[str, bytes] = {}
    bad: dict[str, str] = {}
    seen: set[str] = set()
    try:
        text = raw.decode("gbk")
    except UnicodeDecodeError:
        return {}, {code: "undecodable_response" for code in requested}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = QUOTE.fullmatch(stripped)
        if match is None:
            continue  # 例如 v_pv_none_match="1"; ——无法归属，下面按「无报价」处理
        code = code_of(match.group(1))
        if code in seen:
            bad[code] = "duplicate_in_response"
            good.pop(code, None)
            continue
        seen.add(code)
        try:
            parse_quotes((stripped + "\n").encode("gbk"), trade_date)
        except ValueError as exc:
            message = str(exc)
            fields = match.group(2).split("~")
            stamp = fields[30] if len(fields) > 30 else ""
            if "after market close" in message:
                bad[code] = ("not_after_close" if stamp[:8] == trade_date.strftime("%Y%m%d")
                             else f"stale_quote:{stamp[:8] or 'none'}")
            else:
                bad[code] = "invalid_quote:" + message
            continue
        good[code] = (stripped + "\n").encode("gbk")
    for code in requested:
        if code not in good and code not in bad:
            bad[code] = "no_quote"
    for code in list(good):
        if code not in requested:
            good.pop(code)
            bad.setdefault(code, "unrequested_in_response")
    return good, bad


def chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def probe(codes: list[str], trade_date: date, fetch: Fetcher, batch_size: int
          ) -> tuple[list[str], dict[str, str]]:
    eligible: list[str] = []
    excluded: dict[str, str] = {}
    for batch in chunks(codes, batch_size):
        status, raw = fetch([symbol_of(c) for c in batch])
        if status != 200:
            excluded.update({c: f"http_{status}" for c in batch})
            continue
        good, bad = classify(raw, batch, trade_date)
        eligible.extend(c for c in batch if c in good)
        excluded.update(bad)
    return eligible, excluded


def seal(out_dir: Path, codes: list[str], trade_date: date, fetch: Fetcher, batch_size: int,
         excluded: dict[str, str]) -> list[dict]:
    batches: list[dict] = []
    for pending in chunks(codes, batch_size):
        for attempt in range(1, SEAL_ATTEMPTS + 1):
            if not pending:
                break
            status, raw = fetch([symbol_of(c) for c in pending])
            if status == 200:
                good, bad = classify(raw, pending, trade_date)
                if not bad:
                    try:
                        parsed = parse_quotes(raw, trade_date)
                    except ValueError as exc:  # 逐行都合格但整批不合格：不应发生，保守拒绝
                        bad = {c: "batch_rejected:" + str(exc) for c in pending}
                    else:
                        if set(parsed) == set(pending):
                            name = f"batch-{len(batches) + 1:04d}.raw"
                            with (out_dir / name).open("xb") as handle:
                                handle.write(raw)
                            batches.append({"file": name, "sha256": hashlib.sha256(raw).hexdigest(),
                                            "codes": list(pending), "http_status": status,
                                            "fetched_at": datetime.now(CST).isoformat(timespec="seconds"),
                                            "attempt": attempt})
                            pending = []
                            break
                        bad = {c: "identity_mismatch" for c in pending}
                # 剔除不合格代码后重取整批；原因记进 excluded
                for code, reason in bad.items():
                    if code in pending:
                        excluded[code] = "seal_pass:" + reason
                pending = [c for c in pending if c not in bad]
            elif attempt == SEAL_ATTEMPTS:
                raise CaptureRefused(f"seal batch kept returning HTTP {status}")
        if pending:
            raise CaptureRefused(f"could not seal batch after {SEAL_ATTEMPTS} attempts: {pending[:5]}…")
    return batches


def load_universe(args: argparse.Namespace) -> tuple[list[str], list[dict]]:
    codes: set[str] = set()
    sources: list[dict] = []
    if args.codes_file:
        values = [line.strip() for line in args.codes_file.read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.startswith("#")]
        codes.update(values)
        sources.append({"kind": "codes_file", "path": str(args.codes_file), "count": len(values)})
    if args.from_duckdb:
        import duckdb  # 只读连接；不写库

        con = duckdb.connect(str(args.from_duckdb), read_only=True)
        try:
            for table in ("fact_stock_daily", "fact_stock_daily_hithink"):
                row = con.execute(f"SELECT max(trade_date) FROM {table}").fetchone()
                if not row or row[0] is None:
                    continue
                values = [r[0] for r in con.execute(
                    f"SELECT DISTINCT stock_ts_code FROM {table} WHERE trade_date = ?", [row[0]]
                ).fetchall()]
                codes.update(values)
                sources.append({"kind": "duckdb", "path": str(args.from_duckdb), "table": table,
                                "trade_date": str(row[0])[:10], "count": len(values)})
        finally:
            con.close()
    if args.extra_codes:
        values = [c.strip() for c in args.extra_codes.split(",") if c.strip()]
        codes.update(values)
        sources.append({"kind": "extra_codes", "codes": values})
    bad = sorted(c for c in codes if not CODE.fullmatch(c))
    if bad:
        raise CaptureRefused(f"invalid code(s) in universe: {bad[:10]}")
    if not codes:
        raise CaptureRefused("empty universe: pass --codes-file / --from-duckdb / --extra-codes")
    return sorted(codes), sources


def check_clock(trade_date: date, now: datetime) -> None:
    local = now.astimezone(CST)
    if trade_date != local.date():
        raise CaptureRefused(f"target {trade_date} is not today ({local.date()} CST): "
                             "a capture can only describe the day it was taken")
    if (local.hour, local.minute) < (15, 0):
        raise CaptureRefused(f"now {local:%H:%M} CST is before 15:00 close")


def seal_permissions(out_dir: Path) -> None:
    for path in out_dir.iterdir():
        os.chmod(path, 0o444)
    os.chmod(out_dir, 0o555)


def run(args: argparse.Namespace, *, fetch: Fetcher = http_fetch,
        now: Callable[[], datetime] = lambda: datetime.now(CST)) -> dict:
    trade_date = args.target_date or now().astimezone(CST).date()
    codes, sources = load_universe(args)
    if not args.probe:
        check_clock(trade_date, now())
        if args.out_dir is None:
            raise CaptureRefused("--out-dir is required unless --probe")
        if args.out_dir.exists() or args.out_dir.is_symlink():
            raise CaptureRefused(f"{args.out_dir} already exists; evidence is never overwritten")
    started = now().astimezone(CST)
    eligible, excluded = probe(codes, trade_date, fetch, args.batch_size)
    summary = {"target_date": trade_date.isoformat(), "requested_code_count": len(codes),
               "eligible_code_count": len(eligible),
               "excluded_reasons": dict(Counter(r.split(":")[0] for r in excluded.values())),
               "universe_sources": sources}
    if args.probe:
        summary.update({"probe_only": True, "files_written": False,
                        "excluded_sample": dict(sorted(excluded.items())[:20])})
        return summary
    if not eligible:
        raise CaptureRefused("no eligible quote after close; nothing to seal")
    args.out_dir.parent.mkdir(parents=True, exist_ok=True)
    args.out_dir.mkdir()
    try:
        batches = seal(args.out_dir, eligible, trade_date, fetch, args.batch_size, excluded)
        sealed = [c for b in batches for c in b["codes"]]
        receipt = {"target_date": trade_date.isoformat(), "name_source": NAME_SOURCE,
                   "endpoint": ENDPOINT, "codes": sealed, "captured_code_count": len(sealed),
                   "requested_code_count": len(codes), "universe_sources": sources,
                   "excluded": dict(sorted(excluded.items())),
                   "started_at": started.isoformat(timespec="seconds"),
                   "finished_at": now().astimezone(CST).isoformat(timespec="seconds"),
                   "tool": "scripts/capture_dated_quotes.py", "batches": batches}
        with (args.out_dir / "receipt.json").open("x", encoding="utf-8") as handle:
            json.dump(receipt, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        audit = audit_capture(args.out_dir, trade_date)
        with (args.out_dir / "audit.json").open("x", encoding="utf-8") as handle:
            json.dump(audit, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        receipt_sha = hashlib.sha256((args.out_dir / "receipt.json").read_bytes()).hexdigest()
        seal_permissions(args.out_dir)
    except BaseException:
        failed = args.out_dir.with_name(f"{args.out_dir.name}.failed-{int(time.time())}")
        args.out_dir.rename(failed)
        raise
    summary.update({"capture_dir": str(args.out_dir), "receipt_sha256": receipt_sha,
                    "captured_code_count": len(sealed), "batches": len(batches),
                    "excluded_reasons": dict(Counter(r.split(":")[0] for r in excluded.values())),
                    "audit_capture_validated": audit["capture_validated"],
                    "database_writes": False})
    return summary


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target-date", type=date.fromisoformat,
                        help="默认北京时间今天；只能是今天")
    parser.add_argument("--out-dir", type=Path, help="新目录；已存在则拒跑")
    parser.add_argument("--codes-file", type=Path, help="每行一个 ts_code（600000.SH）")
    parser.add_argument("--from-duckdb", type=Path,
                        help="只读打开，取 fact_stock_daily / fact_stock_daily_hithink 最新一日的代码")
    parser.add_argument("--extra-codes", help="逗号分隔，补新股等库里还没有的代码")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--probe", action="store_true", help="只探不封，不写任何文件")
    args = parser.parse_args(argv)
    if not 1 <= args.batch_size <= 80:
        parser.error("--batch-size must be within 1..80")
    return args


def main(argv: list[str] | None = None) -> int:
    try:
        result = run(parse_args(argv))
    except (CaptureRefused, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"captured": False, "error_type": type(exc).__name__, "error": str(exc),
                          "database_writes": False}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
