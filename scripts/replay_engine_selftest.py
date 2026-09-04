#!/usr/bin/env python3
"""replay_engine 零凭证自测（INDEX #25 §2.11；照 methodology_backtest_selftest.py 的形状）。

LLM 用可注入的 stub callable，不联网、不花钱。在 ``methodology_backtest_selftest.build_sample_db`` 的同款最小
主库 + 旁路库上跑四组对照：

  阳性对照（车道 A）  stub 原样返回编译器事件集 → 三条规则精确率 / 召回率 / 完全一致率都 = 1.0
  阴性对照（车道 A）  stub 返回随机实体子集 → 完全一致率显著低于 1.0（夹具规模下 < 0.8）
  记忆对照（车道 B）  stub「背答案」：当且仅当提示词里出现绝对日期字符串，才查 outcomes 表按真实结果作答，
                      否则 50% 随机 → 命名臂命中率 − 匿名臂命中率 > 0.2，报表「臂间差」非空且带 memory_signal。
                      这是匿名化臂存在的理由：臂间差就是记忆成分的上界。
  前视对照（车道 B）  把 outcomes 整体前移一个交易日（复用 methodology selftest 的作弊夹具）后，「背答案」
                      stub 在命名臂的命中率必须掉到基准 ±0.1 内——基准 = 同一夹具上 50% 随机 stub 的命中率。
                      能掉下来，是因为对照假设用 T+1 / fwd_return@1：前移后判分读到的是 D0+2 那天的收益，
                      与 stub 背的 D0+1 独立（合成日收益 i.i.d.），信息被整体抹掉；若用 @5 则相邻窗口重叠
                      4/5，掉不到基准——那是重叠，不是没泄漏。

另外顺带断言：匿名臂提示词零绝对日期、两臂提示词经映射表替换后逐字相同；每条读数都带
pit_grade / memory_bucket / arm；格子 N<10 不出率。

样本数据全部虚构。用法：
    python scripts/replay_engine_selftest.py
退出码：0 = PASS，非 0 = FAIL。
"""

from __future__ import annotations

import importlib.util
import json
import random
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from intelligence.eval import replay_engine as engine  # noqa: E402
from intelligence.services.methodology_backtest.labels import build_labels  # noqa: E402
from intelligence.services.methodology_backtest.outcomes import build_outcomes  # noqa: E402

SEED = 20260905
N_NODES = 40
N_DIRECTION_CLAIMS = 7  # + 1 条 market 假设 = 8（上限）
HORIZONS = (1, 3, 5, 7, 10)  # 合成库多建 h=1，前视对照靠它


