# 2026-09-23 第二波预检与决策页

## 范围与固定身份

用户问第二波能否开始，随后要求继续。本轮做预检、状态回写与隔离准备，不启动新 agent、不运行全量、不合主干、不部署、不写库、不删除树。

- 预检时间：2026-09-23 11:56 +08:00。
- 固定 base：`9a02279863733c9b9f60fd92fcc7e840fa83f878`。这是当次远端 main 实读；之后的 tip 变化不自动改变本页结论。
- 文档工作树：`/Users/a77/fwp-wt-closeout-workorders-0922`，分支 `docs/closeout-workorders-0922`。原文档 PR #858 已在 `86d3e558e` 合入，本轮是后续状态修订，不等于已经进 main。
- 主检出与三个原任务树的他人改动未动。新建的 `fwp-wt-wave2-history-0923`、`fwp-wt-wave2-re06-0923` 均干净、detached、仍在 `760248ecebc79fbe4f2686ddd42255c1a00ec862`，只是准备目录，不是合流候选。

## 发现与证据

1. 首轮核对时 base 是 `3b7e473575b0`，随后 #873、#858、#879 继续合入。为避免共享 remote ref 在命令之间漂移，最终所有预演用固定 base SHA。
2. 使用 `git merge-tree --write-tree <base> <head>`，不更改现有工作树。exit 0 只代表文本可合；exit 1 是有冲突，不是测试结果。

| 工单 | head | exit | 预演结果 |
|---|---|---|---|
| #68 | `807a75d8817a7b72a4b12cc308c4c022190c3ca3` | 0 | 30 文件增量；tree `7b80b34bea5f3b2e11dd55b3362ec9b80646967e` |
| #71 | `5de303619711995ff6f864487336b7538e6031da` | 1 | 12 个冲突文件 |
| #73 | `100dcb32abd78b7f529d83332731a70704faeeb3` | 0 | 15 文件增量；tree `ba3957c0733d295f10867ebeee7e81a2d48d4ca2` |
| #66 / #855 | `132afc0b157f238ba06818fba281cfaf285b6542` | 1 | 8 个冲突文件 |
| #66 / 混比 | `63f8a385933839834d9c5f46833e9a807aaf80bd` | 1 | 8 个冲突文件 |

文件增量由 `git diff --name-only <base> <merge-tree返回树>` 计数。#68 存在两个 merge-base：`a2c8d1f90`、`442476f7d`，不能把三点 diff 任取一个共同祖先得到的 266 文件当作本次真实增量。`42784d27e` 不是 #68 head 的祖先；两者直接 diff 是 240 文件，包含基线差异，也不等于要移植的代码量。#67 已合入，不再把 #68 描述成等待给 #67 选 head。

#71 冲突路径：

- `.claude/lessons_learned.md`
- `docs/agent-product-door.md`
- `intelligence/runtime/continuous_turn_adapter.py`
- `intelligence/services/derived_calculation.py`
- `intelligence/services/episode_semantic_verifier.py`
- `intelligence/services/episode_tools.py`
- `intelligence/services/research_delivery_checks.py`
- `intelligence/services/research_tool_registry.py`
- `intelligence/tests/test_research_delivery_checks.py`
- `intelligence/tests/test_research_delivery_repair.py`
- `scripts/review_probes/research_delivery_mutations.json`
- `scripts/review_probes/run_extraction_mutations.py`

#66 两个预演的冲突路径相同：门页、`intelligence/api/app.py`、`continuous_turn_adapter.py`、`financial_claim_checks.py`、`honesty_gates.py`、`test_agent_episode_progress.py`、`test_research_progress.py`、`run_extraction_mutations.py`。不能整文件选一侧来代替语义整合。

3. 固定 base 上 `git grep` 确认 `_track_public_delivery`、`append_contract_stub`、`missing_contract_elements` 已在主干调用链。工单旧快照的“main 只记账不执法”已过时；本轮没有查生产版本，不能推断生产是否启用。
4. #69 队列改绑合并提交 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`，检出 `/Users/a77/.finance-runtime/reviews/runtime-identity-effects-20260922/post-merge-main` 的 HEAD 和 clean 已回读。旧 `candidate/finance-workspace-private@698f689b0` 保留作来源对照，不移签收据。
5. 七个旧 tmux 窗口可读，但显示 502/503、认证/压缩失败或重复输入；没有向它们注入命令，也没有停止任何会话。这不证明其他新 Pi 会话不可用。#75 的至少两份主张清单条件已满足，当前审查任务去重、K3 请求参数和网关预检尚未完成。

## 资源与未验证

11:56 的三段 load 为 `8.62 / 6.85 / 6.62`，磁盘约 78.63 GiB，实际 pytest 一条（PID 42744）。本轮未启动 pytest；load 超过全量门限 8，也超过 #68 单条复跑门限 4。启动前必须重新检查，不能把这个快照当配额预留。

在 #68 准备树执行 `python3 scripts/code_map.py query`，结构层为 `refused_empty`，地图不可用。没有从空图推断架构；后续结构探针复跑前要先准备该候选自己的地图，不能借主检出的图宣称候选已通过。旧 `test_structure_probe_daily_full` 1F 仍是待分诊，不宣告环境红已解决。

没有完成：前向候选的四叶、#68 低负载三次复跑与阳性对照、#71 冲突解决、#75 K3 审查、#76 真实模型验收、#61 换库验证。未出新的测试绿单。

## 调度与决策

| 选择 | 结论与理由 |
|---|---|
| #68 先推进候选，#71/#66 做冲突整合准备 | 采用。三者共享 verifier/adapter，最终候选和门禁要依次冻结，避免重复跑旧基线 |
| 第二波所有全量同时启动 | 否。负载门不满足，也会抢首波仍在运行的测试 |
| #66 重合 #835 | 否。#67 财务路线已经落定并合入；仅处理 #855 与混比剩余增量 |
| 把七个旧 tmux 窗口直接当可用审查员 | 否。窗口活着不代表请求成功或审查任务未重复 |
| #73 自动采用推荐 B | 否。继续不等于选定同意范围；先等明确选择 |

需用户选择的 #73：

- A：只改文案，明确停止计时也撤回自用测量同意；行为不变。
- B（推荐）：计时使用独立授权范围（scope），停止计时不再关闭研究测量；需要处理旧记录的迁移或兼容读取。任何生产记录迁移另行授权。
- C：测量门忽略指定 consent_version；改动小，但把入口特例写进权限判断。

#66 路线不再重问；剩余存活变异推荐先修再合，不把继续当作“带缺口放行”。生产执法启用另行确认。#62 等 #61 换库证据；#64 等推送收口、无全量且名单逐项授权；#76 六行各自授权，保持最后执行。

## 提交恢复与方法沉淀

本轮一次 `git commit` 漏 `-m` 进入 Vim 并超时，未产生提交。核对无编辑器/提交进程、锁无持有者后，将本工作树 `index.lock` 改名为 `index.lock.interrupted-20260923T1151` 保留；未删除锁内容，未动别树索引。后续提交显式 `-m` 且只用 pathspec。

没有新增通用脚本：本轮使用 Git 原生命令完成静态预检，调度与冲突解决仍需语义判断；既有工作树看板和门禁工具继续作为执行入口，不为此另造清单或第二套调度器。可迁移原则是固定身份后验证、分开文本可合与行为通过、旧收据不随目标变化自动生效。
