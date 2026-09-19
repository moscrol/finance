# P3b/P3c + 返修独立审查

状态：审查进行中

## 当前已知证据（续接时，尚未重新核验）
- 用户固定审查工作树 `/tmp/e2-qc-301dcd9e`，目标提交 `301dcd9e1eef5095424027ffa703bfeab2472cc6`。
- 据续接说明，先前独立 37 针为 36 绿、1 红；待判定项为 `test_late_result_captures_old_scope_not_new_context`，须核验实际执行与超时等待顺序，不能将退出码 0 当作通过。
- 据续接说明，此前服务发生 Concurrency limit 错误；focused 日志含初始隔离环境错误及后续绿结果，尚待逐项读取。
- P3b/P3c 应用 diff、返修 diff 和原探针/日志已保存在 evidence；本次将保留所有证据，若探针有误将另存修正版。
- 本次不修改/提交/部署应用、不读生产数据、不调用金融 API；pytest 仅使用指定 workbench Python。
- 审查为同型号独立上下文，不称不同模型交叉验证；作者全测 9781P 不替代独立判断。

最终结论：待原范围、脚本、日志和关键执行时序核验后更新。

## 续接核验进展
- 已核验 HEAD 精确匹配、git status 为空，读取 AGENTS、产品材料边界及设计 D4/A16；三个保存 diff 的 SHA-256 与指定 git 区间完全相等。
- 已完整读取指定脚本/日志：`independent.log` 明确为 36 passed / 1 failed（0.48s），不是绿；`adjacent.log` 是 281 passed；当前磁盘 `focused.log` 仅见后续 38 passed（1.57s），未见续接文字提到的初始环境错误。不能补造初始错误内容；将另存重跑日志。三个 IO 收据均无禁止尝试（focused 有3个 git 基础设施子进程）。
- 红针静态根因候选已定位：`ToolSpec` 在构造时包装 runner 为 `ToolRunnerAdapter`；原 slow 回调释放后调用 `base.runner` 会二次进入 `_run_tool`，其 deadline.expired 检查在实际 fixture runner 之前抛超时。将保留原探针并用独立跟踪脚本确认，暂不最终判定。

## 唯一红针已判清（最终报告仍在汇总）
- 保持原源码不变的跟踪重跑 `original-late-trace.log` 为预期 1 failed，保存真实 pytest_exit=1。实际顺序：slow 适配器入场未超时 → 约82ms批次返回 tool_timeout → 绑定新scope → 二次 base.runner 适配器入场已过期 → TimeoutError → 旧scope发 tool/error。产品没有把晚结果写给新scope；原探针根本没生成晚结果。
- 修正版另存 `test_independent_scope_v2.py`（差异 `independent-probe-correction.diff`），只改该针构造为单层在途回调，保留原 .08s deadline、wait(3) 和所有原业务断言，新增先后顺序/真实证据/无错误断言。完整 37 passed，IO尝试0。
- `test_late_repeat.py` 无活动QueryLedger/有活动QueryLedger各5次，共10 passed；晚结果均归旧scope，批次 observation 仍为空，有账本时确认不写成功缓存并留 late_result_discarded。没有调大产品超时或加sleep。
- 当前证据支持红针为探针错误而非产品缺陷；P3b实际临时源测试准备以新日志再跑确认后完成最终裁定。
