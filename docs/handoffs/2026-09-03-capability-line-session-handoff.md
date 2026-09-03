# 日期快照：能力放大 / 工具线一日推进（2026-09-03）——背景、决策、被否方案、读数与后续

配对的在途交接：`docs/handoffs/inflight/spec-capability-amplification-output-gate.md`（≤3K，只写卡点与下一步）。
本快照不限长、写完不改。要动这块地方或想推翻某个决定的人读这份。

## 0. 不读这段会误判后面每个决定的背景

- **架构**：8792 跑的是仓内自己的底座 `ContinuousTurnAdapter → GLMAgentRuntime → ContinuousAgentEpisode`（后端 `continuous_glm`，glm-5.3）。
  9 月 2 日 ResearchHarness 接缝线（#525–#533）把领域抽进 `FinanceResearchHarness`（16 方法），loop 只在接缝上调它。
  分层方向是 pi 的、领域接入方式更像 dsh 的有名决定点、底座里多一台两家都没有的预算状态机（90/60/30、派发实授、reserve、修复轮、升档）。
  **pi / dsh 没有一行代码在跑**；finance-base-ab 的 `pi-shape` / `dsh-shape` 是同一执行器的两种包法，09-01 一次性证完「包法不改路径」即结束。
- **knevo 对照**（spec §1.4，[转述]）：他赢茅台题靯 `web_fetch` + 22 次调用 + 子代理隔离，不靯数据面；他输的工具（`finance_statement` 无 provider 等）是契约缺失。
  用户 09-03 裁决：**抄他的工具形状，契约我们自己做**。
- **预算线**：standard 档总 90s、reserve 60s → 研究窗只有 30s；工具批 asked 30；实授 = min(asked, remaining − reserve)。09-02 finalize 读数：生产成功写作 P95 26.9s，20s 地板证伪，合成侧要 25–35s。spec §6 明写本线不动 90/60/30。
- **今天开工时的状态**（用户两份报告）：#534–#536 已合、8792 在 `532cdb07`；能力放大四块在 `fwp-wt-capability-amplification` 树上未提交两天；主检出树停在 8-30 老分支带 61 脏文件。

## 1. 按发现顺序做了什么

1. **核对两份报告** → 全部属实；发现 cap-amp 树与 main 新提交文件零重叠；收据 7462 与台账 7454 的口径差是 `intelligence tests` vs 整仓（相差 ~50 条），collect-only 逐条对比证明零丢失。
2. **提交 cap-amp、开 #537、干净树整仓门禁 7524P/5F**（= 7454 + 64 新 + 6 conformance 参数化）。
3. **第一次切流 0903a**：8792 `532cdb07 → 6d4a9df1`（#531–#535，有意不带 #537）。首发长电探针 `kb_search`/`evidence_search` 22.8s 超时 → 第二轮 `finance_query` 零授权；复跑通过。
4. **工具侧地板离线量**（`scripts/offline_tool_duration_floor.py`）：825 episode / 2948 工具事件；9/11 工具 p95 < 9s；`kb_search` 成功 30 / 真超时 57，`evidence_search` 3 / 66 → **工具侧没有一个地板可拍**，kb_search 66% 超时是切前就有的生产形状（证明第 3 步的探针红不是本批回归）。
5. **合 #537**；`finance-base-ab` `git init` 推 gitea；`_recover_finalization` 结案「不动」；拆四棵树。
6. **并发首次出现**：docs 提交后 10 秒，同账号从我的分支开合了 #538，我随后误开重复 #539 已带指针关闭。
7. **主检出树足迹**：25 已跟踪修改 + 29 未跟踪代码/文档收进 `wip/mainline-move-footprints-20260903`（pre-commit 全过），主树 `checkout -B main gitea/main`；154 个数据产物原地留。
8. **P0 live 两臂**（快照 `ccf93431`，`SHAPE_OUT_NAME=reference-loop-0903a`）：两臂 `model_finish`、都只调一次 `financial_data` 且 Episode 传了 `{"report_period":"2024年报"}`、答案 1741.44（报告期 2024-12-31 / 披露日 2025-04-03 / E11）、授权集 9 项含 web、`served_models` == 请求。**web 未被调用**——一手证据先到手。配方 ±3 token 硬门差 4 未过。
9. **第二次切流 0903b**：8792 → `ccf9343162d0`（#537 上生产）。探针首发即过，`model_turn` 带 `served_model`。
10. **P1 第一步 #541**：`intelligence/eval/abstention.py` + 消融壳并列聚合 + 08-27 四臂回溯基线：组件臂未见题 10/10 复现；8792（当时 `40fd5a84`）该答 32 题弃 8，其中 7 道判官不可用扣稿；发现消融壳走 legacy `ask` 不经 episode。
11. **4 token 根因 #542**：首轮 user 消息含 `research_contract.task_id = run_<ts>:msg_<hex>`，hex 分词随机；摘掉后同题首轮请求字节稳定。
12. **RAG 三选一执行（用户「执行」）**：#544 菜单裁剪（`min_window_seconds` kb 20 / evidence 30）、#545 worker 保活（首次超时放弃不杀、连续第二次才杀）。
13. **并发第二次**：12:26 另一会话在我刚开的 `fwp-wt-rag-window` 里改 `rag_worker.py`（同设计、改到一半）。按「同一棵树两个 agent」红线，两刀搬到独立树重做，那棵树留对方改动未拆。
14. **第三次切流 0903c**：8792 → `d4fade5494ee`（#541/#542/#544/#545）。探针首轮 `tool_menu` `would_grant=29.67` 藏 `evidence_search`、`kb_search` 22.3s 成功（授予 22.8）；第二轮 `would_grant=0.45` 两条 RAG 都藏；worker 零放弃零杀。
15. **另一会话**合 #547（Alpha 内测基础）并做第四次切流 0903d：8792 → `c88c81da5120`（含本线全部 PR）。

