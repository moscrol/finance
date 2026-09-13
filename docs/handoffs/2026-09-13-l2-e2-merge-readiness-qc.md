# L2 / E2 合并就绪审查 · 2026-09-13

## 结论与范围

- `fix/l2-pct-chg-backfill-0913@3458a7f0`：本轮代码复审通过；**尚不能签完整合并就绪**，准确候选的 frontend / e2e 叶子结论未核得。补齐全绿后可请用户授权合并，不需与 E2 捆绑。
- `feat/e2-material-contract-design@fdeaf1cb`：**设计退回补正，不批准进入实现**。文档型变更不代表内容已正确；下列缺口应在本设计分支修正。
- 两分支均包含当前 `gitea/main@e40f22b8`；fetch 后主干未推进。未执行 merge / push / 部署 / 生产回填 / E2 实现。
- 主检出树 `b4a35fa2` 大量其他人在途改动，未触碰；本轮验证在 `/tmp/l2-3458a7f0-merge-review` 的干净候选检出进行。作者两树各有未跟踪 `.venv-workbench`，没有已跟踪文件改动。

## 发现顺序与证据

### F1 · L2：Python 绿不能外推全部叶子门禁（合并前置）

全量收据 `~/.finance-runtime/test-receipts/20260913T122812Z-3458a7f0.json` 确实为 9554 passed / 0 failed / 0 error / 77 skipped，完整 revision=3458a7f0e79f5ecb4878a67750edef5f10ce69e3，代码 dirty=false，依赖门禁未绕过。

在独立候选树调用 `scripts/check_test_receipt.py`，指定该收据、`--expect-revision 3458a7f0 --require-target /Users/a77/fwp-wt-main-merge-0913 --base-drift-max 0`：exit 0，解释器与依赖指纹一致；因此采信该 Python 全量，不重复耗费一次全量。

本轮自跑：
- `.venv-workbench/bin/python -m ruff check .`：exit 0。
- `tests/test_moneyflow_server_aggregation.py`：16 passed；收据 `20260913T125613Z-3458a7f0.json`。
- 旧独立 QC 脚本 `~/.finance-runtime/reviews/l2-pct-chg-54248fa3/evidence/test_l2_repair_qc.py` 指向新候选，选 CLI 拒绝不存在库 / 两表与台账共同回滚 / 非 pct 列不变且值幂等 / 来源 NULL 四例：4 passed。另两个旧断言固定旧消息格式，不套用；新行数格式与外部明细指针由本轮 16 例覆盖。
- registry 四项（check-parseability、check、backfill-tables --check、generate-views --check）全部 exit 0；跨仓缺席项按脚本合同跳过。
- `audit_ledger_spec_crosswalk.py` exit 0（反向 96 条 warning，非 error）；`git diff --check` exit 0。

未核得 **3458a7f0 对应 frontend / e2e** 收据。作者目标树没有前端依赖安装，本轮不启动浏览器或安装。旧 QC 文档里存在 5fb13a8c 的 frontend/e2e 指针，不可冒充本候选已验。按仓库现行规程，任一叶子无结论仍不能直接合。

本轮不重做生产数据审计；前轮 54248fa3 的 52 日备份重放与生产只读结论属于前轮。回填实现改动集中在工具与测试，未修改 `intelligence/`；本次合入不要求切 Workbench 运行快照，但不要把“工具合入”写成“8792 已部署到新 SHA”。

### F2 · E2：证据只落主树，未进入交付提交（P2）

设计稿 §1 与分支交接声称 `e2-evidence/MANIFEST.json` 有 21 项并含 QC 包。`git ls-tree -r --name-only fdeaf1cb -- <e2-evidence路径>` 实际只有 T2/T3 各 4 个文件，共 8 个；没有 MANIFEST，也没有 qc-pack。

进一步定位：MANIFEST 和 qc-pack 落在**主检出树的未跟踪目录** `docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok/e2-evidence/`，不在作者设计树。这不是“全盘不存在”，而是“指定 revision 不能交付”。主树 MANIFEST 的 21 条记录含 `frozen=false` 的大轨迹指针，不能写成 21 个已冻结工件。应按仓内相对路径核对已冻结子集；外部轨迹另标不可随 clone 重现的源指针。

修法：作者认领、审查原件后将应交付的 MANIFEST/QC 包放入设计树并 pathspec 提交；在全新检出中检验每个 `frozen=true` 文件可达且 SHA-256 匹配。不要从主树一把 add，也不要拷生产数据库。

### F3 · E2：现状描述失真，漏了实际工具授权面（P1）

