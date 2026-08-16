#!/usr/bin/env python3
"""把 score_longtail_live_ab.py 的 JSON 填进 live A/B 收据。窗未齐则拒绝。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / "docs/verification/2026-08-16-longtail-baseline-live-ab.md"
FREEZE = REPO / "docs/verification/2026-08-16-longtail-baseline-frozen-set.md"


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _num(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _pp(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.1f}pp"


def _arm_row(arm: str, stats: dict[str, Any] | None) -> str:
    if not stats:
        return f"| {arm} | 0 | 0 | 0 | — | — | — | — | — | — | — |"
    peel = (
        f"{stats['peel_n']} / {_pct(stats['peel_rate'])}"
        if stats.get("peel_n")
        else "0 / —"
    )
    return (
        f"| {arm} | {stats['n']} | {stats['completed']} | {stats['degraded']} | "
        f"{_pct(stats.get('compliant_delivery_rate'))} | "
        f"{_pct(stats.get('empty_shell_rate'))} | "
        f"{_pct(stats.get('judge_outage_candidate_rate'))} | "
        f"{peel} | {_pct(stats.get('evidence_bound_rate'))} | "
        f"{_num(stats.get('mean_elapsed_s'))} | {_num(stats.get('mean_input_tokens'), 0)} |"
    )


def _delta_row(delta: dict[str, Any]) -> str:
    elapsed = delta.get("elapsed_s")
    tokens = delta.get("input_tokens")
    return (
        f"| Δ | — | — | — | {_pp(delta.get('compliant_delivery_pp'))} | — | — | "
        f"{_pp(delta.get('peel_pp'))} | {_pp(delta.get('evidence_bound_pp'))} | "
        f"{_num(elapsed) if elapsed is None else f'{elapsed:+.1f}'} | "
        f"{_num(tokens, 0) if tokens is None else f'{tokens:+.0f}'} |"
    )


def _layer_table(block: dict[str, Any]) -> str:
    header = (
        "| 臂 | n | completed | degraded | 合规交付 | 空壳 | 宕机候选 | 剥句 n / 率 | eb | 墙钟 s | input tokens |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|"
    )
    return "\n".join(
        [
            header,
            _arm_row("off", block.get("off")),
            _arm_row("on", block.get("on")),
            _delta_row(block.get("delta") or {}),
        ]
    )


def _verdict(data: dict[str, Any]) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    residual = data["summary"]["residual"]
    delta = residual.get("delta") or {}
    peel_n = (residual.get("off") or {}).get("peel_n", 0) + (residual.get("on") or {}).get(
        "peel_n", 0
    )
    guards = data["summary"]["guards"]
    heading_hits = guards.get("heading_hits") or []
    guard_n = guards.get("n") or 0
    if heading_hits:
        notes.append(f"护栏产物出现【长尾回答骨架】: {heading_hits}")
    bad_route = []
    for row in guards.get("routing") or []:
        qtype = row.get("question_type")
        owner = row.get("answer_owner")
        conf = row.get("confidence")
        if qtype == "general_finance_qa" or owner not in {
            "stock-deep-dive",
            "financial-analysis",
            "news-impact",
            "theme-research",
        } or not isinstance(conf, (int, float)) or conf < 0.6:
            bad_route.append(row.get("slot"))
    if bad_route:
        notes.append(f"护栏路由偏离: {bad_route}")
    if guard_n < 5:
        notes.append(f"护栏槽不足 5: n={guard_n}")

    eb_pp = delta.get("evidence_bound_pp")
    compliant_pp = delta.get("compliant_delivery_pp")
    peel_pp = delta.get("peel_pp")
    if peel_n == 0:
        notes.append("residual 两臂 peel_n=0（judge 未跑），剥句率 INCONCLUSIVE，不是 0")
    distinguishable = []
    for name, value in (
        ("compliant_delivery", compliant_pp),
        ("peel", peel_pp),
        ("evidence_bound", eb_pp),
    ):
        if value is None:
            continue
        if abs(value) >= 5.0:
            distinguishable.append(f"{name} {value:+.1f}pp")
    if heading_hits or bad_route:
        outcome = "GUARD_FAIL"
        criterion = "护栏未过：注入标题或高置信路由发生了变化。"
    elif peel_n == 0 and not distinguishable:
        outcome = "CONTRAST_INCONCLUSIVE"
        criterion = (
            "95 槽已齐，但 residual 剥句率因 judge 未跑而缺失，"
            "且合规交付 / eb 的 on-off 差未达到预注册 5pp。不能主张骨架抬了残差地板。"
        )
    elif peel_n == 0 and distinguishable:
        outcome = "CONTRAST_PARTIAL"
        criterion = (
            "95 槽已齐；剥句率仍 INCONCLUSIVE。residual 上有 ≥5pp 的可分辨差："
            + "；".join(distinguishable)
            + "。outlook 档不计入骨架独有信号。"
        )
    elif distinguishable:
        outcome = "CONTRAST_MEASURED"
        criterion = "95 槽已齐。residual 可分辨差：" + "；".join(distinguishable)
    else:
        outcome = "CONTRAST_NEGATIVE"
        criterion = (
            "95 槽已齐。residual 合规交付 / 剥句 / eb 均无 ≥5pp 可分辨差。"
            "否定结论也算交付；不翻默认。"
        )
    notes.append("不翻 ASK_LONGTAIL_BASELINE 默认。")
    return outcome, criterion, notes


def _slot_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| slot | run_id | stratum | outcome | 合规 | 空壳 | 宕机候选 | judge | peel | eb | s |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        if row.get("role") != "longtail":
            continue
        peel = "—" if row.get("peel_rate") is None else f"{row['peel_rate']:.2f}"
        eb = "—" if row.get("evidence_bound_rate") is None else f"{row['evidence_bound_rate']:.2f}"
        lines.append(
            f"| {row['slot']} | `{row.get('run_id') or ''}` | {row.get('stratum')} | "
            f"{row.get('terminal_outcome')} | "
            f"{'Y' if row.get('compliant_delivery') else ''} | "
            f"{'Y' if row.get('empty_shell') else ''} | "
            f"{'Y' if row.get('judge_outage_candidate') else ''} | "
            f"{row.get('judge_status') or '—'} | {peel} | {eb} | "
            f"{_num(row.get('elapsed_s'))} |"
        )
    return "\n".join(lines)


def _guard_table(guards: dict[str, Any], slots: list[dict[str, Any]] | None = None) -> str:
    lines = [
        "| id | run_id | outcome | heading 在产物 | question_type | owner | conf | 墙钟 s |",
        "|---|---|---|---|---|---|---|---|",
    ]
    heading = set(guards.get("heading_hits") or [])
    by_id = {str(row.get("slot", "")).split(":")[1]: row for row in guards.get("routing") or []}
    elapsed_by_id: dict[str, Any] = {}
    for row in slots or []:
        slot = str(row.get("slot") or "")
        parts = slot.split(":")
        if len(parts) >= 2 and parts[1].startswith("G"):
            elapsed_by_id[parts[1]] = row.get("elapsed_s")
    elapsed_vals: list[float] = []
    for gid in ("G01", "G02", "G03", "G04", "G05"):
        row = by_id.get(gid, {})
        slot = row.get("slot") or f"on:{gid}:r1"
        elapsed = row.get("elapsed_s")
        if elapsed is None:
            elapsed = elapsed_by_id.get(gid)
        if isinstance(elapsed, (int, float)):
            elapsed_vals.append(float(elapsed))
        lines.append(
            f"| {gid} | `{row.get('run_id') or 'MISSING'}` | {row.get('terminal_outcome') or 'MISSING'} | "
            f"{'是' if slot in heading else '否'} | {row.get('question_type') or '—'} | "
            f"{row.get('answer_owner') or '—'} | {row.get('confidence') if row.get('confidence') is not None else '—'} | "
            f"{_num(elapsed)} |"
        )
    if elapsed_vals:
        lo, hi = min(elapsed_vals), max(elapsed_vals)
        lines.append("")
        lines.append(f"墙钟 {_num(lo)}–{_num(hi)}s（约 {lo:.0f}–{hi:.0f}s）。")
    return "\n".join(lines)


def render(data: dict[str, Any], health: dict[str, Any]) -> str:
    cov = data["coverage"]
    outcome, criterion, notes = _verdict(data)
    scored_at = data.get("scored_at")
    absorbed = data["summary"].get("routing_absorbed") or []
    outcomes = cov.get("outcomes") or {}
    degraded = outcomes.get("degraded", 0)
    failed = outcomes.get("failed", 0)
    cancelled = outcomes.get("cancelled", 0)
    protocol = outcomes.get("protocol_error", 0)
    note_lines = "\n".join(f"- {item}" for item in notes)
    absorbed_line = "无" if not absorbed else ", ".join(f"`{item}`" for item in absorbed)
    return f"""# 2026-08-16 长尾骨架 15 题 live A/B 对照收据

