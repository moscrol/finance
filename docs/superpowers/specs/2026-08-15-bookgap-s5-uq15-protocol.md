# uq15 判分执行协议（S5 交付物）

- spec：`2026-08-15-bookgap-s5-independent-examiner.md` · 出题完成日 2026-08-15
- 题集：`intelligence/eval/cases/uq15_questions.jsonl`（15 题：盘面事实 4 / 归因分析 4 / 主题链条 4 / 反证与边界 3）
- 哈希清单：`intelligence/eval/cases/uq15_rubric_hashes.json`（sha256 × 15）
- rubric 本体：密封于用户本地保管目录（含 `MANIFEST.sha256` 与校验方法），出分后入仓公开
- 本协议目标：让一个没参与出题、没参与实现的第三方 agent，**不问任何人**就能完成跑批与判分

## 1. 角色隔离矩阵（硬约束）

| 角色 | 谁来做 | 不许做 |
|---|---|---|
| 出题人 | 本 spec 执行 agent（已完成，退出后续环节） | 不跑批、不判分、不改 runtime |
| 跑批方 | 任一新 agent | 开工前不得读任何 rubric；不得改 runtime 后再跑（跑的必须是指定 commit） |
| 判分方 | 另一新 agent（≠跑批方，≠出题人，≠被评 runtime 的实现/调参者） | 判分前不得参与实现讨论；不得改 rubric |
| 翻案裁决 | triage loop 检阅方 | 不得由判分方自裁 |
| 用户 | 保管密封 rubric；判分开始时移交判分方 | — |

## 2. 跑批规程（跑批方照此执行）

1. 声明身份：在 run 工件里写明自己未读过 uq15 任何 rubric、未参与 runtime 实现。
2. 固定被评对象：记录 runtime 的 git commit / 部署位（与 triage loop 跑批同一产品问答入口口径；入口选择写进工件）。
3. 逐题投放：题面 `question` 原文投放；`context` 非空的题（uq15-q14）必须把语境随题面一并注入（模拟提问时刻）。**不做任何提示词增补或改写。**
4. 数据基准：`asof_data_cutoff` 标注了每题的事实基准日。若跑批日期晚于 2026-08-15，须在工件里记录跑批时 DuckDB `max(trade_date)`，供判分方核对时间边界类关键点（q14 的判定以题面注入的提问时刻为准，不随跑批日漂移）。
5. 产出工件：`intelligence/eval/runs/uq15-<UTC时间戳>.json`，每题记录 `{id, question, context, answer_text 全文, trace 引用, 开始/结束时间}`，外加 `{runtime_commit, 入口说明, duckdb_max_trade_date}`。工件先提交（PR 或推分支），**提交完成后才允许开封 rubric**——防止见 rubric 后回改答案。

## 3. 判分规程（判分方照此执行）

1. 验封：从用户处取得 15 份 rubric，逐一 `shasum -a 256`，对照 `uq15_rubric_hashes.json`。任何一份不匹配→停止判分，报告用户。
2. 逐题判分：每题按 rubric 的关键点表打分（关键点分值合计 10 分/题，总分 150）。每个关键点必须引用答案原文片段作为命中依据；无法引用原文=未命中。
3. 一票否决：q13/q14/q15 的 rubric 含一票否决条款，触发即该题 0 分（否决理由写明原文依据）。
4. 容差执行：rubric 写明的容差带是唯一口径；判分方不得自行放宽或收紧。
5. 产出工件：`intelligence/eval/runs/uq15-<同时间戳>-scored.json`：每题 `{id, 各KP得分+依据引文, 小计, 否决标记}`，汇总 `{总分/150, 分题型均分（盘面事实/归因分析/主题链条/反证与边界）, 判分方身份声明}`。
6. 公开：判分完成后，rubric 本体由判分方原样提交入仓（`intelligence/eval/cases/uq15_rubrics/`），入仓文件必须逐一通过哈希校验。

