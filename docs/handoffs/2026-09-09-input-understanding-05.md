# 2026-09-09 · 05 输入理解第一刀（feat/input-understanding-05）决策快照

写完不改。在途状态看 `inflight/feat-input-understanding-05.md`，读数与命令看 `docs/superpowers/plans/2026-09-09-capability-upgrade/progress/05.md`，范围外需求看同目录 `blocked/05.md`。

## 背景

能力升级任务包（`docs/superpowers/plans/2026-09-09-capability-upgrade/INDEX.md`）把 05 定义为「口语、材料、盘感直接变成可执行研究任务」，白名单只有 `task_frame.py / query_understanding.py / user_task.py / episode_factory.py` 的输入上下文装配及其测试，不改判官准入与 runtime 预算。任务 0 要求先核验 Workbench 真实接受哪些输入、冻结 12 题、采基线。

任务 0 的两个决定性事实（[实测]）：

1. 对话入口只接受一个 `content` 字符串，没有附件、材料身份、表格解析；粘贴材料首轮混在问题里跑正则路由，次轮只以「历史对话、不得当作证据」的形态存在；`classify_reference` 不认「这篇 / 这份」。
2. 真实流量 1594 条消息里没有任何带原文、带表格、两家代称的问法；多轮线程只有 10 条。所以「带原文 / 数据表 / 代称」三个槽位只能自拟，冻结文件逐题标来源。

## 按发现顺序

1. 读四个白名单文件与调用点：TaskFrame 是 frozen dataclass，`to_dict()` 被 `episode_protocol.build_episode_input` 原样放进模型输入 → 新增字段可直达模型，不必碰 runtime。`UserTask.user_premises` 有落点但生产从不填。
2. 控制器 LLM 只输出 `route_id,confidence,reason,user_goal,assumptions,ambiguities`；`task_frame._alignment_messages` 生产无调用方。`decide_turn` 拿到对话块但不传给 `build_task_frame`——这一行决定了后面 4 项读数（B05-1）。
3. 07 侧：`methodology_backtest`（propose / rules / lifecycle 队列）已合入，谓词是白名单标签短句，自然语言不编译；07 自己的 `method_validation` 未合入。方法候选因此只能「结构化 + 未验证 + 对照已登记规则报状态」。
4. 规则层基线（gitea/main，控制器 LLM 关）：1/12。失败形状：「8.18的复盘数据你怎么解读」落通用、timeframe None；代称主体空；贴研报被材料正文里的题材词路由成 theme_analysis、材料日期触发日历假设；「龙头不涨了…这条线」落 chat 不追问。
5. 真实入口基线：21 轮全部 3 秒终态「模型服务不可用」，`continuous-episode.json` 里 sol/terra 全 429 `model_cooldown`（reset 1h14m）；15:15 起网关 57244 无监听。生产 8792 同池同网关。判官二进制 1.0.5 已不在盘上（生产启动器仍钉它）。
6. 实现（见 commit 2b5c354d 正文）。第一版材料切分把研报末段「三、我们的判断」当成问句（「判断」在问句标记表里）——问句标记收窄为单行 + 疑问/请求形状。
7. 新增 `dated_market_review` 信封分支时踢红既有测试「2026-08-14涨停家数多少 是 quick_fact」——补回 turn_controller 同款守卫（单指标 / 名单不算复盘）。
8. 「那它的风险点呢」不点名材料：身份表对代词短追问照带、不断定指代；带自己主语的新问题不带。
9. 提交被 ruff E702 拦（docs 下的判卷脚本用了分号一行两句）→ tokenize 切行。

## 决策对比

| 决策 | 备选 | 评价 | 结果 |
|---|---|---|---|
| 新语义落 TaskFrame 尾部默认字段 | 新建 InputFrame；改 ResearchTaskContract | 第二真本源会漂；契约不在白名单且改判官分母 | 采用；为空时 to_dict/hash 逐字节不变，50 个测试文件的位置构造不受影响 |
| 材料身份 = 内容哈希 | 存库 / message 字段 | 没有附件存储；哈希跨轮跨进程可重算 | 采用；`materials_in_conversation` 从对话块找回同 id |
| 路由只看问题部分 | 截掉材料再路由 | 模型要读材料本体 | 采用；raw_question 保留全文 |
| 身份表/假设/竞争解释/方法候选进 conversation_context | 新 required_outputs；改 grounding_mode | 前者改判官分母（01），后者是材料当绑定源（B05-4） | 采用装配层块 + 处理规则 |
| 缺材料确定性追问只在对话块已知时 | 无条件追问 | 次轮「这篇」会误问；对话块未知交给 LLM 对齐（现状） | 采用；B05-1 接上即 12/12 |
| 方法候选对照已登记规则报 lifecycle 状态 | 自然语言编译谓词；直接跑回测 | 模块自述不编译；回测是 IO 且归 07 | 采用，未匹配报「未登记 + 登记入口」 |
| 验收服务器沿生产启动器 export 行 | 手写 env | 与 8792 同 provider 链/档位/判官才是同条件 | 采用；判官二进制显式指 1.0.13+sandbox off 是唯一偏差 |
| 候选先跑、基线后跑 | 基线先 | 共享凭证池，交付物优先 | 采用（waiter 串行） |

## 验证与收据

- 四测试文件 195 passed，收据 `~/.finance-runtime/test-receipts/20260909T070641Z-5eb24515.json`（多树并发下 latest.json 会被覆盖，按时间戳文件取）。
- 规则层判卷：`~/.finance-runtime/evals/05-acceptance/unit-baseline.json`（1/12）、`unit-candidate.json`（11/12）。
- 真实入口：`real-baseline/`（全 429，环境）；候选待 waiter。n=0，不许读快慢与答案质量。

## 后续要做 / 不要做

- 要做：B05-1 一行传参（06/01）；09 接理解卡与第二刀输入面；跑完真实入口后回写 progress/05.md。
- 不要做：不要为了让 Q07 过而在 `build_task_frame` 里无条件追问；不要把材料数字写成市场事实（身份表规则已写明）；不要在网关 429 时批量跑验收——同一凭证池会把生产也拖进冷却。
