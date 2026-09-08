# 运行底座防御模式：坑 → 规则（本仓实例版）

> 运行底座 P4（工单 #31，母单 `2026-09-07-runtime-base-endstate-design.md` §6.5 第 3 条 / G10）。
> 每条规则都配一个**本仓真实踩过的坑**（预测台账 `R-*` 编号或交接「踩过的坑」出处）——
> 不抄 dsh `defensive-patterns.md` 那六条：同名的坑写我们自己的实例，没踩过的不编。
> 这份文件是手写的；`docs/runtime/{events,tools,harness-seams}.md` 三张目录由脚本生成，别混。
> `intelligence/tests/test_defensive_patterns_doc.py` 钉住：G10 原句在、引用的每个 `R-*` 编号在台账里存在。

## 总规则（G10）：抛还是回

**`runtime/` 内部用异常，跨 `services` 契约边界只返回结构化结果；hooks / sink / 投影一律不抛。**

- 为什么分三层：异常是「调用方必须处理、否则程序停」的强信号，只适合在同一层内部传播；跨层
  契约（`ResearchHarness` 16 方法、工具 runner、`EpisodeStore`）的调用方是另一拨人写的代码，
  返回结构化结果（带 `code` / `reason` 的对象）让契约本身把「会发生什么」写在类型里，而不是
  写在 docstring 的「可能抛 XX」里；hooks / sink / 投影是**观测面**，观测坏了不能反过来拥有执行。
- 本仓落点：`RuntimeHandle` 用异常表门（`RuntimeHandleClosed` / `RuntimeHandleCancelled`，
  同层驱动方处理）；工具批次把 runner 的一切异常归一成 `ToolCallResult{status, error}`；
  `EpisodeScope.emit` 吞 sink 异常并计数；`_EpisodeLedger._persist` 落盘失败进 `store_failures`
  收据、不抛；`derive_messages` 失败生产侧只计 `derive_mismatch`，测试侧才抛
  （`FORESIGHT_STRICT_DERIVATION=1`）。
- 面试常考：这是「异常 vs 错误码」老题的工程答案——按**谁来处理**分层，不按「严重程度」分。

## 坑 → 规则

