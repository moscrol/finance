# Round-8 附加修复独立复核 · 2026-09-14

## 结论与范围

**原错配费用反例已修；05 仍不签最终放行，新增相邻 P1 × 2。** 不是把新增边界记成 dd5d54aa 引入的回归：两项在父提交 d7fffbed 同样存在。01/02/04 保持既有候选，本轮未发现其新增阻断，不宣称重新完成四轨全量或 06 集成验收。

目标：01 `6cc5748a`，02 `e27b3352`，04 `fcc7838c`，05 `f8540a53`。实查四轨 HEAD 与汇报相符，status 均空。05 修复 `dd5d54aa`；`dd5d54aa..f8540a53` 只有 inflight 与 PROGRESS 两份文档。主检出树有他人改动未碰；在隔离树 `/private/tmp/research-evolution-r8-dd5d-qc` 测试。无 push、main 合并、外呼、生产写入。

## 原修复：通过

`intelligence/services/product_value/summarize.py:157–170` 的联合匹配拒绝 `(attempt2, run1)` 给两次执行作证。提交的新测试在父提交 d7fffbed 第 1047 行 AssertionError，候选通过；独立探针同样确认：

| 输入 | 父提交 | f8540a53 |
|---|---|---|
| 第一次有完整账，第二次三笔费用挂 attempt2/run1 | known CNY 1.39 | unknown；uncovered=[review_model, writer_model] |
| 第二次三笔费用挂 attempt2/run2 | known CNY 1.39 | known CNY 1.39 |
| 第二次只挂 run2 | known CNY 1.39 | known CNY 1.39 |
| 第二次只挂 attempt2 | known CNY 1.39 | known CNY 1.39 |

因此原修复和合法单身份通路有效，不要求撤回修复。

## 新增相邻发现

### R8A-1 [P1] 生命周期先按 attempt_id 折叠，冲突 run 被静默删除

定位（候选行号）：`intelligence/services/product_value/measure.py:267–284`。

`attempts.setdefault(attempt_id, {run_id: ...})` 固定首个 run，之后同 attempt 的开始/结束事件只覆写时间与状态，不核 run 是否一致。下游联合费用校验收到的已经是丢了 run 的执行集合。

公开入口复现（不改收据，只改原始事件）：同任务两次真实执行 run1/run2，只给 run1 writer/review/tool 账；第二次生命周期误复用 attempt1。实测：两个 real-run 描述都提供给 InMemoryEvidenceReader，但收据 `attempts` 仅剩 `(attempt1, run1, ok)`，`status=valid`，`invalid_reasons=[]`，`rejected=[]`，`unknown_cost_components=[]`，试点 `full_cost_status=known, CNY=0.93`，第二次无账完全消失。同一 attempt 的 `run_started=run1 / run_finished=run2` 也复现同结果。

修复要求：费用匹配前先校验生命周期身份唯一性；冲突显式 invalid/incomplete 并阻断完整成本，或保留独立执行及缺账，不能 first-wins 静默吞掉。可先建立规范身份索引，再统一供执行折叠与费用覆盖使用。06 当前观察器按 run_id 派生 attempt_id，本身不会正常生成该冲突；但 05 公开测量合同未验证输入，不能用单个 writer 的生成习惯代替合同校验。

### R8A-2 [P1] 联合校验只作用于 summarize，MeasurementReceipt 仍用 OR 抹掉缺账

定位：`intelligence/services/product_value/measure.py:556–574`，尤其 557–562。

这是原 round-8 错配输入的**另一公共输出**，不是重复报告已修的 summary：`costed_runs / costed_attempts` 仍独立成集合、用 OR 跳过缺口。错配费用 run1/attempt2 同时消掉两次执行的派生缺账。

实测该配对收据：`status=valid`、`unknown_cost_components=[]`、`known_cost_by_currency={CNY:0.93}`、零 invalid/rejected；后面的试点汇总虽然 unknown，但这张收据仍对外表示完整。合法一致身份返回同样的收据状态与费用金额，读收据者无法区分。

依据：05 spec §3 要求覆盖不明为 incomplete、缺账保留未知；`docs/research-pilots/research-evolution/06-integration-contract.md` §5 要求收据 status/limitations 可见，且 unknown 非空时不显示总成本。06 `pilot_io.cmd_rebuild` 独立保存收据，`cmd_show` 与 facade 暴露其 status，故不是一个只在私有中间变量里出现的差异。

修复要求：测量层派生缺账也使用同一联合身份规则（注意 selected）；错配费用可保留审计/已知原始支出，但不得核销任一错误归属执行的缺账，收据必须携带原因并降级。避免只在汇总补另一个特判。

## 复核与收据

- 候选未增加审查文件前：05 模块 `119 passed in 2.80s`；全仓 ruff `All checks passed`。
- 第 4/5/6/7 轮原安全断言合跑 `23 passed`（4+5+6+8）；第 3 轮 `5 passed`；第二轮 `probe_05_extra.py` exit=0。本轮未独立适配重跑硬绑旧 SHA 的第一轮脚本，不将执行方“第 1–7 轮”全部标为独立复验。
- 本轮公开入口安全断言：候选 **3 failed / 4 passed**，父提交 **4 failed / 3 passed**；3 红对应上述 2 个根因（生命周期有两个参数场景）。原错配 summary 是唯一父红子绿，三个合法身份控制始终绿。
- 已核历史全量原件 `20260913T174753Z-dd5d54aa.json`：revision 完整等于 dd5d54aa、dirty=false、dirty_paths=[]、worktree_dirty_total=0、passed=9659、failed=0、error=0、skipped=77、failed_ids=[]、exit_status=0、dependency_gate_bypassed=false。**本轮未独立重跑全量**；收据不记录 xfailed，不能独立核“2 xfailed”。
- inflight 3056B；代码收据和最终 docs SHA 分开叙述正确。
- 完整 JSON、红灯日志、父版本对照、历史收据副本：`~/.finance-runtime/reviews/research-evolution-round8-addendum-qc-20260914/`。

## 复现与后续

仓内归档，避免只留 /tmp：

```bash
QC_TREE=<05候选绝对路径> /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -rf scripts/review_probes/check_product_value_identity.py
```

探针 `scripts/review_probes/product_value_identity.py` 只构造 synthetic 输入，经公开 measure_pair → summarize 计算；单独运行参数为目标树、输出 JSON。检查文件刻意用 `check_` 命名、显式运行，避免审查分支的已知红断言混入业务默认测试，也不标 xfail 掩盖缺陷。

要求下一轮先补两项公开入口回归（收据与汇总都断言）并保留三个合法身份控制，再复跑历史安全断言和干净代码 SHA 全量。06 集成/前端/E2E/registry 仍是最终放行前提。

可迁移经验：**在降维/去重之前校验身份；汇总门只保护汇总返回值，不会追溯修好已公开的中间收据。** 本轮将专用探针归档为可执行检查，不另造通用 harness 清单，也未修改业务实现或既有门禁。
