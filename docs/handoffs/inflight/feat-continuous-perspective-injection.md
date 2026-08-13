# 在途交接 · feat/continuous-perspective-injection

> 指针（2026-08-14）：代码与测试已提交，PR 待 CI。这是 #331 交接里立案第 1 项的落地：视角接进 continuous 主路径。

## 这个分支做什么

生产 continuous 引擎此前对视角全盲：API 验证、存储都过，但 `_run_turn_ledgered` 在 ask_options 构造前返回，模型输入与答案无任何视角痕迹（08-14 生产 smoke 实测）。本分支把视角约束经 control 缝注入 episode 输入，并在交付层署名。

## 当前状态

- 已提交：注入链 orchestrator（共享原语 `active_runtime_prompt`）→ `TurnControlResult.perspective_context` → `build_episode_context` → `ResearchRunContext` → `build_episode_input`；交付层视角激活时前置 `runtime_answer_header`。
- **neutral 逐字节不变是硬契约**：kwargs / 模型输入 JSON / 答案文本三处，空约束时与改动前一致（各有测试锁死）。

## 已验证

- 全量 pytest 4836 过 0 挂（本地，workbench venv）。
- 新增 4 测：投影透传、输入含/不含视角键、adapter kwargs 守卫、orchestrator 端到端（真实 profile 镜头名到达 control + 答案头署名）。
- 进程内真数据 smoke：生产 `FORESIGHT_USERS_DIR` + 生产 sptfei 画像，模型输入 JSON 含「筹码与结构」「历史同构类比」与证据纪律声明（2308 字符）；neutral 无新键。

## 未验证 / 已知边界

- **未做真 LLM 端到端**：注入字节已证实到达模型输入，但模型拿到视角后的答案质量（视角映射 vs 通用话术）未评。
- **生产 8792 跑的是旧快照**，合并后需重部署才生效。
- 答案头只在视角激活时加；legacy 路径 neutral 也带「数据中立」头，两路径 neutral 行为不一致是**存量**差异，未在本分支扩大改动面（改它会破坏 continuous 原样透传契约 + 全部现有断言）。
- CI 的 e2e 3 红（stock deep-dive 追问轮）是**7 月 18 日后就断的存量**：追问句「…是什么」被词法判成定义题、经继承重基混进 required_outputs，契约门打回。昨日基线复现相同，与本分支无关；完整取证与修复方向见 PR #336 评论。独立立案，别顺手修。

## 下一步

1. CI 绿后合并，重部署 workbench 快照。
2. 8792 重跑 08-14 那组 smoke（单视角 sptfei vs 中性对照），验收答案头 + 视角映射语言。
3. 视角答案质量评估（是否需要 judge 侧配合）另行立案。
4. neutral 答案头两路径不一致：要不要统一，产品决策，别顺手改。

## 踩过的坑

- episode 指令文本是指纹锁定的，**动输入不动指令**（`build_episode_input` 是 sanctioned 注入面，见 episode_factory 注释先例）。
- `ResearchRunContext` 尾插字段保位置兼容；`context_factory` 是鸭子类型注入点，新 kwarg 必须条件传，否则不认识它的测试替身在中立轮全炸。
- 断言 `result.content.startswith(引擎原文)` 锁死了 continuous 原样透传——任何无条件加头的方案都会红一片，这是刻意的契约不是测试脆弱。
