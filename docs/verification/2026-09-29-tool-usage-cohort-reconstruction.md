# 2026-09-29 · R-20260827-14 历史样本重建（未闭环）

## 可复算的时间证据

原工单首次落盘提交 `be00f83c7` 的提交时间是 **2026-08-27 20:43:39 +0800**；该版本已经写有 **747** 份样本、698 可算 run、572 差值 run、1193 suspicious 等原始读数。当前运行根中按 run 日期截至 08-27 有 **748** 份，其中 **747** 份 `continuous-episode.json` 的现存 mtime 不晚于首次提交，只有一份探针 `probe-cutover-0827f/runs/run_20260827_211959_285536/continuous-episode.json` 在 **21:21:25** 才写入（晚于工单首次落盘约 38 分钟）。并非为了凑数随意删一个：严格的“首次提交时不可能已经存在”的时间顺序给出了唯一增量。

在此现存 747 份上重算，**四组验收与原表逐项相等**：`with_checks=735`、`computable=698`、`gap_runs=572`、output 实例差值 **425**、suspicious **1193**；样本名下 387 + 探针/评测 360，日期 08-08→08-27。八行工具分母/分子：`kb_search 603/406`、`web_search 89/83`、`news_search 120/89`、`evidence_lookup 84/55`、`l3_lookup 5/3`、`graph_lookup 199/99`、`market_data 459/171`、`mainline_context 59/14`；output_id 的八格亦与原工单 §3.2 全等。

可复现冻结物：`intelligence/eval/measurements/tool-usage-differential-2026-08-27-reconstructed-cohort.json`（747 个相对路径、各文件 SHA256 与现存 mtime）；同目录 `tool-usage-differential-2026-08-27-all-until-2026-08-27-manifest-*.json/.md` 是 `--manifest` 严格校验文件内容后的审计报告。任何 run 缺失、字节变化、路径越界或清单重复均 fail closed。**这叫从现存产物“重建”，不是当时保存下来的原始 manifest；mtime 可被改写，不把统计一致冒充历史文件身份的绝对证明。**

## 仍未满足的原验收项

747 份历史运行产物的 `continuous-episode.json`、`run.json`、`report.json` 未找到代码 source revision；`stream.jsonl`/`trace.jsonl` 亦未见该字段。部署账本 `/Users/a77/.finance-runtime/deploy-ledger.jsonl` 从 08-19 20:01 +0800 才开始留痕，样本中 **468/747 份早于 08-19**，且账本本身不提供每个 run 的代码映射。不能拿 `kb_commit`、当前 main HEAD 或事后部署账本的部分时段推定全样本 revision 跨度。审计头如实写 `UNAVAILABLE`、覆盖 0/747。

用户选择**维持原严格判据**，不把 748 新基线或未知修订跨度改写为“验收已过”。因此 PR #966 继续 WIP：数值已精确复现，但“原 manifest 与代码 revision 跨度”待独立来源；如另有当时冻结清单/可信 run→revision 映射，再据此复核，不无证据补编。
