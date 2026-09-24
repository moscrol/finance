# RE06 合并候选 0bd11ece 审查

2026-09-14。结论：退修，暂不放行合并。Standards 1 个 P1（行为已证实的建模问题，非独立硬规范违规）；Spec 1 个 P1、2 个 P2。

## 固定范围

- 代码候选 `0bd11ece5ad86dc172a3be47fc08db335f4f598e`，基线 `1fef3d276d0e251158803fc09d5a81e60d79241b`。
- `git diff 1fef3d27...0bd11ece` 为本批差异；候选父节点精确为 `7abaa938` 与 `1fef3d27`。
- 06 最新交接 `5290852c` 只更新 inflight 与 BLOCKED，两者不在候选内；已作为补充交付说明读取。
- 原候选树 `/Users/a77/fwp-wt-merge-re06` 保持干净。归档/复验树为 `/Users/a77/.finance-runtime/reviews/re06-merge-0bd11ece`，仅增加本报告、审查探针与交接。
- 06 facade、run_observer、消息存储、API app/router 与 `7abaa938` 无差异；合流主干没有修掉既有 Y1/Y2。
- 使用 `code-review` 双轴审查；代码地图查询返回 empty，未从空图推导架构，定位依据为 Git diff 与直接源码。

## Standards

### S1 / Y2 [P1] 来源读取错误被解释为无冲突

位置：`intelligence/services/research_evolution/facade.py:1367-1368,1386-1388`；消费点 `1024-1032`。

`_source_message_launch` 将 `OSError/ValueError` 转为 None；新增消费校验遇 None 即放行。
实测先把运行登记给 B，再落源消息明确指向 A，正常终态折回会拒绝；仅让消息 reader 抛 OSError，
相同折回便写入 `rejudgment_failed`，B 从 `rejudgment_requested/revision=1` 变为 `open/revision=2`。
恢复读取后错误状态仍在台账中。

这是 Primitive Obsession 启发式下已证实的行为问题：None 混合了 absent、pending、error 三种权限不同的状态。
台账地图要求关联证明“本次复核发起”，但未规定必须采用某种类型，故不声称独立硬规范违规。
修复应让来源读取故障保持待复核、恢复后重试；不得将错误当作已确认的裸 run。

## Spec

### F1 / Y1 [P1] 消息落盘前取消 run，会消费其他维护请求

位置：`intelligence/services/research_evolution/facade.py:1381-1388`；终态消费 `1024-1032`。
真实消息创建顺序见 `intelligence/api/app.py:2957-3016`。

run 创建后已可查询/取消，用户消息尚未落盘；此窗口里显式抢登到 B 后取消 run，
源消息 reader 返回 None，终态折回把 B 从 requested/1 改成 open/2。
继续原消息持久化后可核实启动坐标实际指向 A，B 的错误事件没有回滚。
这违反 X2 的“矛盾链接只留审计、不得驱动状态”以及 06 §4.2 的原对象/维护项/来源版本关联合同。

修复需在 run 可被消费前保存可信启动身份，或区分“消息来源尚未就绪”与“已确认无来源”。
未就绪时不能迁移维护项；来源就绪后允许恢复。合法裸 run 的显式登记合同仍需保留。
Y1 与 S1 共享状态混淆根因，覆盖终态先到、读取故障两个独立触发条件，不另计共同根因。

### F2 [P2] I11 的关闭测量没有实际生效

位置：`intelligence/services/research_evolution/run_observer.py:61-70`；无条件注入见 `intelligence/api/app.py:2451`。
规格 06 §5：“关闭测量不影响核心研究；关闭前后的分母与缺口都可解释”；I11 要求关闭后继续研究。

真实 API 探针依次提交同一会话的 `consent_changed(grant logging)` 与 `withdraw logging`，均 accepted；
随后通过消息 API 发起研究并完成，仍新增 `run_started/run_finished/cost_recorded`。
观察器和前端未接测量启停状态。现有 `test_research_evolution_api.py:682` 的 I11 只做绑定/认领，
不执行关闭也不启动研究，因此不能证明 I11。应补前后端控制与实际关后运行的验收。

自用 `workbench-self-use/v1` 与真人试点分区是已说明的设计，不能据此豁免 I11。
本项依据关闭测量的工程合同，不把真人试点授权规则或付款要求扩大到自用功能。

### F3 [P2] I14 尚缺前端计时接线，不能签完整工程交付

位置：`docs/superpowers/plans/2026-09-13-research-evolution/06/BLOCKED.md:24`。
规格 06 I14 要求“应用内活跃时间可暂停，端到端耗时保持完整”，§8 将 I01-I16 走通列为工程硬条件。

BLOCKED 已明确还需补 `visibilitychange` 上报和浏览器验收；源码核实前端没有对应事件生产链，
仅下游 05 时间计算有测试。此项是普通工程缺口，不依赖真人授权；5290852c 修正分类没有补实现。
应补接线与验收，或明确批准缩小本次交付范围。全绿现有测试无法替代这项证据。

## Q2 与合并说明

- 从工程判断，支持用人工确认作为过渡：它避免把普通聊天判断按会话和时间误认成复核成果。
- 当前 completed 分支没有自动成果归属通路；不传 `new_judgment_ref` 一律待复核。准确代价是当前所有成功复核都多一次显式确认。
- 此建议不代表用户已经接受 Q2，也不代表合并或部署已获授权。接受 Q2 不能消除上述四项。
- I13/I15 的真人/未来结果证据仍按 pending 处理，本次未追加为实现缺陷。

## 验证

| 检查 | 证据 |
|---|---|
| 原 X1/X2 + rework/API + 原样 Y1/Y2 | **81 passed / 2 failed**；失败仅 Y1/Y2，44.53s |
| 上述收据 | `~/.finance-runtime/test-receipts/20260914T074137Z-0bd11ece.json`；dirty=false 指代码前缀，worktree_dirty_total=1 是新审查探针目录 |
| I11 新探针 | **1 failed**，2.50s；撤回 accepted、研究 completed、仍写三类测量 |
| I11 收据 | `~/.finance-runtime/test-receipts/20260914T074727Z-0bd11ece.json` |
| 执行方全仓收据核实 | `20260914T064917Z-0bd11ece.json`：10211 passed / 0 failed / 77 skipped / exit=0，dirty=false，worktree_dirty_total=0，未绕依赖门禁 |
| 差异完整性 | `git diff --check 1fef3d27...0bd11ece` 通过 |
| 本轮完整 pytest / 前端 / E2E | 未重跑；已有确定性阻断，不把执行方结果冒称本轮独立验收 |

首次从外部 round8 路径执行 Y1/Y2 也双红，但测试 hook 按测试文件位置生成 `d51b5e6c` 收据，
不将那份当成本候选收据。原样复制探针到独立候选树后重新执行，以上两份才是正式引用。

重放（在本审查树，主树规定解释器）：

```bash
env PYTHONPATH=. /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -s docs/verification/re06-0bd11ece/test_review_round8.py docs/verification/re06-0bd11ece/test_review_measurement.py
```

修复后保留原探针断言并使其转绿，保留原 X1/X2、Q2、R7 和 API/rework 套件通过；另补 I14 浏览器验收。
未修改应用、未合 main、未 push、未部署、未触碰生产用户数据。
