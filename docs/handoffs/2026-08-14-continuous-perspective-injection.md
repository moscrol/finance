# 2026-08-14 continuous 视角注入 — 已合 main

PR #336 已合入 `main`（`03a00b39`）。已部署生产、生产 smoke 已验：单视角答案带
「当前视角：SPT-Molmansk」署名、走 continuous_episode、语言吃到视角镜头
（分歧/承接）；中性对照无头无污染。

做了：生产 continuous 引擎此前对视角全盲（API 验证、存储都过，但 `_run_turn_ledgered` 在 ask_options 构造前返回，模型输入与答案无视角痕迹）。本轮把视角约束经 control 缝注入 episode 输入，交付层署名。

## 实现与验证（全绿）

- 注入链：orchestrator（共享原语 `active_runtime_prompt`）→ `TurnControlResult.perspective_context` → `build_episode_context` → `ResearchRunContext` → `build_episode_input`；交付层激活时前置 `runtime_answer_header`。
- **neutral 逐字节不变是硬契约**：kwargs / 模型输入 JSON / 答案文本三处有测试锁死。
- 全量 pytest 4836 过 0 挂；新增 4 测；进程内真数据 smoke（生产 sptfei 画像 2308 字符进模型输入）。

## 已知边界

- 部署走 `scripts/deploy_workbench_runtime.sh`，源必须是 origin/main 的干净 worktree（主仓工作树又脏又旧）。health 的 `code_matches_repo:false` 是拿主仓比的仪表噪音，以部署脚本自己的指纹校验为准；快照目录随每次部署换 id，别写死路径，用 `finance-workspace-runtime` 软链解析。
- 答案头只在视角激活时加；legacy neutral 也带「数据中立」头，两路径 neutral 不一致是存量差异，刻意未动（动它破坏 continuous 原样透传契约）。

## 遗留（未做）

1. **质量项**：视角激活时 required_outputs 不含视角段，交付门只按通用契约裁剪，
   模型可只交片段（生产实测单视角 103 字 vs 中性 355 字）。修法方向：contract
   附加视角段验收，或 semantic judge 加检查。**本轮唯一未闭环项。**
2. neutral 答案头两路径不统一 = 产品决策，别顺手改。
3. ~~e2e 深挖追问 3 红~~ 已由 #337 + #339 收（取证在 #337 评论：门前草稿已是缺口桩而 spec 完好，属呈现层选型）。基线现已全绿。

## 踩过的坑

- episode 指令文本指纹锁定，**动输入不动指令**（`build_episode_input` 是 sanctioned 注入面）。
- `ResearchRunContext` 尾插字段保位置兼容；`context_factory` 鸭子类型，新 kwarg 必须条件传，否则不认识它的测试替身在中立轮全炸。
- `result.content.startswith(引擎原文)` 断言锁死 continuous 原样透传——无条件加头必红一片，这是契约不是测试脆弱。
- 生产 API 按 user 分空间：conversations 和 messages 都要带 `user`，视角校验在错误用户空间下会 422。
