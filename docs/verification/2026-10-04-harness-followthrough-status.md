# 原质检建议落实复核（10-04 晚）

观察时间：2026-10-04 22:40–23:30（Asia/Taipei）。父任务 FINANCEWORKS-1，本页更新 FINANCEWORKS-2 的基线。
上一版 [10-03 基线](2026-10-03-harness-followthrough-baseline.md)保留原读数不改；本页替换它的“当前状态”列，并补上它没有的条目。

## 固定版本与读数

- GitHub main 与 8792 生产同为 `bd2c58b3775f`（#40 与 #39，10-04 17:36 切换，收据见 FINANCEWORKS-13 评论）。
- PR #30 仍是 Draft：文档头 `bffc675da`，产品候选 `51b66d52`。文档头的 python / frontend / e2e / registry-check / workbench-check 五项均为 success（23:22 回读）。
- 主检出 `~/finance-workspace-private`：HEAD `47a05e36b`，落后 main 224 个提交，脏条目 118（其中 5 处是本轮改的，见下文）。
- 开放 PR：#30、#38、#41。
- 预测台账：Open 表 205 行，pending 115，其中超过 30 天未处理的 101 条；最新编号 R-20261004-02。

本轮没有发起任何模型调用。数据库只用只读连接查询。

## 建议 → 10-04 实测 → 接替任务

| 原建议或缺口 | 10-04 实测状态 | 接替 |
|---|---|---|
| 修正技能暴露集合 | main 上已修，有防回归测试。**新发现**：桌面 app 的 worktree 会话从主检出加载技能，而主检出落后 224 个提交，所以此前会话看到的仍是旧视图（`up-line` 等三个在，`stock-technicals` 不在）。本轮已在主检出工作区对齐；改完后本会话技能列表当场热更新，证实了加载来源。 | 13（主检出整体同步） |
| 429 按冷却重试 | 已部署。同一 provider 按 `Retry-After` / `retry-after-ms` 等一次再试；没给就等 2 s 加抖动，上限 20 s，并计入调用预算。工具调用与合成路径都走 `_with_rate_limit_retry`。只重试一次，不做多次退避；网关写在响应正文里的 `reset_seconds` 读不到。14 天效果预测 R-20261001-02 仍 pending。 | 10 |
| 模型身份准入 | continuous 路径每轮写 `model_admission`，错配只告警不拦截；2×2 分析按产物重算身份。8792 固定流程路径没有正向的实际模型字段，10-04 的 MY-01 因此 identity stop。代码默认模型仍是 `glm-5.2`。 | 5 |
| 恢复台账、到期规则 | 记账已恢复，到期体检工具在用。过期待处理 101 条，10-03 以来只清了 1 条。 | 10 |
| 可表达 MODEL_FIX / TOOL_SURFACE_FIX | 未加，fix_type 仍是七类冻结枚举。HARNESS_FIX 占 140/205（68%）。 | 10 |
| 2×2 分离模型与 harness | 10-02 四格各跑一次，结果 0/0/1/0，R17 证伪。10-04 用户把正式问题收窄为“同一 GLM-5.3-Flash 在 Pi ReAct 与 8792 上的差异”，设计稿是 20 题 × 2 臂 × 3 次。冒烟每臂 1 题：Pi 7/7、8792 6/7（n=1，不比高低）；预注册修订在 PR #41。模型轴不在正式设计内，强模型参照沿用 08-27 的 react 臂，版本与数据快照都不同。正式批量未开跑。 | 5 |
| 冻结正则，先量改写路由 | 8 个文件共 245 处，与基线相同。改写题路由准确率未量。 | 7 |
| finance_query 裁剪、合并重叠工具 | 未动。agent schema 24,156 字（其中 dataset 10,937），40 个数据集全量下发；注册表 19 个工具，三组重叠都还在。 | 7 |
| 内容正确性题包、切流前必跑 | 留出集已冻结（PR #31：10 道单轮 + 2 道多轮，48 个字段哈希），任务板记录里没有用过。10-04 #40 部署的放行项是门禁、三验和两道探针，不含它。 | 4、6 |
| 记忆召回题集与语义对照 | 真实快照上 24 道改写题：关键词档 hit@5 为 2/24（原句）到 9/24（加主题）；BGE 23/24，但多返回 97 次，人工审读其中 57 次与题目无关，生产保持 keyword。“命中后只交付原则、丢掉纠偏正文”由 PR #33 修复并已上线。冷启动开场预取约 1 s 超时，文档记录时尚未解决。 | 8 |
| 开场召回、条目归属与冲突 | 生产含 memory_prefetch，冷启动超时同上。归属与冲突去重本轮未复核。 | 8 |
| 核心表日期 / 非空红绿表 | 未开工。23:29 只读实测：核心行情到 09-30（节前最后交易日），时效正常；主线板块 09-30 共 68 行，成交额、强度、涨幅等 22 列全空；`fact_sector_daily.strength` 共 113,537 行，无一非空；`fact_stock_high_daily.is_new` 当日 295 行全空。龙虎榜、竞价、外盘等 7 张表停在 09-02（龙虎榜、竞价有同花顺表到 09-30），`fact_theme_flow_daily` 停在 09-15。 | 9 |
| 一个数据族完成换源与消费 | 未签字，现状同上。 | 9 |
| 开发、生产、夜跑根隔离 | 生产固定快照加独立 venv 已落实。主检出仍是数据根，落后 224 个提交、脏 118。 | 13 |
| Knevo 周题包、吸收项回归、月度留出 | 仍在 backlog，旧包端到端 0/12 未翻案。 | 11 |
| 巨函数渐进拆、增量复杂度检查 | 未做。300 行以上函数 32 个；`_run_turn_ledgered` 2,299 行（审计时 2,279），`create_app` 1,354 行（1,330）。ruff 仍只开 E4/E7/E9/F，target 仍是 py39。 | 12 |
| 收据离 Git | 未做。`docs/verification` 有 14,533 个文件、131.9 MB 在 git 里（全仓跟踪 286.6 MB）。本页的原件放在运行目录，git 里只提交本页。 | 12 |
| AGENTS / lessons 精简 | 未做。AGENTS.md 23,003 B，lessons 106,731 B，inflight/main.md 21,557 B。 | 12 |
| 非生产循环归位 | 未做。runtime 共 24 个模块、25,608 行，`layer_audit.py` 仍写“底座 15 个模块”。 | 12 |
| 换库锁自检、Mac 专属测试、CI | 已做，10-03 基线已核。本轮只见 CI 在正常运行（PR #30 文档头五项），未复测锁。 | 13 |

