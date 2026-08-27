# 诊断：锚定实体数字证据在 R 通道消失

日期：2026-08-17
handoff：`docs/handoffs/2026-08-17-evidence-number-density.md`（#153）
探针：`/tmp/probe-evidence-number-density.py`（不入库；层 1/层 2 + 插桩 `collect_evidence_index`）
生产 8792：未动（`877e1f72`）

## 结论

H1 **REJECTED**。H2 **REJECTED**。H3 **REJECTED**。
新假设 H4 **CONFIRMED**：`collect_evidence_index` 用图谱暴露概念过滤锚定实体自己的证据，错位概念把整包滤空。

单子里「保底名额」按诊断取舍：**不采用**。锚定实体已经排在 targets 第一位；滤空修好后它会先占满 R 名额，不需要再加配额层。不动 `max_evidence`，不动 stale 排序。

## 三假设

| 假设 | 结论 | 证据 |
|---|---|---|
| H1 targets 错位 | REJECTED | `ctx.anchor=长电科技`；`targets[0]=长电科技`。`result.anchored_entity` 与入口一致。 |
| H2 行建了被挤掉 | REJECTED | `bundle.lines` 全量 8 条，无一含「长电科技」或 `286.69`。差集为空——行没建出来。 |
| H3 cite 分支没走到 | REJECTED | 锚定实体分支走到了：`get_evidence('长电科技', concept='1.6T CPO')` 已调用；`found=False` 后 `continue`，`cite('R')` 对这条没有可 cite 的 item。不是漏走分支。 |

## H4（新）

`collect_graph` 把 `graph_query`（实体名 + 实体概念袋）的暴露收成 `company_evidence_concepts`。长电科技的概念袋是 `1.6T CPO / ABF载板 / AI基础设施与国产算力 / AI应用`，第一条暴露绑成 `1.6T CPO`。

`collect_evidence_index` 对每个 target 调用：

```text
get_evidence(target, concept=company_evidence_concepts.get(target))
```

长电科技 top-8 证据的 concept 是 `光模块 / AI应用 / AI端侧 / AI算力 / ASIC / AI芯片 / GPU / HBM`，没有 `1.6T CPO`。精确过滤失败，模糊匹配也找不到「1.6T CPO」子串 → `found=False`。

随后 targets 扫到盘面候选：富信科技/工业富联/剑桥科技/汇绿生态/铭普光磁/长芯博创 里，谁的绑定概念能命中谁就进 R。`max_evidence=8` 被这些行占满。

复算（与 handoff 层 1 同一 adapter）：

- `get_evidence('长电科技', limit=8)` → 8 条，含 `286.69`
- `get_evidence('长电科技', concept='1.6T CPO')` → `found=False`
- `get_evidence('长电科技', concept='AI算力')` → 1 条，含 `286.69`（说明数在库里，是过滤把它拿掉）

## 修复

锚定实体调用 `get_evidence` 时不带图谱暴露 concept。无锚定题仍按原逻辑带 concept。回归在 `test_evidence_providers.py::CollectEvidenceIndexAnchorTests`。

修后层 2（`use_llm=False`，本树）：R1–R8 的 target 全是长电科技；`证据链` 含 `286.69` / `12.00` / `13.2` / Chiplet `50` 亿。注意 handoff 原探针 `any('286.69' in str(c) for c in citations)` 会假阴——`cite` 的 detail 只有 `target=` / `source=`，数字在证据行不在 Citation 对象里。验收看证据链或 `bundle.lines`。

修后 live（in-process，`use_llm=True compose=True`，`WORKBENCH_GROUNDED_PRESENTER=0`，未碰 8792）：收据 `~/.finance-runtime/claim-tiering-20260817/live-number-density.json`。答案正文写出 286.69 亿(+18%)、市占率 12.00%、毛利率 13.2%；R1–R8 全部 `target=长电科技`。compose 正文未打 `[R4]` 这种标签（marker lane），但数字已从锚定实体证据行进入终稿。

pytest（`umask 022`）：本树 5342 passed / 19 failed / 4 skipped。同一 19 条在未改 `collect_evidence_index` 的 `fwp-wt-deploy-main` 上同样 19 红（worker/RAG ready/paths 环境项），不是本修复引入。相关新测 9 passed；golden+adapter 22 passed；ruff 改动文件绿。
