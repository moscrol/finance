# RE06 第八轮复审：fdb5f91d / 代码 7abaa938

日期：2026-09-14。结论：**继续返修；X1 可关闭，X2 尚未闭合。**

固定候选 `fdb5f91d`；对比 `b5ecc298...fdb5f91d`，即第七轮代码与交接两提交。
独立检出 `/Users/a77/.finance-runtime/reviews/re06-round8-fdb5f91d`，分支 `codex/review-re06-round8-fdb5f91d`。
主检出树有他人改动，本轮没有使用它的应用内容；只借用规定的 `.venv-workbench` 解释器。

## Spec 轴：P1，源消息落盘前取消 run 仍能消费错误维护请求（Y1）

位置：`intelligence/services/research_evolution/facade.py:1024-1032,1381-1388`；
真实取消入口 `intelligence/api/app.py:2747-2766`，消息创建顺序 `2958-3016`。

新增检查把“消息尚在持久化、查不到坐标”作为无冲突放行，假设消费一定发生在消息落盘之后。
但 run 创建后已能通过公开取消接口进入终态，不必等待执行器启动。

最小复现（真实 API、01 状态机、writer，合成用户，确定性执行器）：

1. A、B 均发起复核；通过 messages API 启动明确携带 A 坐标的 run。
2. 在用户消息落盘前暂停该请求。GET runs 已能读到 run；显式抢登 B 返回 **200**，保留原 X2/R7 setup。
3. 源消息仍未落盘，调用真实 `POST /api/runs/{id}/cancel`，返回 **200 / cancelled**。
4. 观察器及确定性恢复折回把 B 从 `rejudgment_requested/revision=1` 变成 **open/revision=2**，追加 `rejudgment_failed`。
5. 放行源消息，核实真实消息坐标指向 A；原消息请求返回 202，B 仍错误地保留 open/2。

这违反前轮 `re06-9266407f/REVIEW.md:48-50` 的来源就绪顺序约束，以及本轮
`re06-9266407f/REWORK.md:31-32` 的“窗口期矛盾链接仅作审计，不得驱动状态”。
原 X2 等源消息落盘再让执行器失败，覆盖不到本交错。Y1 连续两次独立执行红，合并归档探针再次红。

修复要求：在 run 对外可查询/取消后，仍须能判定它是已确认的裸 run，还是来源尚未完成的消息 run。
来源未就绪的终态不得消费维护请求；身份就绪后可恢复折回。实现可用发布前保存的可信启动身份或明确的
pending 状态，不能继续把“暂时没有读到”当作“已经确认无来源”。保留合法裸 run 合同。

## Standards 轴：P1，来源读取故障会重新激活已拒绝的矛盾链接（Y2）

位置：新增 `facade.py:1386-1388`；所调用 reader 在 `1365-1368` 吞 `OSError/ValueError` 返回 None。

真实存储场景：run 先按裸 run 合法登记 B，源消息随后明确保存 A 坐标，run failed。
正常折回已正确拒绝，B 保持 requested/1。此时仅让 `ConversationStore.load_messages` 抛出
`OSError`，再次折回却返回 **accepted/rejudgment_failed**，B 变为 **open/2**。
恢复 reader 后重读状态，错误事件确实持久化；`_run_continuation` 也吞同类错误，因此后续不会阻止写入。

规范轴没有发现独立的硬规范违规；这是带有已证实业务后果的 Primitive Obsession 启发式观察：
用同一 `None` 表达读取成功无来源、未就绪、读取故障，掩盖了它们不同的状态迁移权限。
行为后果同样违反 X2“矛盾链接不得驱动状态”。独立子审探针复现两次，主审归档为 Y2 后再次复现。

修复要求：读取失败返回可识别的 unavailable/error，终态保持 pending，恢复读取后重试。
不得将读错误折算成裸 run；本反例只注入读取故障，没有伪造判断或修改候选源码。

## 已关闭与边界

- **接受路线 B**：前轮已允许全显式过渡；本轮交接与 Q2 明确调整，删除自动挑判断属于授权范围。
- **X1 可关闭**：原样 X1 通过；不存在/原对象/跨会话/过早判断校验保留，新增已消费检查位于同一 owner 锁内；确认同键重放通过。
- **原 X2 场景已通过**：接受侧不追加矛盾归属，来源已可读时终态能拒收；Y1/Y2 是剩余未覆盖路径，不声称本轮新引入。
- **补偿审计行不另报问题**：第七轮快照已说明补偿可建坐标匹配链接、旧矛盾行保留审计；不能仅凭物理行数升级成新的错归属结论。
- 生产调用点核对为 `subconscious.py`；测试和 E2E fixture 另有 writer 调用。未把尚未扩展的研究 turn writer 另列阻断。
- 分支确实已含 01/02/04/05 合并与 I17。本轮在该组合候选审查，没有冒称纯 06 分支。
- 未重做沙箱根因诊断；接受“检出位置敏感”的有条件口径，不能写死嵌套沙箱根因。

## 验证证据

| 检查 | 本轮实际结果 |
|---|---|
| 仓内五套件 + round3-7 原探针 | **129 passed**，59.95s；收据 `~/.finance-runtime/test-receipts/20260914T064830Z-fdb5f91d.json` |
| round2 原外部探针 | **10 passed**，7.59s；路径 `/Users/a77/.finance-runtime/reviews/research-evolution-06-ba10747d/test_review_contracts.py` |
| 历史组合合计 | **139 passed**，分两次执行，不是另一次整套命令 |
| 新 Y1/Y2 | **2 failed**，均为目标业务断言，见 `probes.txt`；Y1 单独复跑见 `y1-repeat.txt` |
| 全仓 Ruff；最终新增探针 Ruff | **通过** |
| 执行方全量收据核实 | `20260914T060312Z-7abaa938.json`：**10141 passed / 0 failed / 77 skipped**，dirty=false，dependency_gate_bypassed=false，exit=0 |
| 代码与交接一致性 | `git diff 7abaa938 fdb5f91d -- intelligence` 为空 |
| 本轮独立全量 / 前端 / 浏览器 E2E | **未重跑**；已存在阻断反例，未把执行方收据写成本轮全量/E2E 通过 |

## 重放与下一步

在固定候选根目录执行：

```bash
env PYTHONPATH=. /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -s docs/verification/re06-fdb5f91d/test_review_round8.py
```

当前预期为 2 failed；修复后应两条原样转绿，保持原 X1/X2、R7、Q2 和历史组合通过。
工程修补仍由执行分支承担，本审查分支只提交报告与反例。未改应用，未合并 main，未部署，未写生产用户数据。

双轴计数：Spec 1 个 P1；Standards 1 个有行为后果的 P1 启发式问题、0 个独立硬规范违规。
两轴共享“来源未知被当作无冲突”的根因，分别覆盖终态先到和读取失败，不将共用代码重复计成额外发现。