设计稿 §2 / OQ1 把 TaskFrame 描述成无 premise 载体、哈希 asdict 全字段直入。当前基线实际：
- `intelligence/services/task_frame.py:124-142` 已有 `user_premises`、`materials`；`_payload()` 已省略默认空输入字段与空 history_intent。缺的是**显式材料边界策略的载体和投影**，不是用户前提载体从零缺席。
- `intelligence/services/episode_factory.py:509-556` 已有 prior-memory / methodology / 反事实 / 前瞻等 grounding 分支，不能泛写“全部落 evidence”；应限定为 T2/T3 的实际路径没有识别成 material-only。
- `episode_factory.py:244-261` 会加入模型自选读能力 `finance_query/evidence_search`；`build_episode_context:629-650` 冻结最终证据计划与工具授权。
- 已有 `_is_evidence_free_task` 分支会清空证据 requirements 和 authorized；这正是可复用的反事实抑制路径。

D4 只写 `TurnDecision.needs_retrieval=False` 与 retrieval_planner 短路（图里定位 ask.py），没有落到 Workbench Episode 的最终 `contract.allowed_capabilities`。该注册表字段才是工具执行硬门（`research_tool_registry.py:1118`）。只关固定检索，模型仍可能自主读现实数据。

修法：在两条引擎分别列出控制路径，约束最终工具授权、mandatory requirements 回填、预注入上下文与恢复路径；优先扩展已有 evidence-free 投影，不造另一套仅提示词抑制。验收要覆盖“模型主动请求禁用工具也被拒绝”和“最终 prompt 不含越界事实”。

### F4 · E2：D2 把三种不同约束并成全局抑制（P1）

`不要联网` 只禁止网络，不天然禁止本地 DuckDB；`假设降息，结合最近三个月数据分析` 同时需要假设推理与现实证据；材料里的“仅根据”也不是用户对系统下令。当前 D2 词表 + `premise_mode != real_world` 全题清空检索，会误伤这些正常任务；§7 “假设误报代价低”不能成立为默认前提。

修法：区分前提性质、允许证据来源、约束作用范围；只在用户指令区识别，而非扫描整份被引用材料。补 no-network 但允许本地数据、假设+真实数据、引用文本含限制词、混合子题四类反例。普通 hypothetical 不应无条件等同 material_only。

### F5 · E2：验收对错题，未定义合法跨轮材料（P2）

- 稿 §1 把 T3 的 memo 缺失列出是对的，但 A4 错写“T2 答案 + memo ≤200字”。已提交 `t2-question.txt` Q8 要优先研究与两份材料；**T3 Q8** 才要求 ≤200 字备忘录。
- T3 Q1 要逐条引用上一轮原答，且起句“继续上一轮…其余条件不变”。不能把“全新会话重跑”理解成 T3 裸题丢入无上下文会话，也不能为禁 memory 把本次题链合法上下文抹掉。
- A3 禁失败样本板块名只能作一条回归，挡不住其他日期/名称污染，也可能误伤材料内合法同名实体。D5 只数标题不证明 Q1–Q8 一一交付。

修法：全新会话先跑 T2，再同会话跑 T3；冻结 T2 原答/材料及 T3 增量引用。逐题用稳定 question_id 对齐，区分“未答”与“明确缺证据”；memo 仅在题目明确要求时生成并定义计数字符口径。前提纯度按来源/引用边界验证，不靠板块名黑名单。

## OQ1–3 建议（非用户拍板）

| 问题 | 建议 | 取舍 |
|---|---|---|
| OQ1 哈希 | 默认字段省略，非默认策略进入哈希；复用 `_payload` | 保住默认任务旧哈希；补旧 payload round-trip 与不同策略不碰撞测试，而非接受无谓全量失效 |
| OQ2 memory | 严格 material-only 禁跨会话事实记忆；保留明确引用的同题链材料/上一轮原答 | “用户资产”不等于“本题授权证据”；hypothetical 若显式允许现实检索则按来源策略单独授权 |
| OQ3 交付 | 单 Episode 内 question_id→输出槽→逐题章节 | 避免 N 子 Episode 的预算/跨题上下文复杂度；数章节不能替代逐题验收 |

## 接续动作与不做事项

1. L2 补准确候选全部叶子门禁，专属在途交接放 `fix-l2-pct-chg-backfill-0913.md`（目前仍修改别枝旧交接）。用户明确授权后才 `--no-ff` 合并；main 变动则重判候选与收据适用性。
2. E2 先修 F2–F5 与 OQ 定义，补齐冻结证据，再复审设计。此轮没有批准任何实现阶段。
3. 不把“无运行时代码变更”外推为“无需合并门禁”；不把“设计产物可存档”写成“材料题已就绪”。

本轮工具复用 `check_test_receipt.py`、registry 门禁、旧独立 QC 脚本与 Git 对象清单，没有新增通用工具或能力；本次设计审查属于语义边界判断，暂不抽成跨项目自动门禁。既有证据纪律足以覆盖“落盘不等于入提交”，不另建方法论清单。
