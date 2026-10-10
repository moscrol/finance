#!/usr/bin/env python3
"""视角可消费性审计：我的视角里的每一条判据，河现在接得住几条。

    python3 scripts/audit_perspective_consumability.py --perspective kol_fengyuan
    python3 scripts/audit_perspective_consumability.py --perspective example --user me
    python3 scripts/audit_perspective_consumability.py --all --json

## 为什么要这个工具

视角画像（``perspective_lab``）与时间长河（``river``）**互不引用**——实测双向 0 处 import。
画像里是散文（``market_lenses`` 的 name / description 字符串），河里是 7 个可判标签，
中间没有任何映射。于是每次要用「风远视角」读一段行情，agent 都得临场把散文翻译成
标签组合：翻译结果不确定、不可复算、不可回溯，也没人能说出「这次翻译漏了哪条判据」。

本工具不替你做那个翻译——它**把差距变成一个可以反复测量的数**：

    每条判据落在哪一档？
      ✅ 可判       河的可判标签里有对应的词，能直接写进情景树的分枝条件
      🟡 有料无词   河发了原始字段，但没有标签；agent 每次都要自己从原料重推
      🟠 有库无河   库里有这张表/这个列，但六轨一个都不读，透过河看不见
      ❌ 无数据     库里就没有
      🔵 架构已有   不是数据问题；情景树 / 规则 DSL 已经实现了这个形状

## 为什么判定要靠人工映射表而不是自动匹配

试过关键词匹配，不可用：「拥挤度」要对上 ``opinion_stage == '拥挤'``、
「市场场景」要对上 ``market_stage``、「先定周期位置」要对上 ``lifecycle_stage``——
全是语义对应，字面毫无交集。而字面能匹配上的（「涨幅收敛」vs ``pct_chg``）恰恰
是最容易判错的那种：有原始字段 ≠ 有判据。

所以映射表是**人工写的、带署名的、要你点头的**（``docs/learning/perspective-river-map/``）。
工具只负责：① 检查映射表有没有漏掉画像里的判据；② 按映射表核对河此刻的实际能力；
③ 把结果变成一行可比的读数。映射表写错了，工具不会救你——但至少错在明处、有版本、能复核。

## 输出的那个数怎么用

不要当「完成度」看。它真正的用处是**排工作的优先级**：

- 🟡 这一档最便宜。原料已经在河里发出来了，缺的只是一个标签名 + 一次口径确认。
  本仓 2026-10-07 把可判词汇从 4 扩到 7，走的就是这一档（见
  ``docs/verification/2026-10-07-river-label-binding-expansion.md``）。
- 🟠 要改的是取数层：六轨该不该读这张表，是设计决定不是工程量。
- ❌ 要接新数据源，最贵，而且很多（盘中、产业链）根本不在本仓范围内——
  这一档数字高不丢人，它只是在说「这条判据不该指望河来回答」。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MAP_DIR = REPO_ROOT / "docs" / "learning" / "perspective-river-map"

VERDICTS = ("judgeable", "raw_only", "in_db_not_in_river", "absent", "architecture")
MARK = {
    "judgeable": "✅ 可判",
    "raw_only": "🟡 有料无词",
    "in_db_not_in_river": "🟠 有库无河",
    "absent": "❌ 无数据",
    "architecture": "🔵 架构已有",
}


# --------------------------------------------------------------------------- #
# 河此刻的实际能力（现查，不抄）
# --------------------------------------------------------------------------- #
def river_capability(db_path: str | None, entity: str, as_of: str | None) -> dict[str, Any]:
    """河现在能判什么、能发什么字段、库里有什么列。

    三者都**现查**：标签白名单从 ``river_derive`` 取，发出的字段从一片真切片上数，
    库里的列从 ``schema.sql`` 读。任何一处抄成常量，这份审计就会在河变了之后继续报旧数。
    """
    from intelligence.services import river_derive as rd

    labels = set(rd.SLICE_EVALUABLE_LABELS)

    emitted: set[str] = set()
    slice_note = ""
    if db_path:
        from intelligence.services.river import slice_river

        sl = slice_river(as_of, entity, db_path=db_path, allow_hindsight=True)
        for o in sl.objects:
            emitted |= set((o.payload or {}).keys())
        slice_note = f"{entity} @ {as_of}（{len(sl.objects)} 个对象）"
    else:
        # 没给库就退回夹具库。夹具不含真库的全部形状，所以「河发了哪些字段」这一列
        # 会偏保守——偏保守比偏乐观好：它只会把 🟡 误报成 🟠，不会把 🟠 误报成 🟡。
        import tempfile

        from tests.fixtures.river_mini_db import ENTITY, build_mini_db, trading_days
        from intelligence.services.river import slice_river

        with tempfile.TemporaryDirectory(prefix="river-audit-") as tmp:
            fx = build_mini_db(Path(tmp) / "mini.duckdb")
            sl = slice_river(trading_days()[-1], ENTITY, db_path=fx, allow_hindsight=True)
        for o in sl.objects:
            emitted |= set((o.payload or {}).keys())
        slice_note = f"夹具库 {ENTITY} @ {trading_days()[-1]}（保守读数，真库字段更多）"

    schema = (REPO_ROOT / "market_feature_store" / "schema.sql").read_text(encoding="utf-8")
    return {"labels": labels, "emitted": emitted, "schema": schema, "slice_note": slice_note}


def classify(entry: dict[str, Any], cap: dict[str, Any]) -> tuple[str, str]:
    """按映射表声明的依赖，核对河此刻**真的**提供到哪一档。

    注意方向：映射表声明的是「这条判据需要什么」，不是「它属于哪一档」。
    档位每次现算——河扩了标签，昨天的 🟡 今天自动变 ✅，不需要改映射表。
    这正是把结论挂在能力上而不是挂在注释上的意义。
    """
    if entry.get("architecture"):
        return "architecture", str(entry["architecture"])

    need_labels = entry.get("needs_labels") or []
    hit = [x for x in need_labels if x in cap["labels"]]
    if need_labels and len(hit) == len(need_labels):
        return "judgeable", f"标签 {hit}"
    if hit:
        miss = [x for x in need_labels if x not in cap["labels"]]
        return "raw_only", f"只有 {hit}，还缺标签 {miss}"

    need_fields = entry.get("needs_fields") or []
    have = [x for x in need_fields if x in cap["emitted"]]
    if have:
        return "raw_only", f"河发了 {have}，但没有标签"

    need_cols = entry.get("needs_schema") or []
    insch = [x for x in need_cols if x in cap["schema"]]
    if insch:
        return "in_db_not_in_river", f"schema 有 {insch}，六轨不读"

    return "absent", entry.get("absent_note") or "库里没有"


# --------------------------------------------------------------------------- #
# 映射表
# --------------------------------------------------------------------------- #
def load_map(pid: str) -> dict[str, Any]:
    path = MAP_DIR / f"{pid}.json"
    if not path.exists():
        raise SystemExit(
            f"没有 {pid} 的映射表：{path}\n"
            f"  视角画像是散文，河是标签，中间那层对应关系必须有人写下来并署名。\n"
            f"  现有映射表：{sorted(p.stem for p in MAP_DIR.glob('*.json')) or '（一张都没有）'}\n"
            f"  照着现有的抄一份，或者先跑 --list-criteria 把画像里的判据导出来当草稿。"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def profile_criteria(pid: str, user: str | None) -> list[str]:
    """从画像里把「可操作判据」摊平成一张清单，用来核对映射表有没有漏。

    摊的是 ``market_lenses`` / ``risk_triggers`` / ``reasoning_patterns`` /
    ``falsification_style`` 四个字段——这四个是**会落到判断上**的。
    ``voice_guidance`` / ``anti_patterns`` 不摊：前者是文风，后者是「不要做什么」，
    都不该变成数据条件。
    """
    from scripts.export_perspective_framework import load_profile

    prof, _ = load_profile(pid, user)
    out: list[str] = []
    for ln in prof.get("market_lenses") or []:
        out.append(f"镜头·{ln.get('name')}：{ln.get('description')}")
    out += [f"风险触发·{x}" for x in prof.get("risk_triggers") or []]
    out += [f"推理模式·{r.get('name')}：{r.get('rule')}" for r in prof.get("reasoning_patterns") or []]
    out += [f"证伪式·{x}" for x in prof.get("falsification_style") or []]
    return out


# --------------------------------------------------------------------------- #
def audit(pid: str, cap: dict[str, Any], *, user: str | None) -> dict[str, Any]:
    spec = load_map(pid)
    rows = []
    for e in spec["criteria"]:
        v, why = classify(e, cap)
        rows.append({"lens": e.get("lens", ""), "criterion": e["criterion"], "verdict": v, "why": why})
    tally = {v: sum(1 for r in rows if r["verdict"] == v) for v in VERDICTS}

    # 画像改了而映射表没跟上，这份审计就会对着一个过期的判据集报数——而且报得像没事一样。
    #
    # 覆盖检查必须**精确**，不能模糊匹配：第一版用了字符串前缀匹配，把 6 条已经拆进
    # 映射表的判据误报成「未覆盖」。在一个把「看着合理的假数字」当头号敌人的仓里，
    # 一个会误报的检查比没有检查更坏——人会学会忽略它。
    #
    # 改为：映射表必须用 profile_coverage 显式声明它覆盖了画像里的哪几条原文，
    # 两边做集合相等比较。画像加了一条而映射表没声明 → 直接报出来，零歧义。
    live = profile_criteria(pid, user)  # 来源缺失应中止，不能报成零缺口。
    coverage = spec.get("profile_coverage") or {}
    uncovered = sorted(set(live) - set(coverage))
    stale = sorted(set(coverage) - set(live))

    return {
        "perspective": pid,
        "map_version": spec.get("version"),
        "map_author": spec.get("author"),
        "rows": rows,
        "tally": tally,
        "total": len(rows),
        "profile_criteria_count": len(live),
        "uncovered": uncovered,
        "stale": stale,
        "river": {"labels": sorted(cap["labels"]), "slice": cap["slice_note"]},
    }


def render(rep: dict[str, Any]) -> None:
    print(f"\n视角 {rep['perspective']}    映射表 {rep['map_version']}（{rep['map_author']}）")
    print(f"河的可判标签（{len(rep['river']['labels'])}）：{rep['river']['labels']}")
    print(f"切片样本：{rep['river']['slice']}")
    print("-" * 104)
    print(f"{'镜头':<16}{'判据':<34}{'结论':<14}依据")
    print("-" * 104)
    for r in rep["rows"]:
        print(f"{r['lens']:<16}{r['criterion']:<34}{MARK[r['verdict']]:<14}{r['why']}")
    print("-" * 104)
    t, tot = rep["tally"], rep["total"]
    for v in VERDICTS:
        n = t.get(v, 0)
        if n:
            print(f"  {MARK[v]:<14}{n:>3}/{tot}  ({100 * n / tot:.0f}%)")
    cheap = t.get("raw_only", 0)
    if cheap:
        print(f"\n  → 最便宜的一档是 🟡 有料无词（{cheap} 条）：原料已经在河里，缺的只是标签名 + 一次口径确认。")
    if rep["uncovered"]:
        print(f"\n  ⚠ 画像里有 {len(rep['uncovered'])} 条判据没进映射表（映射表落后于画像）：")
        for c in rep["uncovered"]:
            print(f"      - {c[:92]}")
    if rep["stale"]:
        print(f"\n  ⚠ 映射表声明覆盖了 {len(rep['stale'])} 条画像里已经没有的判据（画像改过，映射表没跟）：")
        for c in rep["stale"]:
            print(f"      - {c[:92]}")
    if not rep["uncovered"] and not rep["stale"] and rep["profile_criteria_count"]:
        print(f"\n  ✓ 映射表与画像逐条对齐（{rep['profile_criteria_count']} 条原文全部有归属）")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perspective", help="画像 id，例如 kol_fengyuan")
    ap.add_argument("--all", action="store_true", help="审计全部已有映射表")
    ap.add_argument("--user", help="蒸馏画像所属用户（内置画像不用给）")
    ap.add_argument("--db", help="主库路径；不给则用夹具库（读数偏保守）")
    ap.add_argument("--entity", default="半导体")
    ap.add_argument("--as-of")
    ap.add_argument("--list-criteria", action="store_true", help="只把画像里的判据导出来，当映射表草稿")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.list_criteria:
        if not a.perspective:
            ap.error("--list-criteria 要配 --perspective")
        for c in profile_criteria(a.perspective, a.user):
            print(c)
        return 0

    pids = sorted(p.stem for p in MAP_DIR.glob("*.json")) if a.all else [a.perspective]
    if not pids or pids == [None]:
        ap.error("要么 --perspective，要么 --all")

    cap = river_capability(a.db, a.entity, a.as_of)
    reports = [audit(p, cap, user=a.user) for p in pids]
    if a.json:
        print(json.dumps(reports if a.all else reports[0], ensure_ascii=False, indent=2))
    else:
        for r in reports:
            render(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