| # | 坑（本仓实例） | 规则 | 出处 |
|---|---|---|---|
| 1 | 预算 consume 失败时把模型这轮已经点出的 `tool_calls` 整个丢掉，`stop_reason=deadline_exhausted` 且 `carried_draft_chars=0`——像是模型「知道缺、不去补」，其实是邮箱里的查询被 fail-closed 扔了 | **已经发生的工作不能 fail-closed 扔掉**：外部效果的产出（模型点的工具、跑完的批次）要么结算、要么 flush 后停机，不发明稿、不开下一轮 | `R-20260828-06`；`agent_episode._flush_pending_tools` |
| 2 | `tool_result` / `tool_error` 事件展开漏了 `call_id`（`call.call_id` 就在作用域），意图与结算配不上对；同名工具重复调用只能靠顺序猜 | **意图与结算靠预留的关联 id 配对，不靠名字、不靠顺序**；且 id 只进 ledger 展开，不进喂模型的那个 dict（同一个 dict 同时是模型视图底稿） | `R-20260827-15`；INV-R2 |
| 3 | 预注册号「读当日 max + 1」再落盘，两个 session 各自让路让到同一号上，单日撞号四例、双向避撞不收敛 | **check-then-act 不原子就不是分配**：配额 / 编号 / 座位在副作用之前用锁或登记簿**预占**（`claim_ledger_id.py` + flock） | `R-20260828-01` |
| 4 | 全量门禁一条 `executor_timeout` 族的红：单跑绿、失败文件不在改动面、兄弟树同晚两轮全绿；另有一次「五道绿」读数与树内容矛盾，源头是合流解冲突后没重跑扫描 | **收据要能对上 revision**：读数写 `--expect-revision <tip>`；挂钟类偶红按三态签名判（单跑 / 改动面 / 兄弟树），复跑求干净收据，不许「带红合入回头再修」 | `R-20260827-11`；`scripts/check_test_receipt.py` |
| 5 | Gitea 的 `mergeable` 十张全报 true、两张真冲突；后来又一次：多 merge-base（criss-cross）历史下它拿一个 base 做三方合并，把两边都含的 P0 提交报成 6 个文件冲突，而递归合并干净 | **服务端的「可合并」是缓存不是判据**：本机 `git merge-tree --write-tree` 说了算；栈式分支先前向合并 main 让 merge-base 唯一，再让服务端合 | `scripts/gitea_pr.py` 文首第 2 条；2026-09-08 合入 #624 / #638 / #677 的交接 |
| 6 | 用宿主 `python3` 跑 pytest，71 个失败看起来「完全合理」，实为缺依赖；换 venv 解释器 14 个 | **解释器是判据的一部分**：门禁只认 `.venv-workbench/bin/python`，pre-commit 第一道就拦错解释器；读数里不写解释器等于没写 | `AGENTS.md` 合并纪律；SessionStart 事实注入 |
| 7 | 变异实验后用 `cp` 还原源码：大小相同、mtime 同一秒，Python 沿用变异版 `.pyc`，还原后的测试「莫名」红了两轮 | **源码与字节码缓存是两份真相**：做变异 / 热改要 `rm __pycache__/<模块>*.pyc` 或 `touch` 源文件；把「同秒同大小」记成一类已知假象 | `docs/handoffs/inflight/feat-sandbox-derived-calculation.md` 踩过的坑 |
| 8 | 死循环脚本被 `RLIMIT_CPU` 先杀（`SIGXCPU`，exit −24），墙钟超时还没到，读数把它归成「脚本崩」 | **多重限制先到者要归入同一个语义类**：CPU 限 / 墙钟 / 取消都是「时间到」，读收据的人不该按 kill 方式分家 | 同上 |
| 9 | Seatbelt profile 写 `/var/folders/...`，实际路径是 `/private/var/...`，整条 allow 失效、进程起不来 | **系统级边界只认 realpath**：给 OS 的路径先 `os.path.realpath`，并在收据里记生效的 `enforcement` 档而不是配置值 | 同上；`calculation_sandbox.seatbelt_profile` |
| 10 | `store_failures` 写了三个月没人读：INV-R2 的「落盘失败要有收据」测试只断言了 `attempts == 1`，收据本身不存在 | **写了没人读的字段等于没写**：每个新字段要有生产读者（进 `finish` 收据 / `dump()` / 投影），`check_unread_fields.py` 门禁拦新增；这次把它落进 `finish.store_failures` | 竞态目录 `store_failure_vs_memory_ledger`；pre-commit `unread-fields` |
| 11 | 多个 `return` 点各自清箱 / 各自写终态，十个出口漏一个就丢话 | **终态动作挂在唯一出口上**：`done` 与收件箱清空都挂 `_EpisodeLedger.add("finish")`，不挂十个 return | P3 交接「清箱挂 finish 唯一出口」；INV-R5 |
| 12 | 取消 / 超时 / 未派发共用一个错误码，重试逻辑靠 detail 字符串猜 | **重试语义决定错误码的粒度**：该重试的（超时）与不该重试的（用户取消、零授权未派发）必须是不同码；取消带类型化原因，first cause wins | P1 `tool_not_dispatched` 拆码；INV-R4 |
| 13 | 在飞的模型请求取消了，结算却没落——意图成了孤儿，恢复时不知道那次请求发生没发生 | **取消不吞结算**：取消只挡下一件外部效果，已经开始的效果必须结算完（成功 / 错误 / 取消都行）再写 `finish{cancelled}` | 竞态目录 `cancel_vs_model_settlement` / `cancel_vs_tool_settlement` |
| 14 | 只做「恢复给计划、不重新驱动」的决定没有测试钉着，下一个人可能顺手让 `restore()` 写点东西 | **只读操作要有「一字不写」的钉**：`restore` 在 resumable / already_terminal 两种处置下事件数与状态逐字节不变（只有截止已过的 `closed` 才合成并落盘） | 竞态目录 `restore_vs_inflight_drive`；INV-R3 |

## 与 dsh 六条的关系

dsh `docs/defensive-patterns.md` 讲的是它自己的坑（Cordis 插件树、TS 类型边界）。这里只保留形状层面的三条共识——**观测不拥有执行**、**意图先于效果**、**只读要可证明只读**——其余按本仓实例写。将来某条规则在本仓再没有实例支撑（机制拆了），把那一行删掉，不要留成教条。