## 4. 翻案规则

- 翻案窗口：判分工件合入后 48 小时内；逾期分数冻结。
- 谁可翻案：跑批方或 runtime 维护方，逐关键点提出，必须带答案原文引文+rubric 条文依据。
- 谁裁决：triage loop 检阅方逐条裁决（维持/改分），结论追加进 scored 工件；判分方与出题人不得自裁。
- rubric 勘误：若翻案证明 rubric 本身错误（如库内口径读取有误），不改原 rubric 文件（哈希已封），由检阅方新增 `erratum_uq15-qNN.md` 说明修正口径，经用户确认后生效；该题按勘误口径重判。

## 5. 与 qc28 的关系

- uq15 不替换 qc28：qc28 仍是 triage loop 回归基线；uq15 是抗泄漏的独立评测集，两者分数不混算、不换算。
- uq15 的题面公开、判分要点密封；qc28 的既有口径本 spec 未读未动。

## 6. 出题人隔离声明与已读路径清单（验收判据 3）

出题人声明：全程未读 `intelligence/eval/cases/` 既有内容（仅新增两个 uq15 文件）、未读 `docs/verification/`、未读 runtime 源码（finance 仓任何 `.py` 实现，含 `market_feature_store/`、`intelligence/services/`、verifier/episode 系列）。`.foresight/` 中刻意避开判分产物类文件（`verdicts.jsonl`、`answer_scores.jsonl`、`recall_cases.jsonl` 未读）。

已读路径全清单（内容级读取）：

| 类别 | 路径 | 用途 |
|---|---|---|
| spec/索引 | `docs/superpowers/specs/2026-08-15-bookgap-s5-independent-examiner.md`、`2026-08-15-bookgap-index.md`（git show 自 gitea/main） | 任务定义 |
| 仓内文档 | `docs/learning/current-duckdb-source.md` | 定位 canonical 盘面库 |
| 仓内文档 | `AGENTS.md`（finance，仅 `rg "foresight|duckdb"` 命中行） | 定位台账 |
| KB 规则 | `~/knowledge-base-private/AGENTS.md` | 遵守 KB 仓纪律 |
| KB wiki | `wiki/concepts/`：光纤光缆.md、空芯光纤.md、稀土.md、医疗服务.md、液冷.md（前120行）、CPO.md（前80行） | 出题素材 |
| KB wiki | `wiki/entities/`：蓝盾光电.md、亨通光电.md（前100行） | 出题素材 |
| DuckDB 只读 | `db/market_feature_store.duckdb`：fact_market_daily、fact_sector_daily、fact_stock_daily、fact_leader_height_daily、fact_mainline_sector_daily、fact_theme_limit_heat_daily、fact_limit_advance_daily（均 read_only=True 查询） | 盘面事实 ground truth |
| .foresight | `~/agent-memory/.foresight/linxiaoqi5111/`：corrections.jsonl（尾6条）、experience_cards.jsonl（尾6条） | 对齐产品真实用途与失败模式 |

目录名级浏览（未读内容）：home 目录、`market_feature_store/` 文件名、`wiki/` 子目录文件名、`.foresight/` 文件名、git 元数据（status/log/branch/worktree）、`intelligence/eval/runs/` 未跟踪文件名（来自 git status 输出）。

## 7. 验收判据对勾（预注册判据 → 交付状态）

1. ✅ 15 题齐，配比 4/4/4/3 符合 spec §3.2；每题 `material_domain` 均在限定面内（KB wiki / DuckDB 只读 / .foresight）。
2. ✅ 哈希清单与密封 rubric 一致（`MANIFEST.sha256` 与仓内 JSON 同源生成；用户可按 README 抽 2 题当场验）。
3. ✅ 已读路径清单见 §6，不含隔离区路径。
4. ✅ 本协议给出跑批/判分/翻案全流程，第三方 agent 可照此执行，无需问人。