## 2. 决策表（含被否方案）

| 决策 | 选了什么 | 否了什么 | 为什么 |
|---|---|---|---|
| 切流拆两次 | 先切 #531–#535 的 `6d4a9df1`，再切含 #537 的 `ccf93431` | 一次带全 | 五张是零 live 判据重构（#534 一处模型可见文案），#537 是真行为改动；混切出问题分不清归因 |
| 首发探针冷 RAG 超时 | 作废、复跑再采 | 当回归回滚 | 离线读数证明 kb_search 66% 超时切前就有；08-28 有同一先例 |
| 弃权判定口径 | **首句定性**；短快答无标记即回答；结构层（终局/gate receipt/`terminal_phase`）优先 | 长度阈值；只看文本 | 62 字快答（C4）被长度规则误判弃权、783 字诚实拒答（react D8）被漏；判官扣稿正文看不出 |
| 弃权率与分数 | 并列念、不折进边际贡献，按 `expect_refusal` 分「该拒而拒 / 不该弃而弃」 | 折进总分；一个弃权率 | 一票否决式二值量进连续分会把「不说话」读成「略差」；六道题本该拒 |
| 4 token | 从 prompt 摘 `task_id` | 放宽配方容差到 ±8；开 PERSIST 复现 | 模型用不上、协议不解析；摘掉后请求字节稳定、可缓存，容差问题根除 |
| RAG 工具侧 | 1 保活 + 2 菜单裁剪 | 给工具设地板；3 缩 asked | 9 个工具不需要地板，2 个 RAG 在 90s 装不下；保活是唯一找回 kb_search 价值的路；缩 asked 只在保活不成时值 |
| 菜单裁剪落点 | 底座 `EpisodeToolBatchSession.menu()`，领域只申报 `min_window_seconds` | 在 harness 里判；改授予算术 | 「领域申报、底座裁决」同修复轮纪律；spec §6 不动 90/60/30 |
| 菜单口径 | 菜单时的窗，不减思考时间 | 减 p50 5.9s | 先要 live 读数再调；首轮 kb_search 约 24s ≥ 20 装得下 |
| 保活阈值 | 热 worker 连续第二次超时才杀 | 永不杀；每次都杀（原状） | 永不杀会让真卡死的 worker 拖住所有查询；原状是放大器 |
| 并发冲突 | 搬独立树重做，不动对方改动 | 在同一树继续 / 清掉对方改动 | AGENTS.md「不代解」；对方改到一半 |
| 主检出树足迹 | 收进 wip 分支、主树前移 main | 原地不动 / 直接丢 | 08-28 先例；双盲链 plist 指主树，不在 main 上钩子与修复不生效 |
| finance-base-ab | `git init` 推 gitea 私有仓 | 搬进主仓 | 它承载了 P0/P4 依赖的投影与配方，先止血；是否并入另议 |
| P1 第二步 | 不跑 38 题；建议 D 组 8 道 | 全量重跑 | 用户「不用跑很多题」；回溯基线已给改前图 |
| 子代理 | 不动，先写 spec | 现在做 | knevo 唯一确认领先的一轴，但结果须带证据、预算要从 deep 档出、挂哪条 loop 看 P4 |