格式参照 bookgap S2 对照收据（`fwp-wt-bookgap-s2`：预注册度量、分层对照、允许否定结论）。
口径在窗未齐时已锁（见 §0）；本节数字来自 `{scored_at}` 的只读计分，不是预判。

## Verdict

- outcome: {outcome}
- failure_criterion: {criterion}
- live_window: `~/.finance-runtime/longtail-ab-20260816/`
- user: `longtail-ab-0816`
- baseline_tip: `773b3d7e`（两臂同一 SHA；`source_dirty=false`）
- fixture: `intelligence/eval/fixtures/longtail-baseline-frozen-15-2026-08-16.questions.json`
- fixture_sha256: `9b43354b2d9af669634d87df6f1e8ae219ebb751156694d0e01dc65a948b3fd8`
- freeze_receipt: `docs/verification/2026-08-16-longtail-baseline-frozen-set.md`
- closeout_handoff: `docs/handoffs/2026-08-16-longtail-ab-window-closeout.md`
- scorer: `scripts/score_longtail_live_ab.py`（只读）
- score_json: `~/.finance-runtime/longtail-ab-20260816/score.json`
- threshold_pp: **5.0，不放宽**
- default_switch: 本收据无论结论如何都不翻 `ASK_LONGTAIL_BASELINE`（权威 handoff §2.4 第 4 刀另开 PR）
- routing_absorbed: {absorbed_line}

