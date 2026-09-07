# spec/runtime-base-endstate · 运行底座终局（pi / dsh 工程设计补齐）

更新：2026-09-07 · 树 `/Users/a77/fwp-wt-runtime-base` · 基线 `gitea/main@504cbbc9`

## 这条线做什么
用户拍板「换不了底座，就把 pi / dsh 的工程设计里我们欠缺的补上，达到他们那种运行底座的效果；领域 harness 另由 agent 打磨」。母本 `docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md`：六条不变量 R1–R6、十条 [实测] 差距 G1–G10、五阶段 P0–P4、与 harness 的文件级分工（§5）、待拍板五题（§12）。

## 当前状态
- 终态稿已落，**待用户审 §12**（未拍板前按推荐执行）。工单 INDEX 登记 #27 母单。
- **P0 与本分支同落**（零行为改动）：`services/episode_messages.py` `derive_messages` + 三处补账（`tool_result.model_content`、新 kind `model_input` / `prompt_assembled`）+ 请求前派生断言（生产计数不炸、测试抛）+ 投影默认剔正文只留 hash + `scripts/gen_runtime_catalog.py` 三张目录与保鲜测试。进度看本文件下一次更新或分支提交。
- P1–P4 未开：各开工单与分支，编号分派时取。

## 卡点 / 需要用户的
1. §12 五题拍板（存储后端 JSONL vs SQLite；拆码要不要 live 探针；重启后只登记还是自动恢复；P3 Workbench 端点本轮做不做；编号方式）。
2. 与 harness 那拨 agent 的分工以 §5 为准；两处接触点（`ToolSpec.replay` 字段、`admit_inbox_message` 方法）分别在 P2 / P3 开工前单独过。

## 下一步（本线）
1. P0 代码 + 夹具 → 分支门禁（ruff / layer_audit / 全量 pytest）→ 收据 → 开 PR（不合，等用户）。
2. 用户审过 §12 后：P1 开单（消息类型 + `CancelCause` + `tool_not_dispatched` 拆码，一次 live 探针）。

## 不要做
- 不动 `research_harness.py` 16 方法语义、不动 90/60/30、不动 Evidence Ledger / verifier。
- 不 import pi / dsh、不拷源文件、不把 lanes / Cordis / LLM 压缩当本线缺口。
- 不在本分支切 8792。
