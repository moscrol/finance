# feat/input-understanding-05 · 05 输入理解第一刀

## 这个分支做什么
口语 / 粘贴材料 / 表格 / 代称 / 盘感 / 方法描述直接变成正确研究任务；只改 task_frame / query_understanding / user_task / episode_factory 及测试。合同与读数：`docs/superpowers/plans/2026-09-09-capability-upgrade/{progress,blocked}/05.md`；决策快照 `docs/handoffs/2026-09-09-input-understanding-05.md`。

## 决策与被否方案
- 新语义放 TaskFrame 尾部默认字段，为空不进 to_dict/hash；否了新建 InputFrame（第二真本源）、改 ResearchTaskContract（非白名单）。
- 材料身份 = 内容哈希 `m-<sha1>`，跨轮重算；否了存库（无附件存储，B05-5 归 09）。
- 路由只看问题部分、raw_question 留全文；否了截材料（模型要读材料）。
- 身份表 / 假设 / 竞争解释 / 方法候选进 conversation_context（装配层）；否了加 required_outputs（改判官分母）与改 grounding_mode（B05-4）。
- 缺材料确定性追问只在对话块已知时生效；否了无条件追问（次轮「这篇」会误问）。控制器传参 = B05-1。
- 方法候选只对照已合入 methodology_backtest 的规则目录报 lifecycle 状态；否了自然语言编译谓词（模块自述不做）。

## 当前状态
已提交 2b5c354d（实现+测试+验收脚本）、11206cf9（docs），已推 gitea，未合 main。全量 ruff 过；全量 pytest 在跑（`~/.finance-runtime/evals/05-acceptance/full-pytest.log`）。真实入口受阻：网关 57244 15:15 起无监听、此前凭证池 429 model_cooldown；`05-acceptance/wait_and_run_05.zsh`（/tmp 同名副本在后台）等网关恢复后自动起 8798/8797 并跑候选→基线。

## 已验证
四测试文件 152→195 全绿（收据 20260909T070641Z）。`judge_05.py unit`：gitea/main 1/12 → 本分支 11/12；链 C1 3/3、C2 3/3、C4 2/2；反向 R1–R4 过。基线树 8797 真实入口 21 轮全 429（环境，非代码）。

## 未验证 / 已知边界
- 真实入口候选 12 题 + 4 链未跑成（网关）；跑完用 `judge_05.py score`（命令在 progress/05.md）。
- Q07 / C3 / R5（不给原文的确定性追问）需 B05-1 一行传参；LLM 对齐能否兜住待真实入口。
- 8798 判官用 grok-1.0.13 + sandbox off（生产钉的 1.0.5 已不在盘上），唯一偏差。
- 代称 12 条、盘感 8 类纯规则；材料判官准入未动（B05-4）。

## 下一步
1. `wait-and-run.log` 见 ALL DONE → 跑两条 score，把 N/12、链、material_usage、episode_health 写回 progress/05.md。
2. 停 8797/8798。3. B05-1 递 06/01；B05-3/B05-5 递 09。4. 用户确认后再开 PR 合 main。

## 踩过的坑
- trace.jsonl 的 `output_summary` 是 JSON 字符串不是对象。
- `/api/health/ready` 503 不是协议错：生产同样 `market_data_consistency=false`。
- 材料末段「三、我们的判断」会被当问句：问句只认单行 + 疑问/请求形状。
- docs 下 .py 也过 ruff（E702 挡过提交）。