{note_lines}

## 0. 口径锁（窗未齐已生效，避免 HARKing）

### 0.1 判断句标记词表

与 `_JUDGE_SYSTEM_PROMPT` 逐字一致，实现常量 `ANALYTICAL_MARKERS`：

> “据此判断”“这说明”“这意味着”也属于显式分析标记

出处：`intelligence/services/episode_semantic_verifier.py` 的 `_JUDGE_SYSTEM_PROMPT`。
`SKILL.md` / `longtail_baseline.ANALYTICAL_MARKERS` 必须含原词。收据不另造同义词。

### 0.2 四度量（权威 handoff §3 / FREEZE §预注册对照）

| 度量 | 定义 | 分母 | 不放宽 |
|---|---|---|---|
| 非空 direct_answer 交付率 | 公开 `answer.md` 里 `direct_answer` 被 marker coverage 标为 present | 对照槽（见 0.4） | — |
| 合规交付（空壳 vs 诚实缺口） | 正文含「未取得」或「现有证据不足，暂不能可靠回答」算合规；聊天意见「看起来有字」不算成功 | 同上 | — |
| judge 宕机候选草稿 | 正文以「结构化证据绑定已通过边界校验，但语义核验因瞬时服务问题未完成」起头 | 单列，**既不算合规也不算空壳** | 不进剥句分母 |
| judge 剥句率 | `rejected_sentence_indexes` / 草稿句数 | **仅 judge 实际跑过的槽** | judge_unavailable 不进分母，不折进 failed |
| evidence_bound_rate | 有 `evidence_hashes` 且 `gap` 为空的 binding / binding 总数；无 binding = 0 | 有 episode 的对照槽 | **5pp 门槛不放宽** |
| token / 墙钟 | `context_growth.cumulative_input_tokens`；smoke `elapsed_s` | 有读数的对照槽 | 报增量，不作放行门槛 |

分层：outlook（题面含「你认为 / 你觉得 / 怎么看 / 机会在哪 / 会怎么走」）vs residual。
**骨架独有信号只看 residual。** outlook 档剥句/降级叠着 #79 比较集绑定，不算进本刀的账。

### 0.3 护栏：改用 FREEZE 已登记口径，不补跑 off 臂

设计 handoff §3 原文要「高置信路由行为零变化，取 5 题回归对比字节级 diff」。
FREEZE_ONLY 后写、更具体，已改成：

> 护栏 5 题只跑注入臂，确认 `【长尾回答骨架】` 不出现。

本收据采用 FREEZE 口径，**不**在收口阶段补跑 5 槽 off 臂。理由：

1. 冻结收据是后写的操作协议；runner 按它只排了 on ×1，不是执行偏差。
2. 收口交接 §7：收口前 8792 不跑任何其他 live 批。补跑会占用 off 臂，也是重开窗。
3. `【长尾回答骨架】` 是 prompt-only 注入标题，公开产物里本来就不会出现；on 臂长尾题的 episode 里也搜不到该标题（14:00 抽查 on:L01:r1）。字节级公开答案 diff 会被 theme-research 正文方差淹没，测不到「有没有注入」。
4. 护栏另加三条可观察断言，全部只读：标题不在 5 个 on 臂 run 产物里；`question_type` 仍是 `theme_analysis`（或至少不是 `general_finance_qa`）；`answer_owner` 仍在 `RESEARCH_OWNER_IDS` 且 confidence ≥ 0.6。