## 本轮受托动作

授权：用户原话「都做，按最优推进」（Claude Code 会话 `74dae9f9-1568-4f13-9063-40253d68445e`，约 2026-10-04 23:20 CST）。范围是上一轮列出的四项，不含合入或部署。

1. **PR #30 正文**补记文档头 CI 全绿，并加一条“main 已含 #40，合入须先重新合成”的提示；Pi 的原句保留。PR 仍是 Draft，没有开自动合并。
2. **FINANCEWORKS-3** 补评论后由 in_review 改为 done（v12），只关闭工程/集成范围。
3. **主检出技能视图**：删掉 `up-line`、`watchlist-ma`、`top-gainers-feishu` 三个软链，加上 `stock-technicals`，并把 `skills/top-gainers/SKILL.md` 写成 main 版本（只差描述一行）。只改工作区，没动索引，也没提交。以后整体同步主检出前，先按原件 `skill-view/README.md` 撤掉这 5 处，否则那个未跟踪的软链会挡住快进。
4. **回收两棵树**：`…/harness-integration-20261003/gate-trees/mutation-fix` 和 `~/fwp-wt-harness-output-provenance-1003`。两棵的 HEAD 都钉到了 Gitea 的 `refs/archive/wt-20261004/…`，分支保留，残留已打包、数据库已克隆，卷可用空间 +0.84 GiB。第一次 dry-run 作废：工具只取最后一个 `--reason`，套到了两棵树上；改用计划文件重跑。

## 新发现的遗留

- **PR #30 合入前提变了**：main 上的 #40 和 PR #30 都改了 `intelligence/services/episode_protocol.py`，`51b66d52` 的收据覆盖不到新组合。PR #30 的回答质量验收目前没有执行者；用户分发的 GLM 对照比的是线上 8792 和 Pi 外壳，不包含 PR #30。
- `worktree_closeout.py` 的 `--reason` 不会和 `--tree` 一一配对，已另开任务修。
- 记忆库里还有一棵 `~/agent-memory-wt-harness-output-provenance-1003`（Pi 的分片记忆树，干净），不在本轮授权范围内。
- 桌面 worktree 会话开场注入的“工作区事实”描述的是主检出，不是当前 worktree。在 worktree 里要自己重跑 `bash scripts/session_facts.sh`。

## 原件

原件在 `~/.finance-runtime/reviews/harness-followthrough-20261004/`：

- `measurements/`：台账、正则、函数、工具面、数据只读查询，以及任务板、PR 快照
- `skill-view/`
- `tree-closeout/`
- PR #30 正文改前、改后与回读

文件清单与哈希见同目录的 `evidence-manifest.sha256`。
