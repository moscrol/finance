# 技能超时测试的任务生命周期收口 · 2026-09-23

## 背景与发现顺序

#883 已合 `2edbe4c46595cbea3eb3abe04fe84a7bd5afd55e`，#885 已由它承接关闭。用户随后要求“继续推进直到可以收尾”（pi session `01a0cbdf-8033-71c3-9314-9cf6c26bc033`，message `ddd61757`，2026-09-23T08:33:04.057Z）。先前“继续推进，可以合并的内容你就合并”的授权仍见同 session message `7ca1305d`；原文抽取在本轮 `authorization.json`。

在实际合并提交的独占干净检出中，两份冻结答卷的完整 JSON 与合前一致，材料题 1 条、行情题 3 条，CLI 均按预期退出 1。合后四文件定向却出现 213P/1F（collected 214）：`test_skill_timeout_degrades_one_module_and_continues` 固定断言 `task_may_continue is True` 失败。原五个修复回归不是本次失败项。这个新红不改写旧候选的完整绿收据，也不能被旧绿覆盖。

原失败 run `run_20260923_164637_909239` 的 `skill.result` 已记录：slow-skill 为 degraded、警告为执行超时、elapsed_ms=1298、task_may_continue=false；fast-skill completed，最终 run completed。旧 `_SlowSkill` 只睡 1.2 秒，技能预算 1 秒；记录降级与模块期间，工作线程可能已经结束。生产字段按事件构造时的 `not future.done()` 取值，false 是合法结果，不是漏做降级。

## 决定

| 采用 | 不采用 | 理由 |
|---|---|---|
| 用 Event 控制工作线程，分别在超时事件构造前完成、或持有至事件落盘 | 把 sleep 加长，或只删掉状态断言 | 两种状态都合法；要验证各自的精确值，不靠 200ms 调度余量 |
| 按该技能实例识别实际 Future，等待 `future.result` | 把技能方法里的 finished 标志当 Future 已结束 | 方法返回与 Future 结算仍是不同观察点 |
| 仅本测试实例的 add_degrade / _emit 控制时序，finally 放行并等待 Future | 改生产超时、事件字段或线程池 shutdown | 失败来自测试假设，生产行为与字段语义一致 |
| 注入确定性 answer_query_fn，并清除模型钥匙环境变量 | 顺带执行真实知识库检索 | 本用例验证技能超时后继续执行，后续检索不参与该断言；真实检索覆盖仍在其他集成用例 |

测试保留运行完成、超时警告、fast_result 模块、degraded 事件及 retrieve 耗时断言。两个参数分别要求 task_may_continue=true / false，不放宽为“任意布尔值”。原 sleep 夹具只在这一用例使用。

## 已验证与原件

证据根：`~/.finance-runtime/reviews/claim-scope-postmerge-closeout-20260923/`。

- `targeted.log`、`targeted.xml`、`targeted-receipts/gate-l0sKrbus/pytest.json`：实际 main@2edbe4c4 的 213P/1F，Ruff 通过；原现场在 `basetemp/`，原检出在 `checkout/finance-workspace-private/`，保持不改。
- `material.json`、`market.json`：合后完整 JSON 与上一轮 `retry-03/` 相等，SHA256 也一致；不是实时重新作答。
- `controlled-red.log/.xml`、`controlled-red-basetemp/`：夹具初稿误把 Context.run 当技能方法，2F 仅为夹具设置错误，不能作为原缺陷的复现证据。
- `controlled-red-02.log/.xml/.patch`：修正夹具绑定、保留原 True 断言，稳定 1P/1F；完成于事件前的参数失败，仍运行的参数通过。
- `controlled-green.log/.xml`：断言改为与受控状态一致后 2P。
- `modules.log/.xml`：离线判据、CLI、Workbench API、会话集成和编排器五文件 320P。这些是未提交开发树的定向读数，不是完整门禁。
- 冻结提交后的完整门禁只读 `gates/`；最终状态、确切被测 SHA、合入与清理从树外 `closeout.json` 及 PR 回读。当前文档不预填尚未完成的门禁结果。

## 范围与后续

代码差异只在 `intelligence/tests/test_workbench_conversation_integration.py`。不改生产超时、取消、终态或 `shutdown(wait=False)`，不操作 8792，不启动 #75 K3 / #76 L5 验收或 claim-scope 运行时接入。

后续以本分支实际冻结 head 跑完整门禁；主干漂移则核对组合，不能移签。新 PR 承接本次合后新发现，不重开 #883/#885。保留所有历史红记录与他人工作树。

复用既有门禁、收据校验与 Gitea 工具，未新增通用脚本。可迁移方法是“超时不等于仍运行；断言应绑定观察时刻的实际任务状态”，不为这一测试新增生产生命周期抽象。