假骨架含市场数字必须被 review 拒绝——那是单测门，不在本 live 窗重跑。

### 0.4 清污（不入对照统计）

引 closeout handoff §2。workbench 目录里这些 run **账留全史，收据不算**：

| 类别 | run_id | 说明 |
|---|---|---|
| 带病期已删槽 | `run_20260816_125145_832107` … `run_20260816_130525_453745`（8 个，progress.jsonl 前 8 行） | 两臂健康不对称；墙钟 151.0/152.5/151.5/37.0/153.0/93.0/81.5/104.0s 只作取证 |
| kickstart 中断 | `run_20260816_130709_427017` | off:L09:r1，13:08:50 打断，无 smoke json、无账行 |
| 启动孤儿 | `run_20260816_124504_615880`、`run_20260816_124957_138951`、`run_20260816_131020_573635` | 12:45 / 12:49 / 13:10 |

对照起点：`run_20260816_131941_597875`（13:19:41 双臂健康后的 off:L01:r1）。
对齐键：smoke `slot` + `run_id`，不以 workbench 目录时间猜。

### 0.5 降级与路由吸收

- `terminal_outcome=degraded` **单列**，不折进 failed。
- 某题在 `773b3d7e` 上改判成 `market_*` 或 `RESEARCH_OWNER_IDS` owner → `routing-absorbed`，不进剥句率。L04 尤甚。
- `judge_status=unavailable`（预算/核验没跑到 judge）→ 剥句率缺失，不是剥句率 0。这与 `2026-08-16-outlook-verification-budget-regression.md` 同形；outlook 档这类降级不记骨架账。

### 0.6 环境坑（杀进程纪律）

本机 `pgrep/pkill -f` 对这批长 argv/大 env 进程系统性失明。停 8793 前必须：

```bash
sid=$(cat ~/.finance-runtime/longtail-ab-20260816/sidecar.pid)
ps -p "$sid" -o pid,args=
# argv 须含：uvicorn ... --port 8793
```

三次事故（12:48-12:51 叠启、13:06 假杀、13:09 叠启）都是这个坑。是否升格 lessons 由 owner 决定。

## 1. 窗身份（收口重读）

| 臂 | 端口 | 开关 | health `source_revision` | dirty | ready |
|---|---|---|---|---|---|
| off | 8792 | 默认 off | `{health.get("off_rev", "")}` | {health.get("off_dirty")} | {health.get("off_ready")} |
| on | 8793 | `ASK_LONGTAIL_BASELINE=on` | `{health.get("on_rev", "")}` | {health.get("on_dirty")} | {health.get("on_ready")} |

- runner pid **{health.get("runner_pid", "36401")}**（13:19:41 起；`ps -p` 验过 argv 含 `run_live.py`。15:37:57 `all slots processed` 后自然退出，收口时 `ps -p` 已空）
- sidecar pid **{health.get("sidecar_pid", "21888")}**（12:50 起；`ps -p` 验过 argv 含 `--port 8793`）
- sidecar 停机：**15:39:07** 干净退出——`sidecar.err.log` 写 `Shutting down` → `Finished server process [21888]`（mtime `2026-08-16 15:39:07`）。收口时 `ps -p 21888` 已空
- 端口 8793：收口时 `lsof -nP -iTCP:8793 -sTCP:LISTEN` 无行、exit 1，已验空
- 生产 8792 **未重启、未替换**（收口后仍 `773b3d7e` / `source_dirty=false` / ready 200）
- filled_at: {datetime.now(timezone.utc).isoformat(timespec="seconds")}

## 2. 覆盖

| 项 | 值 |
|---|---|
| 预注册槽 | 95 = 15×2×3 + 5 guard(on×1) |
| `all slots processed` | {cov.get("all_slots_processed_log")} |
| `runs/` 覆盖 | {cov.get("present_count")}/95 missing={len(cov.get("missing") or [])} |
| degraded 单列 | {degraded} |
| failed / cancelled / protocol_error | {failed} / {cancelled} / {protocol} |
| log_tail | `{cov.get("log_tail")}` |

## 3. 主表

### 3.1 全样本（routing-absorbed 已剔除）

{_layer_table(data["summary"]["all"])}

### 3.2 outlook（#79 叠层；不算骨架独有）

{_layer_table(data["summary"]["outlook"])}

