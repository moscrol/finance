# feat/ranking-scenarios-10 · 能力升级 10 号单（排序与情景）· 2026-09-09

## 这个分支做什么

多对象排序题（「英维克、申菱环境、高澜股份谁更值得优先研究」「如果铜价回落 20% 排序怎么变」）此前落 theme_analysis / news_impact，名单加形容词就能过门。本分支加 `intelligence/services/ranking_contract.py`（沿 scenario_tree / track_contract 的表达层惯例，零新数据源）：固定表头公司矩阵（优先级 1..N）+ 财务传导 + 竞争解释（≥2 + 区分变量）+ 改判条件表（↑/↓）+ 下一步；两条引擎都注入；缺件以 `ranking_*` 合成 id 走既有 contract_rewrite 修复；`apply_scenario` 按改判条件表箭头**机械再排序**（不给权重/概率），再排序追问把上一轮矩阵的机械基线注进 episode 指令，收据含 `rerank_consistent`；改判条件登记 `checkpoints.jsonl`（source=`ranking_flip_condition`）、`foresight` 渲染——排序输出成为 07 回检 / 09 续研的输入。

提交 `444e520e`（基 `gitea/main 5eb24515`），已推 Gitea，**未合 main、未切生产**。范围合同 `docs/superpowers/plans/2026-09-09-capability-upgrade/10-ranking-scenarios-goal-brief.md`；冻结六题 `10-frozen-questions.md`；进度 `progress/10.md`；范围外 `blocked/10.md`；验证 `docs/verification/2026-09-09-ticket10-ranking-scenarios.md`（附录存档全部验收脚本，/tmp 不持久）。

## 决策与被否方案

- 表达层契约而非新题型/新数据块 / 否 改 route_table 加 ranking 题型——题型改动影响全路由面，契约按词面注入对非排序题零改动；Q3 被路由成 news_impact 也能拿到契约。
- 机械再排序用「箭头 × 1.5 位次」稳定重排 / 否 让模型自由重排——反向验证要求「只换文案不能改推导」，机械基线让 Q6 可程序判定；模型可据证据偏离但必须在「变动原因」列给依据。
- 缺件并入 `missing_outputs` 复用 track_contract 的 contract_rewrite 通道 / 否 进 verifier issues——#224 放行门吃 issue 前缀，生造文案会改门禁（track_contract 注释里的先例）。
- 改判条件进既有 `checkpoints.jsonl` / 否 新台账——台账地图规定新增台账先登记，且 07/foresight 已消费 checkpoints。

## 当前状态（按四项报告）

| 项 | 状态 |
|---|---|
| 已实现 | ✅ 44 条新单测全绿；ruff 全仓 0；unread-fields / layer_audit / path_literals 无新增；全量 pytest 8340P/3F（三条计时 flake 单独重跑全过，收据 `20260909T073156Z-5eb24515.json`；合入前需空闲机器再拿一次干净绿收据） |
| 已进默认入口 | ✅ 代码层实测：契约注入 episode `question_type_rules` 与 ask_synthesis contract_parts，`skill_mode=hybrid`（UI 默认）下真实 run 收据在 `continuous-episode.json` |
| 真实验收 | ⏳ 第一份真实差分已拿到（见下）；完整六题配对批跑排队中 |
| 生产生效 | ❌ 按合同不合 main、不切生产 |

**第一份真实差分（第一轮 Q1 对，判官同等不可用条件下 draft 层可比）**：候选臂 `run_20260909_161136_249649` draft 1473 字，`ranking_contract` 收据 matrix=4 行 / flip=3 / 竞争解释=2 / 下一步=3 / **缺件=0**，1 轮修复后 completed；基线臂同题 812 字散文、无矩阵无改判条件。

## 验收批跑状态（接手者先看这里）

- 两臂旁路实例：8815=基线（`/Users/a77/fwp-wt-ranking-baseline-10`，detached 5eb24515 干净树）、8816=候选（本树）；users 目录隔离 `~/.local/share/finance-workbench-ticket10/users`；**都已带 `LLM_JUDGE_GROK_SANDBOX=off` 修复重启**（16:47，pid 45120/45121，cwd 已核对）。
- 批跑进程 `/tmp/ticket10/paired_batch.py`（16:35 启动）在睡网关冷却（gpt-5.6-sol 冷却 16237 s，**约 21:05 自动醒来跑 q1..q5 两臂**，Q6 为 Q2 同会话追问）。结果落 `/tmp/ticket10/paired/{base,cand}/q*.json`；第一轮存档 `/tmp/ticket10/paired-r1/`。
- 批跑完成后：`python3 /tmp/ticket10/summarize.py /tmp/ticket10/paired --md` 出汇总表，填进验证文档 §4.2 与四项报告，再按判卷点（`10-frozen-questions.md`）逐题打分。
- 两处**运行环境**故障已定位并绕开（不是本分支代码问题，生产也会踩）：① launcher 判官二进制钉死在已被自动更新清掉的版本化路径 + 1.0.24 `--sandbox read-only` 本机拒启 → `blocked/10.md` 前两行，修法两行（symlink + sandbox off），归运行底座/用户；② 共享网关 429 无退避、单深题 12+ 模型调用可触发整模型 75 分钟冷却 → 建议归 06/运行底座。

## 未验证 / 已知边界

- 表达契约对模型是**引导**不是硬闸：模型不写矩阵时走 contract_rewrite 修复轮，修复预算耗尽仍可能发无矩阵稿（此时收据 `missing_outputs` 非空，评测可见）。
- `apply_scenario` 的 1.5 位次步长是把「↑=上移一位」翻译成稳定排序键的确定性规则，不是校准过的量；两箭头同向叠加未在真实题验证。
- 基线臂离线复用候选树解析器量结构（解析器确定性、两臂同尺），但基线代码里没有 `ranking_contract` 收据，episode dump 层不对称——汇总脚本已注明。
- 冻结题判卷点里「独立评审只看匿名前后答案」尚未执行（需批跑完成后由验收方/用户做）。

## 下一步（按序）

1. ~21:05 批跑自动恢复；若再遇冷却脚本会继续睡。盯 `/tmp/ticket10/paired/paired.log`。
2. 跑 `summarize.py`，填验证文档 §4.2、§6 四项报告；对 Q6 检查 `rerank_consistent`。
3. 空闲机器重跑全量 pytest 拿干净绿收据（上次 3 条计时 flake 与另两棵树并发全量有关）。
4. 合并回 main 等用户确认；合入后能力图谱该行去掉 `@branch`（`~/agent-memory/10_knowledge/finance-agent-capability-graph.md` 已有在途行与变更记录）。
5. 把 `blocked/10.md` 前两行（launcher 判官两处、网关退避）转给运行底座负责人。

## 踩过的坑（可迁移）

- 判官二进制钉版本号路径会被 grok 自动更新清掉；新版 1.0.24 还需要 `LLM_JUDGE_GROK_SANDBOX=off`（本机 `--sandbox read-only` 因 `/var/run/docker.sock` 符号链接拒启）。诊断用一次 `complete_grok_cli` 同款 argv 手跑，别烧整个 episode。
- 共享网关探活别用 `max_tokens=1`（会被当 availability probe 拒），用 `max_tokens≥3`；429 正文里有 `reset_seconds`，睡它而不是盲目重试。
- 一道深题（sub_research 三分支）≈ 12+ 模型调用，足以把整个模型打进冷却——批跑要按题间隔预算，且每题跑前重探。
