# feat/input-understanding-05 · 05 输入理解第一刀

## 这个分支做什么
口语 / 粘贴材料 / 表格 / 代称 / 盘感 / 方法描述直接变成正确研究任务；只改 task_frame / query_understanding / user_task / episode_factory 及测试。合同与全部读数：`docs/superpowers/plans/2026-09-09-capability-upgrade/{progress,blocked}/05.md`；决策快照 `docs/handoffs/2026-09-09-input-understanding-05.md`。

## 决策与被否方案
- 新语义放 TaskFrame 尾部默认字段，为空不进 to_dict/hash；否了新建 InputFrame（第二真本源）、改 ResearchTaskContract（非白名单）。
- 材料身份 = 内容哈希 `m-<sha1>`，跨轮重算；否了存库（无附件存储，B05-5 归 09）。
- 路由只看问题部分、raw_question 留全文；否了截材料（模型要读材料）。
- 身份表 / 假设 / 竞争解释 / 方法候选进 conversation_context（装配层）；否了加 required_outputs（改判官分母）与改 grounding_mode（B05-4）。
- 缺材料确定性追问只在对话块已知时生效（B05-1 = 控制器一行传参）；否了无条件追问。
- 信封层 dated_market_review 只接「日期+复盘」且三件套认不出的说法；否了连「解读」一起收（撞 watchlist 负例锁与冻结三十题契约）。
- 基线真实臂放弃：共享生产额度已耗尽 + frame 级基线已有 unit 读数（1/12）；答案级同题对照归 00。

## 当前状态
四个提交（2b5c354d 实现 / 11206cf9 / 7b7356cb / 7df9cc55 收窄）+ 本次收尾提交，已推 gitea，未合 main（等用户确认）。验收服务器 8797/8798 均已停。

## 已验证
四测试文件 195 全绿；全树 ruff 0；全量 pytest 8342 passed（1 个负载抖动单跑 1.28s 过）。规则层判卷 1/12→11/12。真实入口候选臂（8798@7df9cc55，16:07–16:21）：frame 级 **11/12** 同 unit；4 轮真答案——Q02 按「区分三种解释的当前读数」组织（盘感→竞争解释端到端生效）、Q05 代称解析后真实行情估值比较、Q01/Q04 正常；13 completed / 9 failed（429）。

## 未验证 / 已知边界
- **材料内容使用未验证**：材料轮全撞 429，降级模板只回显问题；material_usage 已剔回显（新教训见 memory：degraded-template-echo）。复验：额度恢复后 `run_05_acceptance.py --only Q06,Q08,C2,C3`。
- Q07 / C3 / R5（缺材料确定性追问）卡 B05-1；LLM 对齐路径真实入口也没兜住（C3#1 实测直接进研究）。
- 基线真实臂无读数（放弃，理由见上）；8797 曾被 macOS 低内存杀掉（双 uvicorn 带 RAG worker + 全量 pytest 并行）。

## 下一步
1. 额度恢复后重跑材料轮 + score，把 material_usage 写回 progress/05.md。2. B05-1 递 06/01（blocked/05.md 有精确 diff）；B05-3/B05-5 递 09。3. 用户确认后开 PR 合 main。

## 踩过的坑
- trace.jsonl 的 `output_summary` 是 JSON 字符串不是对象。
- 降级模板回显问题原文——内容命中类指标必须先剥回显。
- 材料末段「三、我们的判断」会被当问句：问句只认单行 + 疑问/请求形状。
- 验收服务器继承生产 `RAG_WORKER_ENABLED=1`，16G 盒子双实例会 OOM；单臂串行或显式关。