def _load_mb_selftest() -> Any:
    path = REPO_ROOT / "scripts" / "methodology_backtest_selftest.py"
    spec = importlib.util.spec_from_file_location("mb_selftest_for_replay", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mb_selftest_for_replay"] = module
    spec.loader.exec_module(module)
    return module


def _node_input(run_root: Path, run_id: str, as_of: str) -> tuple[dict[str, Any], dict[str, Any]]:
    node_dir = run_root / run_id / "nodes" / as_of
    return (
        json.loads((node_dir / "input.json").read_text(encoding="utf-8")),
        json.loads((node_dir / "anon_map.json").read_text(encoding="utf-8")),
    )


def _true_outcomes(labels_db: Path, as_of: str, entities: list[str], horizon: int) -> dict[str, float | None]:
    con = duckdb.connect(str(labels_db), read_only=True)
    try:
        out: dict[str, float | None] = {}
        for entity in entities:
            row = con.execute(
                "SELECT fwd_return FROM history_outcomes WHERE entity_type='sector' AND entity_id=? AND trade_date=? AND horizon=? AND status='ok'",
                [entity, as_of, horizon],
            ).fetchone()
            out[entity] = float(row[0]) if row and row[0] is not None else None
        return out
    finally:
        con.close()


def _advancers(source_db: Path, date: str) -> float | None:
    con = duckdb.connect(str(source_db), read_only=True)
    try:
        row = con.execute("SELECT advancers FROM fact_market_daily WHERE trade_date = ?", [date]).fetchone()
        return float(row[0]) if row and row[0] is not None else None
    finally:
        con.close()


def _noise_entities(mb: Any, replay_input: dict[str, Any], calendar: list[str]) -> list[str]:
    """只挑 D0+1 / D0+2 都落在合成噪声日（不在任何植入事件窗 [e, e+6]）的板块：噪声日收益 i.i.d.，
    前移一日后判分读到的 D0+2 与 stub 背的 D0+1 独立，命中率才会真正回到基准；事件窗内相邻两日同号，
    会把「泄漏」和「重叠」混在一起。"""
    as_of = replay_input["as_of"]
    idx = calendar.index(as_of)
    n_days = len(calendar)
    out: list[str] = []
    for entity in replay_input["labels"]["sector"]:
        code = entity["entity_id"]
        s = int(code.split(".", 1)[0]) - 880000
        windows = [(e, e + 6) for e in mb.event_days(s, n_days)]
        if any(lo <= day <= hi for lo, hi in windows for day in (idx + 1, idx + 2)):
            continue
        out.append(code)
    return out


def _pick_entities(mb: Any, replay_input: dict[str, Any], calendar: list[str], rng: random.Random) -> list[str]:
    ids = _noise_entities(mb, replay_input, calendar)
    rng.shuffle(ids)
    return ids[:N_DIRECTION_CLAIMS]


def make_stubs(*, mb: Any, run_root: Path, run_id: str, oracle_db: Path, source_db: Path, calendar: list[str], mode: str) -> engine.LLMCallable:
    """mode: positive（车道 A 原样复现 + 车道 B 背答案不看日期）/ negative（车道 A 随机子集 + 车道 B 硬币）/
    memory（车道 A 原样复现 + 车道 B 只在见到绝对日期时背答案）。"""
    rng = random.Random(SEED)
    rules = engine.load_lane_a_rules()

    def stub(prompt: str, meta: dict[str, Any]) -> dict[str, Any]:
        as_of, arm, lane = meta["as_of"], meta["arm"], meta["lane"]
        replay_input, anon_map = _node_input(run_root, run_id, as_of)
        alias = (lambda c: anon_map["codes"].get(c, c)) if arm == "anonymized" else (lambda c: c)
        if lane == "A":
            con = duckdb.connect(str(oracle_db), read_only=True)
            try:
                expected = engine.expected_triggers(con, rules, as_of, restrict_to=replay_input.get("visible_entity_ids"))
            finally:
                con.close()
            if mode == "negative":
                universe = [e["entity_id"] for e in replay_input["labels"]["sector"]]
                themes = [e["entity_id"] for e in replay_input["labels"]["theme"]]
                triggers = {}
                for rule in rules:
                    pool = themes if rule.entity_type == "theme" else universe
                    k = rng.randint(0, max(1, len(pool) // 3))
                    triggers[rule.rule_id] = [alias(c) for c in rng.sample(pool, min(k, len(pool)))]
            else:
                triggers = {rid: [alias(c) for c in ids] for rid, ids in expected.items()}
            return {"content": json.dumps({"rule_triggers": triggers}), "model": "stub-oracle", "provider": "stub", "reason": "", "elapsed_ms": 0}

        entities = _pick_entities(mb, replay_input, calendar, rng)
        sees_dates = bool(engine.ABSOLUTE_DATE_RE.search(prompt))
        cheat = mode == "positive" or (mode == "memory" and sees_dates)
        truth = _true_outcomes(oracle_db, as_of, entities, 1) if cheat else {}
        as_of_label = as_of if arm == "named" else "T-0"
        hyps: list[dict[str, Any]] = []
        for i, entity in enumerate(entities):
            if cheat and truth.get(entity) is not None:
                positive = truth[entity] > 0
            else:
                positive = rng.random() < 0.5
            op = ">" if positive else "<="
            hyps.append(
                {
                    "id": f"d{i}",
                    "category": "direction",
                    "claim": f"{alias(entity)} fwd_return@1 {op} 0",
                    "horizon": "T+1",
                    "confidence": "medium",
                    "confidence_probability": 0.6,
                    "evidence_refs": ["labels.sector"],
                    "evidence_as_of": as_of_label,
                    "falsify_when": f"{alias(entity)} fwd_return@1 {'<=' if positive else '>'} 0",
                }
            )
        idx = calendar.index(as_of) if as_of in calendar else -1
        t1 = calendar[idx + 1] if 0 <= idx < len(calendar) - 1 else None
        actual = _advancers(source_db, t1) if (cheat and t1) else None
        threshold = int(actual) - 1 if actual is not None else 2700
        hyps.append(
            {
                "id": "m0",
                "category": "market",
                "claim": f"T+1 涨家数 > {threshold}",
                "horizon": "T+1",
                "confidence": "low",
                "confidence_probability": 0.5,
                "evidence_refs": ["market_history[T-0].advancers"],
                "evidence_as_of": as_of_label,
                "falsify_when": f"T+1 涨家数 <= {threshold}",
            }
        )
        return {"content": json.dumps({"hypotheses": hyps}, ensure_ascii=False), "model": "stub-oracle", "provider": "stub", "reason": "", "elapsed_ms": 0}

    return stub


def _rate(records: list[dict[str, Any]], **where: Any) -> tuple[int, float | None]:
    picked = [r for r in records if all(r.get(k) == v for k, v in where.items()) and r["verdict"] in ("hit", "miss", "partial")]
    if not picked:
        return 0, None
    return len(picked), sum(1 for r in picked if r["verdict"] == "hit") / len(picked)


def _lane_b_records(run_root: Path, run_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for verdict_path in sorted((run_root / run_id / "nodes").glob("*/verdict.json")):
        doc = json.loads(verdict_path.read_text(encoding="utf-8"))
        for arm, items in (doc.get("lane_b") or {}).items():
            for v in items:
                out.append({**v, "arm": arm, "pit_grade": doc["pit_grade"], "as_of": doc["as_of"]})
    return out


def run_once(*, mb: Any, run_root: Path, run_id: str, source_db: Path, judge_db: Path, oracle_db: Path, mode: str, calendar: list[str], nodes: list[dict[str, Any]]) -> dict[str, Any]:
    stub = make_stubs(mb=mb, run_root=run_root, run_id=run_id, oracle_db=oracle_db, source_db=source_db, calendar=calendar, mode=mode)
    return engine.run_replay(
        db_path=source_db,
        labels_db=judge_db,
        snapshot_root=run_root / "no-snapshots",
        runtime_root=run_root,
        count_per_grade=N_NODES,
        llm=stub,
        ledger_dir=None,
        reconcile=False,
        measurements_dir=None,
        run_id=run_id,
        nodes_override=nodes,
        abort_failure_rate=None,
        log=lambda _msg: None,
    )


def main() -> int:
    checks: dict[str, bool] = {}

    def record(name: str, ok: bool, detail: str = "") -> None:
        checks[name] = ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    mb = _load_mb_selftest()
    with tempfile.TemporaryDirectory(prefix="replay-selftest-") as tmp:
        root = Path(tmp)
        source_db = root / "sample_feature_store.duckdb"
        labels_db = root / "history_labels.duckdb"
        mb.build_sample_db(source_db)
        build_labels(source_db, labels_db)
        build_outcomes(source_db, labels_db, horizons=HORIZONS)
        (root / "no-snapshots").mkdir()
        con = duckdb.connect(str(labels_db), read_only=True)
        try:
            calendar = [str(r[0])[:10] for r in con.execute("SELECT trade_date FROM history_calendar ORDER BY 1").fetchall()]
            conditions = engine.load_conditions(con)
        finally:
            con.close()
        end = engine.judgeable_end(source_db, horizon=10)
        nodes = engine.select_nodes(source_db, conditions["calendar"]["start"], end, count_per_grade=N_NODES, snapshot_root=root / "no-snapshots")
        record("节点选择：无快照目录 → 全部 trade_date_only", bool(nodes) and all(n["pit_grade"] == "trade_date_only" for n in nodes), f"nodes={len(nodes)}")

        # 两臂提示词 + 匿名臂零绝对日期（第一个节点）
        first = nodes[0]
        replay_input = engine.build_replay_input(first, db_path=source_db, labels_db=labels_db, snapshot_root=root / "no-snapshots")
        anon_map = engine.build_anon_map(replay_input)
        diff_ok = True
        for lane in engine.LANES:
            named = engine.render_prompt(replay_input, "named", lane=lane, anon_map=anon_map)
            anon = engine.render_prompt(replay_input, "anonymized", lane=lane, anon_map=anon_map)
            diff_ok = diff_ok and engine.apply_anon_map(named, anon_map) == anon and not engine.ABSOLUTE_DATE_RE.search(anon)
        record("两臂提示词：命名臂经映射表替换后与匿名臂逐字相同；匿名臂零绝对日期", diff_ok)

        # 阳性对照（车道 A + 车道 B 背答案不看日期）
        pos = run_once(mb=mb, run_root=root, run_id="positive", source_db=source_db, judge_db=labels_db, oracle_db=labels_db, mode="positive", calendar=calendar, nodes=nodes)
        cells = pos["lane_a"]["cells"]
        record(
            "阳性对照（车道 A）：stub 返回编译器事件集 → 精确率 / 召回率 / 完全一致率 = 1.0",
            bool(cells) and all(c["exact_match_rate"] == 1.0 and (c["precision_micro"] in (1.0, None)) and (c["recall_micro"] in (1.0, None)) for c in cells),
            "; ".join(f"{c['arm']}/{c['rule_id']}: exact={c['exact_match_rate']} tp={c['tp']} fp={c['fp']} fn={c['fn']}" for c in cells if c["arm"] == "named"),
        )
        pos_b = _lane_b_records(root, "positive")
        n_pos, pos_rate = _rate(pos_b, arm="named", category="direction")
        record("阳性对照（车道 B）：背答案 stub 命名臂 direction 命中率 ≈ 1.0", pos_rate is not None and pos_rate >= 0.95, f"N={n_pos} hit_rate={pos_rate}")
        n_pm, pm_rate = _rate(pos_b, arm="named", category="market")
        record("阳性对照（车道 B）：market 类走 market_actuals + 条件口径，背答案 → 命中率 ≈ 1.0", pm_rate is not None and pm_rate >= 0.95, f"N={n_pm} hit_rate={pm_rate}")
        tagged = all({"pit_grade", "memory_bucket", "arm"} <= set(c) for c in pos["lane_b"]["cells"]) and all({"pit_grade", "arm"} <= set(c) for c in cells)
        record("每条读数都带 pit_grade / memory_bucket / arm 三标签", tagged)
        small = [c for c in pos["lane_b"]["cells"] if c["n"] < pos["lane_b"]["min_n"]]
        record("格子 N<10 只给 N，不出命中率 / 区间", all("hit_rate" not in c and "wilson_95" not in c for c in small), f"small_cells={len(small)}")
        record("memory_bucket：stub 模型不在截止日表 → 全部 unknown 且标 memory_contaminated", all(c["memory_bucket"] == "unknown" and c["memory_contaminated"] for c in pos["lane_b"]["cells"]))

        # 阴性对照（车道 A 随机子集 + 车道 B 硬币）
        neg = run_once(mb=mb, run_root=root, run_id="negative", source_db=source_db, judge_db=labels_db, oracle_db=labels_db, mode="negative", calendar=calendar, nodes=nodes)
        neg_cells = [c for c in neg["lane_a"]["cells"] if c["nodes_with_expected_events"] > 0]
        worst = max((c["exact_match_rate"] for c in neg_cells), default=1.0)
        record("阴性对照（车道 A）：随机子集 → 有事件的规则完全一致率 < 0.8", bool(neg_cells) and worst < 0.8, f"max exact_match_rate={worst}")
        neg_b = _lane_b_records(root, "negative")
        n_base, baseline = _rate(neg_b, arm="named", category="direction")
        record("阴性对照（车道 B）：硬币 stub 给出基准命中率", baseline is not None and 0.3 <= baseline <= 0.7, f"N={n_base} baseline={baseline}")

        # 记忆对照：只在见到绝对日期时背答案
        mem = run_once(mb=mb, run_root=root, run_id="memory", source_db=source_db, judge_db=labels_db, oracle_db=labels_db, mode="memory", calendar=calendar, nodes=nodes)
        mem_b = _lane_b_records(root, "memory")
        n_named, named_rate = _rate(mem_b, arm="named", category="direction")
        n_anon, anon_rate = _rate(mem_b, arm="anonymized", category="direction")
        gap = (named_rate - anon_rate) if (named_rate is not None and anon_rate is not None) else None
        record("记忆对照：命名臂命中率 − 匿名臂命中率 > 0.2（匿名化臂的检出力）", gap is not None and gap > 0.2, f"named N={n_named} {named_rate} vs anonymized N={n_anon} {anon_rate} → gap={gap}")
        gaps = mem["lane_b"]["arm_gap"]
        record(
            "报表臂间差字段非空且带 memory_signal",
            bool(gaps) and all(g["gap_named_minus_anonymized"] is not None and "memory_signal" in g and "上界" in g["memory_signal"] for g in gaps),
            json.dumps([{k: g[k] for k in ("pit_grade", "memory_bucket", "gap_named_minus_anonymized")} for g in gaps], ensure_ascii=False),
        )

        # 前视对照：判分用前移一日的 outcomes，stub 仍背原表答案
        shifted_db = root / "history_labels_shifted.duckdb"
        shutil.copyfile(labels_db, shifted_db)
        shifted = mb.shift_outcomes_one_day_earlier(shifted_db)
        cheat = run_once(mb=mb, run_root=root, run_id="lookahead", source_db=source_db, judge_db=shifted_db, oracle_db=labels_db, mode="positive", calendar=calendar, nodes=nodes)
        cheat_b = _lane_b_records(root, "lookahead")
        n_cheat, cheat_rate = _rate(cheat_b, arm="named", category="direction")
        within = cheat_rate is not None and baseline is not None and abs(cheat_rate - baseline) <= 0.1
        record(
            "前视对照：outcomes 前移一交易日后，背答案 stub 命中率落到基准 ±0.1 内",
            shifted > 0 and within,
            f"shifted_rows={shifted} N={n_cheat} hit_rate={cheat_rate} vs baseline={baseline} (unshifted={pos_rate})",
        )
        record("前视对照：前移前后命中率之差 > 0.3（阳性优势被抹掉）", pos_rate is not None and cheat_rate is not None and pos_rate - cheat_rate > 0.3)
        del cheat, mem, neg

    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        print(f"\n[FAIL] {len(failed)} 项断言未通过: {failed}")
        return 1
    print(f"\n[PASS] 全部 {len(checks)} 项断言通过；合成库上 节点 → 输入 → 两臂提示词 → stub → 判分 → 聚合 端到端跑通。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
