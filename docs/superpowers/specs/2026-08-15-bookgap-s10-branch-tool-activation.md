# S10 · branch_tool 激活诊断：子研究分支为何从未被走进

- 索引:`2026-08-15-bookgap-index.md` · 靶:第 10 章 + 马书 ch20 派生设计 + 08-14 实测 · 仓:finance · 优先级 P2
- **形态:诊断先行(Phase A = EVAL_ONLY,零行为改动),修复(Phase B)另行裁决**
- **串行依赖:Phase B 若动 `agent_episode.py`,排 dsh 第 5 步与 S1 之后;Phase A 随时可开(live 批遵守 `/tmp/finance-8792-live.lock`)**

## 1. 背景(证据)

- runtime 已有 subagent 原语 [实测]:`intelligence/runtime/continuous_sub_research.py`
  的 `ContinuousSubResearchWorker`——子研究分支带独立预算视图(`root_budget` 子视图)、
  隔离 frame、不发布、丢弃分支正文。隔离设计符合马书「独立侧查询」与「Don't peek」。
- 但它在生产是**休眠的** [实测]:`docs/handoffs/2026-08-14-tool-observability.md` 记
  「branch_tool 现场三次未进路径——GLM 跳过 PLAN」。零件在,协作从未发生。
- aab 第 10 章准则:多 Agent 只在「引入生成时不存在的新信息」时有实质优势;
  分支子研究带工具通道,**属于能引入新信息的那类**,与 semantic judge(S2 之前
  的形态)不同——所以激活它有理论收益,但书同时警告 token 可达 15 倍,
  值不值要靠对照数据说话,不靠直觉。
- 与 S1 的疑似交互 [推断,待证伪]:模型看不见剩余预算时,可能系统性回避
  昂贵的分支路径;S1(状态栏)落地本身可能改变 branch 调用率。

## 2. 目标 / 非目标

- 目标(Phase A):用 triage loop 纪律给「branch_tool 零调用」定 PRIMARY——
  在预注册的分支适格任务集上复现零调用,四阶段分诊,≥3 条可证伪假设逐条判定。
- 目标(Phase A 附带):产出「分支适格任务」的判定谓词并进 eval 夹具,
  供 Phase B 与 S1 后的 A/B 复用。
- 非目标:本 spec 不承诺「必须激活」——若分诊结论是任务分布里分支收益不成立
  (`NO_SYSTEM_FIX`),如实结案也算交付;不动 judge(S2 的缝);不改
  `episode_semantic_verifier.py`(R-24 保留地);Phase A 不改任何 prompt/工具描述/路由。

## 3. 工作面(Phase A)

| 项 | 内容 |
|---|---|
| 冻结失败标准 | 预注册 N≥5 个分支适格任务(判定谓词写死:多子题可并行、单子题需独立检索、题面不含"简答"约束),branch_tool 调用率 = 0 即复现 |
| 取证 | 已有 trace(08-14 三次现场)+ 新批 trace:PLAN 段原文、工具清单呈现、branch_tool 的 description 与 schema、mode_governor 信号 |
| 假设池(至少) | H1 prompt/工具清单未有效呈现 branch_tool;H2 预算不可见抑制昂贵路径(与 S1 交互,标记为 S1 后 A/B 臂);H3 工具描述不满足触发语义(TOOL_DESCRIPTION);H4 mode_governor/frame 分类从不进 PLAN 分支态(ROUTING);H5 任务分布本身不需要分支(NO_SYSTEM_FIX) |
| 报告 | `docs/verification/<日期>-s10-branch-activation.md`,账本新 R 行(来源标「标准 M1 分诊」),fix_type 限 `SYSTEM_PROMPT_FIX / TOOL_DESCRIPTION_FIX / ROUTING_FIX / NO_SYSTEM_FIX` |

## 4. 验收判据(预注册)

1. 失败标准先冻结后取证,判定谓词与任务清单在开批前写进报告(时间戳可证)。
2. 假设逐条 CONFIRMED / REJECTED / INCONCLUSIVE;分不出胜负写
   `ROOT_CAUSE_NOT_CONFIRMED`,不硬选 PRIMARY。
3. H2 不允许在 S1 落地前结案为 PRIMARY(无法单变量消融),只能标 pending。
4. Phase B(若开):修复后同一任务集 branch 调用率 >0,**且分支产物进入终稿
   证据链**(分支检索的 evidence 出现在最终 `evidence_bound` 集合)——只调用
   不消费不算激活;同时报告额外 token/耗时,按第 10 章成本准则给出「值不值」结论。
5. 全程不触碰在途保留地;live 批遵守锁协议与同步窗口互斥。

## 5. 风险

- 分支适格任务集有主观性:接受,谓词预注册 + 检阅方审后冻结,不事后改口。
- 08-14 的三次现场证据可能不足以定层(只有终态):则 Phase A 输出
  `INSUFFICIENT_TRACE` + 最小补埋点清单(EVAL_ONLY),不带着模糊证据硬归因。
- 与 S1 的交互使单变量困难:已用判据 3 显式封堵。