### 3.3 residual（本刀独有信号）

{_layer_table(data["summary"]["residual"])}

### 3.4 读表（不改口径）

residual 的两列 ≥5pp 差是同一件事的两面，不能拆开只报合规：

- on 臂更多公开答案是诚实缺口（「未取得」/「暂不能可靠回答」），空壳从 26.7% 降到 6.7%，宕机候选从 56.7% 降到 23.3%。L12/L15 的 chat 完成态尤其明显：off 3/3 空壳，on 2/3 合规。
- off 臂更多是「候选草稿 + judge 未跑」还挂着 binding，所以 eb 看起来高（77.1%）。on 臂诚实缺口没有 binding，eb 掉到 27.1%。这不是「绑得更差」，是公开交付从「未核验候选」换成「缺口声明」。
- 73/95 槽 `degraded`，两臂 `peel_n=0`。预注册剥句率本窗量不出来，与预算回归案同形，不把 unavailable 写成剥句率 0。
- outlook 合规 +13.3pp、eb +4.2pp，未过 5pp 门，且叠着 #79，不记骨架账。
- 护栏 5 题 heading 缺席，路由仍是 `theme_analysis` / `theme-research` / 0.98。它们也全是 degraded，说明预算/judge 问题不是护栏注入造成的。

因此：骨架在残差档抬了诚实交付、压了空壳；剥句率未知；不能凭 eb 下跌主张绑定变差，也不能凭合规上涨主张翻默认。

## 4. 护栏 5 题（on 臂 ×1）

{_guard_table(data["summary"]["guards"], data.get("slots") or [])}

## 5. 逐槽

{_slot_table(data.get("slots") or [])}

degraded 不改写成 failed。清污 8+1+3 不出现在本表。

## 6. 回链

- FREEZE_ONLY `live_ab_ran` 指向本文件，并注明 13:19 清污重跑（引 closeout handoff §2）。
- **不改**夹具 `sample_design.live_ab_ran`：加载器要求该字段保持 `false`。

## 7. 收口后清理（已做）

1. sidecar **21888** 已于 **15:39:07** 干净退出（`sidecar.err.log`：`Shutting down` → `Finished server process [21888]`）。收口时 `ps -p 21888` 已空；`lsof -nP -iTCP:8793 -sTCP:LISTEN` 无 LISTEN。launcher 写明「评测结束即停，不要用它替换 8792」。
2. runner **36401** 已自然退出（15:37:57 `all slots processed`）；`runner.pid` / 日志 / progress / `score.json` 原地留档。
3. 8792 未动（仍 `773b3d7e` / ready 200）；未翻 `ASK_LONGTAIL_BASELINE` 默认。

## 8. 边界

- 不改 runner / 夹具 / 触发条件。
- 不在 `docs/dsh-absorption-spec` 提交本文件。
- 10 题窗仍等分诊/预算回归处置，不在本收据里开。
"""


def update_freeze() -> None:
    text = FREEZE.read_text(encoding="utf-8")
    if "live_ab_ran: `docs/verification/2026-08-16-longtail-baseline-live-ab.md`" in text:
        return
    old = (
        "- live_ab_ran: false\n"
        "- failure_criterion: 未开对照窗。本文件只锁题面、分层、触发观察和护栏，不报告剥句率。\n"
    )
    new = (
        "- live_ab_ran: `docs/verification/2026-08-16-longtail-baseline-live-ab.md`"
        "（13:19 清污重跑后；progress.jsonl 前 8 行与孤儿不入账）\n"
        "- live_ab_in_flight: false\n"
        "- failure_criterion: 本文件只锁题面、分层、触发观察和护栏，不报告剥句率。live 对照见 `live_ab_ran`。\n"
    )
    if old not in text:
        raise SystemExit("freeze receipt pointer text drifted; refuse to patch")
    text = text.replace(old, new, 1)
    text = text.replace("## 预注册对照（仍未跑）", "## 预注册对照（live 已跑，数字不在本文件）", 1)
    FREEZE.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score_json", type=Path)
    parser.add_argument("--health-json", type=Path)
    parser.add_argument("--write-freeze", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.score_json.read_text(encoding="utf-8"))
    if not data.get("coverage", {}).get("complete"):
        raise SystemExit("window not complete; refuse to fill receipt")
    health = {}
    if args.health_json:
        health = json.loads(args.health_json.read_text(encoding="utf-8"))
    RECEIPT.write_text(render(data, health), encoding="utf-8")
    if args.write_freeze:
        update_freeze()
    print(f"wrote {RECEIPT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
