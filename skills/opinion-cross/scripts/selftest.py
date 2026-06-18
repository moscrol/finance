#!/usr/bin/env python3
"""opinion-cross 零凭证 selftest：合成 events + outcomes，验证盘面兑现维(b) 接线。

照搬 theme-fermentation-tracer/scripts/selftest.py 的结构（合成输入 → subprocess
跑目标脚本 → 断言 RC=0 + 关键串命中 → 打印 [PASS]/[FAIL]）。本测试**不联网、不读飞书/
iFinD/DuckDB**：只在临时目录里写两份 JSONL（opinion-events.jsonl + outcomes.jsonl），
然后跑 consensus_staging.py / pan_realize.py，校验：

  1. py_compile 两个核心脚本通过；
  2. 默认同目录 outcomes.jsonl 自动接（无 --outcomes 也接）→ stage/board 出「盘面兑现(b)」列、footer「已接」；
  3. 「一致认同」标的把盘面判定 slot 进判定理由（冲高透支 → 透支区）；
  4. --outcomes 指向不存在文件 → 不接，该列/footer 退回「待接」（存在才接）；
  5. pan_realize.py 独立视图跑通。

用法：python3 skills/opinion-cross/scripts/selftest.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGING = HERE / "consensus_staging.py"
PAN_REALIZE = HERE / "pan_realize.py"


def _event(report_date, source_id, target, concept, *, hard=None, soft=None,
           catalysts=None, tier="Tier 2") -> dict:
    """构造一条最小可用「观点事件」行（字段对齐 opinion_store schema）。"""
    return {
        "event_id": f"st-{source_id}-{report_date}-{target}",
        "report_date": report_date,
        "source": source_id,
        "source_id": source_id,
        "report_title": "",
        "term": "测题",
        "target": target,
        "concept": concept,
        "stance": "看多",
        "hardness": "硬证据" if hard else "软推演",
        "hard_evidence": hard or [],
        "soft_claims": soft or [],
        "catalysts": catalysts or [],
        "resonance_tier": tier,
        "mention_count": 1,
    }


def _outcome(report_date, target, concept, *, excess_5d, ret_5d, interval_max_ret,
             peak_day, post_peak_dd) -> dict:
    """构造一条最小可用 outcomes 行（字段对齐 build_outcomes/price_lib.fwd_metrics）。"""
    return {
        "event_id": f"oc-{target}-{report_date}",
        "report_date": report_date,
        "source": "src-x",
        "source_id": "src-x",
        "target": target,
        "code": "sz000001",
        "concept": concept,
        "term": "测题",
        "stance": "看多",
        "benchmark": "sh000300",
        "ret_5d": ret_5d,
        "ret_5d_complete": True,
        "excess_5d": excess_5d,
        "interval_max_ret": interval_max_ret,
        "peak_day": peak_day,
        "post_peak_dd": post_peak_dd,
    }


def build_events(path: Path) -> None:
    """样龙甲：5 来源跨 4 日 + 硬证据 → 一致认同；样补乙：单来源软料 → 观察池。"""
    events = [
        _event("2026-06-01", "src-001", "样龙甲", "测题A", hard=["签订10亿元供货合同"]),
        _event("2026-06-02", "src-002", "样龙甲", "测题A", soft=["看好放量"]),
        _event("2026-06-03", "src-003", "样龙甲", "测题A", soft=["首选标的"]),
        _event("2026-06-03", "src-004", "样龙甲", "测题A", soft=["弹性大"]),
        _event("2026-06-04", "src-005", "样龙甲", "测题A", soft=["空间可观"]),
        _event("2026-06-02", "src-006", "样补乙", "测题B", soft=["有望受益"], tier="Tier 3"),
    ]
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
                    encoding="utf-8")


def build_outcomes(path: Path) -> None:
    """样龙甲：区间冲高+大幅回吐 → 冲高透支；样补乙：明显超额+持稳 → 已兑现持稳。"""
    outs = [
        _outcome("2026-06-01", "样龙甲", "测题A", excess_5d=3.0, ret_5d=4.0,
                 interval_max_ret=20.0, peak_day=2, post_peak_dd=-15.0),
        _outcome("2026-06-03", "样龙甲", "测题A", excess_5d=2.0, ret_5d=3.0,
                 interval_max_ret=22.0, peak_day=3, post_peak_dd=-14.0),
        _outcome("2026-06-02", "样补乙", "测题B", excess_5d=8.0, ret_5d=9.0,
                 interval_max_ret=9.0, peak_day=5, post_peak_dd=-3.0),
    ]
    path.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in outs) + "\n",
                    encoding="utf-8")


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


def main() -> int:
    checks: dict[str, bool] = {}

    # 0) py_compile 两个核心脚本
    comp = _run(["-m", "py_compile", str(STAGING), str(PAN_REALIZE)])
    checks["py_compile consensus_staging + pan_realize 通过"] = comp.returncode == 0
    if comp.returncode != 0:
        print(comp.stderr)

    with tempfile.TemporaryDirectory(prefix="opinion-cross-selftest-") as td:
        d = Path(td)
        events = d / "opinion-events.jsonl"
        outcomes = d / "outcomes.jsonl"
        build_events(events)
        build_outcomes(outcomes)

        # 1) 默认同目录 outcomes.jsonl 自动接（不传 --outcomes）
        a = _run([str(STAGING), "--store", str(events), "--view", "all"])
        checks["consensus_staging --view all RC=0（默认同目录 outcomes 自动接）"] = a.returncode == 0
        rep = a.stdout
        checks["stage/board 出现「盘面兑现(b)」列"] = "盘面兑现(b)" in rep
        checks["盘面判定「冲高透支」出现（样龙甲/测题A）"] = "冲高透支" in rep
        checks["盘面判定「已兑现持稳」出现（样补乙/测题B）"] = "已兑现持稳" in rep
        checks["footer 改为「已接」（盘面兑现维已接）"] = "盘面兑现(b)」维已接" in rep
        checks["一致认同把盘面判定 slot 进理由（盘面兑现：冲高透支）"] = "盘面兑现：冲高透支" in rep
        if a.returncode != 0:
            print(a.stderr)

        # 2) --outcomes 指向不存在 → 不接，退回「待接」（存在才接）
        b = _run([str(STAGING), "--store", str(events),
                  "--outcomes", str(d / "nope.jsonl"), "--view", "stage"])
        checks["缺 outcomes 时 RC=0（存在才接，缺则照旧）"] = b.returncode == 0
        checks["未接时该列/footer 退回「待接」"] = "待接" in b.stdout
        if b.returncode != 0:
            print(b.stderr)

        # 3) pan_realize.py 独立视图
        c = _run([str(PAN_REALIZE), "--outcomes", str(outcomes), "--by", "concept"])
        checks["pan_realize --by concept RC=0"] = c.returncode == 0
        checks["pan_realize 输出「盘面兑现维」+「冲高透支」"] = (
            "盘面兑现维" in c.stdout and "冲高透支" in c.stdout
        )
        if c.returncode != 0:
            print(c.stderr)

    failed = 0
    for label, ok in checks.items():
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            failed += 1
    print(f"\n{len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