## 3. 验证与收据

| 项 | 读数 | 收据 |
|---|---|---|
| #537 门禁 | 7524P/5F @`f472f1a8` | `20260903T020730Z-f472f1a8.json` |
| #541 门禁 | 7545P/5F @`5aa26fdb` | `20260903T033505Z-5aa26fdb.json` |
| #542 门禁 | 7546P/5F @`e3b3eedf` | `20260903T034554Z-e3b3eedf.json` |
| #544 门禁 | 7551P/5F @`0d90fdab` | `20260903T043653Z-0d90fdab.json` |
| #545 门禁 | 7552P/5F @`0a3d385b` | `20260903T044442Z-0a3d385b.json` |
| P0 live | 两臂 model_finish / 1741.44 一手 | `finance-base-ab/out/reference-loop-0903a/` |
| 切流探针 | 0903a 复跑 `run_20260903_101655_589201`；0903b `run_20260903_104321_934629`；0903c `run_20260903_124759_653491` | `~/.finance-runtime/live-probe-traceability/20260903-cutover-*.json` |
| 工具地板 | 见 `docs/verification/2026-09-03-tool-duration-floor-offline.md` | 同名 json |
| 弃权基线 | 见 `docs/verification/2026-09-03-abstain-rate-baseline-offline.md` | 同名 json |
| 回滚锚 | `cutover-20260903{a,b,c}-rollback-8792.txt`（d 为另一会话） | `~/.finance-runtime/` |

**哪些结论不成立**：worker 保活效果样本为 0（刚上线，`counters` 全零）；弃权率只有「改前」；茅台题 n=1 的 49s vs 110s 不许读成速度提升；菜单裁剪防的是后续轮次的白烧，首轮那次 23s 超时它防不了。

## 4. 后续要做的（按序）与不要做的

要做：① 库里没有的题跑两臂验 web 链路与判官对 `public_web` 句的处置；② 源可用性进菜单（worker failed → 藏 RAG）；③ 翻 `tool_hunger` 遥测决定加什么工具；④ P2 第一步判官删句结构化落盘（web 证据放量前）；⑤ 子代理 spec（dsh `tool-subagent` 形状、结果带证据、deep 档预算、先看 `govern_mode` 升 deep 频次）；⑥ `graph_lookup` 实体解析契约、`finance_shareholders` 视 ③ 而定。待用户：P1 第二步 D 组 8 道、P4 `sdk_glm` 两臂、足迹分支认领。

不要做：不动 90/60/30（reserve 是写作窗的命，finalize 读数已证 20s 不够）；不给全部工具缺省地板（`would_grant<1s` 时无地板工具照旧可见，那是预算线的事，另一个决定）；不把 web 正文当一手（tier 与 as_of 契约已写死）；不在同一棵树与他人并行改文件；变异恢复不用 `git checkout --`。

## 5. 工具沉淀盘点

| 问 | 答 |
|---|---|
| 重复两次以上的手工排查 | 切流五步跑了三次、干净树规程壳门禁跑了五次、Gitea 开 PR/合并的 python 片段跑了八次——**都没有脚本化**。原因：切流脚本改生产，该单独开 PR 评审；门禁与 PR 片段可脚本化，本轮没做，列为下一任的 `scripts/run_main_gate.sh` / `scripts/gitea_pr.py` 候选 |
| 只在 /tmp 跑过的脚本 | 无；两个离线普查脚本已进 `scripts/`（`offline_tool_duration_floor.py`、`offline_abstain_baseline.py`），docstring 写了防的失败形状 |
| 现有门禁的洞 | ±3 token 硬门量的是 `task_id` 分词噪声 → #542 根除并在 finance-base-ab README 注明前提 |
| 可迁移的模式 | 「run 级 id 进 prompt 让请求不可复现」「超时即杀热进程是放大器」「二值量不进连续分」——建议进 `10_knowledge/`，本轮未写 |
