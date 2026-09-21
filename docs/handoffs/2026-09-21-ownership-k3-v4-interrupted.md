# 归属 v4 无预算 K3：异常中断与证据保全

## 背景

#812看板/#813回填/#814收据的作者工程绿对象仍是`6eb12c1b8a41071fd4af8bee343950fe0b85b221`，tree `e99dad14cb946a112d92537289854d914e558936`，基线`c615adbd2f861e23f2c8d03631833f98b3ae5aba`。启动与用户撤预算授权见`2026-09-21-ownership-k3-v4-launch.md`，工程证据见`2026-09-21-ownership-integration-v4.md`。旧快照不改写。

## 按发现顺序

1. 用户说“执行”后续查原来两个会话，没有重启。08:25:45Z Spec32/Quality33准入，均活着并开始自写收据小仓库探针。
2. 准备独立operator审计器`audit_mechanics.py`：只接收已结束execution，恢复原tool-result行及write版本，核对源身份/冻结输入/输出哈希/实际shell记录。它不代写模型结论。后续六项离线自测与Ruff通过，保留自测夹具和日志。
3. 08:44:54Z再查，两路都已退出1，各50准入/49完整assistant消息，均无REPORT/verdict/completion。Spec实际结束08:40:39.231815Z（1978.656秒）；Quality08:40:37.949713Z（1977.369秒）。第50次请求均停在流式输出中，没有完整message_end。
4. Spec stderr明确`ENOSPC: no space left on device, write`，Pi JSON stdout写入失败；Quality stderr为空，提前1.282秒退出，原因未确证。**不是触请求数或时长帽**：执行器仍无限额，没有外层watchdog/自动重试。`stop_reason=null`不等于成功。
5. 磁盘08:44仅余3.5GiB、显示100%，08:50恢复8.1GiB，08:59为9.5GiB。本任务没有删除文件，不能将共享机器的空间回升记成我们修复。已保留文件清单约Spec15.3MB/Quality1.055GB（后者含正式测试合成DuckDB）；不足以解释全机从启动前21GiB的波动，未完成全机归因。
6. 执行机械审计，两轴首尾及复核时净同revision/tree/十二源哈希，冻结输入、runner输出哈希一致；75份shell记录完整、日志哈希和有效timeout全部匹配。无未配对工具记录。两组原PID/进程组无残留。
7. 阅读自写探针/结果/原shell日志，QC单列不足和设施误差。七档旧证据30/30/86/26/450/115/82成员/字节/哈希复核通过，旧v3三个树和v4三个树保持净同原SHA。
8. 新证据封于`docs/verification/2026-09-21-ownership-k3-v4/`：**819文件、33,027,503字节**（README算、manifest不算），两路events各按LF原字节分四片，拼接与原哈希一致。成员、字节、哈希及runtime原件比对通过。DB/Git对象/缓存不入Git，原件未删。

## 结论与部分读数

**BLOCKED_INFRASTRUCTURE / NO_INDEPENDENT_SIGNOFF。** 这是operator结论；没有伪造或补写模型终审。没有确立新的候选产品缺陷，不等于已证明没有缺陷。

Quality现有定向测试71P+139P/1S=210P/1S，真实`PYTEST_RC=0`，外层receipt关闭，tail后日志不是pytest完整stdout。same-target内层`-k leaf`1P、外层2P的小仓库探针保住外层唯一收据；toy SHA不是候选测试收据，环境契约也已缩为合成版。

Spec最终矩阵45条readback参数/9条execution/8条ownership/12条board断言；Quality17条记录16个PASS字面true、signal一条为`[]`。分母不同不得加成独立场景。两轴都未完成独立动态backfill probe，Quality未做独立board probe，不能由现有测试补签。

原始偏差完整列于归档`operator-qc/review-qc.md`：Spec pipeline读错退出码、先前fixture失败/覆盖/删除、board分节切片误判；Quality曾宽泛pkill后才改owned child PID，SIGINT控制仍不一致。原事件和shell记录保留，但删掉的旧fixture/收据不能假装恢复；没有全机旁伤审计，不能保证无旁伤。shell没有OS沙箱。

## 决策对比

| 方案 | 评价 | 决定 |
|---|---|---|
| 50次后退出解释成新的预算帽 | 与实际授权/代码/错误日志矛盾 | 否 |
| Quality与Spec同时失败就判同因 | 空stderr不足以确证 | 否；明确未知 |
| 部分探针绿就补PASS报告 | 缺回填覆盖、缺最终模型结论 | 否 |
| 磁盘回升后自动开新会话 | 违反一次会话/无自动重试授权，且根因未清 | 否 |
| 删除别的worktree/测试目录腾空间 | 所有权与保留价值未核实 | 否 |
| 保全中断证据、单列operator QC、待资源/恢复授权 | 可追溯且不扩权 | 选 |

## 下一步与禁止事项

先确认容量和拟处理路径归属，再决定迁移/删除哪些可再生内容；处理范围与新的恢复审查须用户明确确认。不得重跑原`launch.py`/`run_k3.py`或覆盖这轮。无预算偏好仍有效，恢复时不能重新加40请求/20分钟帽。若恢复，保留每个失败版本，信号只发给本次创建的PID，覆盖驱动而非次数驱动完成。

本轮没有合main、部署、生产回填、删除真实树或接管Arena。最新main集成与完整副本302132发布恢复仍另验；三单与组合不能重复合入。文档尖不继承a092/6eb12工程收据。

原件`~/.finance-runtime/reviews/ownership-k3-v4-20260921/`；发布/校验记录`~/.finance-runtime/reviews/ownership-k3-v4-closeout-20260921/`。工具盘点：审计与封档脚本保存在本轮归档中，是一次性证据设施而非常驻服务；未擅改共享harness。无OS沙箱下进程/磁盘隔离的工程修复另定范围，本轮只如实记录，不能称已补硬门禁。
