# v4 K3 中断轮次：operator QC（不是模型终审）

对象 `6eb12c1b8a41071fd4af8bee343950fe0b85b221`；tree `e99dad14cb946a112d92537289854d914e558936`；冻结基线 `c615adbd2f861e23f2c8d03631833f98b3ae5aba`。

## 结论

**BLOCKED_INFRASTRUCTURE / NO_INDEPENDENT_SIGNOFF。** 两个现有会话均已退出，均无 `REPORT.md`、`verdict.json`、`completion.json`，不能称为“独立验收通过”。本轮未确立新的产品缺陷；也不能据此断言没有缺陷。

| 轴 | 开始 UTC | 结束 UTC | 耗时秒 | 准入 / 完整 assistant message | 工具 / shell | 退出 |
|---|---|---|---:|---:|---:|---:|
| Spec | 08:07:40.573158 | 08:40:39.231815 | 1978.656 | 50 / 49 | 64 / 39 | 1 |
| Quality | 08:07:40.573164 | 08:40:37.949713 | 1977.369 | 50 / 49 | 56 / 36 | 1 |

用户“不用给k3设置预算，随便用”已真正落实：总时长、请求数、token、强制收尾点均无限额；两轴均越过历史40请求和20分钟。50是观测数，不是新帽。`stop_reason=null`仅表示未被runner外层信号取消，不表示正常完成。逐命令120秒防卡死、凭证解析35秒仍存在。

## 退出原因与资源

- Spec `spec-k3/stderr.log`明确：`Error: ENOSPC: no space left on device, write`，发生于Pi JSON stdout写入；Node未处理的error事件导致退出1。不是候选源码失败，也不是模型预算耗尽。
- Quality空stderr，事件止于第50次请求流式输出，退出1比Spec早1.282秒。共同磁盘故障合理可疑，**但不足以确证Quality同因**；不得补写错误或把推测当事实。
- 08:44:54Z磁盘只剩3.5GiB、显示100%；08:50:46Z又为8.1GiB。是共享机器时点观测，本任务没有删除任何文件；不解释为我们修好了容量。
- 保留文件清单显示Spec 15,313,907字节、Quality 1,054,643,137字节（含正式测试留下的合成DuckDB）。本轮自身约1GiB，无法独自解释从启动前21GiB到低水位的变化；未完成全机空间变化归因。禁止因此清理其他agent或真实数据。
- `stop-state.json`记录两组旧PID/进程组没有残留。本轮未重启、增开模型会话、切路由或自动重试。

## 机械证据复核

`audit_mechanics.py`从原events恢复所有write版本、tool result原始行；语义判定不由它代做。`test_audit_mechanics.py`六个离线合成测试通过，Ruff通过；这是审计设施自测，不是候选测试。

两轴均满足：首尾revision/tree/状态/十二个监看源哈希不变，作者树不变，全部冻结输入不变，runner已记录输出SHA-256全部匹配。当前树再次复核一致。请求编号连续、模型均`mirasim-kimi/kimi-k3`。75份shell记录全部完成、原始combined日志哈希匹配、有效timeout在(0,120]；没有未配对工具记录。没有观察到compaction/retry事件或完整message_end模型错误，但最后一次请求未完成，不能由此声称没有底层错误。用量仅为完整消息事件相加，不是账单或全部未完成流用量。

七档旧归档成员/字节/哈希重新通过：30/30/86/26/450/115/82（README算、manifest不算）。旧v3三个树及当前v4三个树均净、保持原revision。证据在`stop-state.json`和两份`*-mechanics/mechanical-audit.json`。

## 部分测试能证明什么

### Quality正式测试：支持证据，不是独立终审

- `shell-records/0014`：四个receipt模块 **71P**，`PYTEST_RC=0`。
- `shell-records/0015`：board/backfill/collection-scope三个模块 **139P/1S**，`PYTEST_RC=0`。
- 合计 **210P/1S**，共享指定Python3.12.13，冻结候选源码。外层显式`FWP_TEST_RECEIPT=0`，没有独立测试收据；实际pytest退出由正确的`${PIPESTATUS[0]}`打印，不能只看shell最终0。
- 这些命令把pytest输出交给tail，wrapper保留的是tail之后全部combined字节，**不是pytest完整stdout**。该数不能与作者整仓12461P直接比较。

### Spec自写探针

最终矩阵报告45条readback参数、9条execution记录、8条ownership组合记录、12条board断言均ok。这些分母不相同，不能加成“74个独立端到端场景”。读取了探针、shell记录和关键收据，但未把每条作者式`ok`自动升为独立终审结论。

收据控制支持：失败测试gate1、无/错误身份/零执行拒绝、allow-dirty不豁免身份、嵌套内层不能抢外层、顺序/配置失败释放、path switch拒绝、并发rendezvous确有重叠。Spec O1使用不同测试文件；不是同target反例，不能拿它单独证明同target防护。Spec O8使用不同receipt根、同target同计数，强度低于Quality同根/不同-k计数的并发控制。

Board是在一组自建小仓库上的12条断言；正确区分clean/dirty/locked/missing/broken-gitdir、无main失败。固定SHA输出不等于“扫描期间main移动”的动态控制；parent-repo fallback未独立压测。

### Quality自写收据探针

最终结果17条记录，16个`PASS`字面true；`a11_signals.PASS=[]`，**不是通过**。四个顺序参数、两个继承PID参数不能冒称额外独立场景。

关键旧回归：`logs/a4_nested_inproc.log.txt`与仍在的`tmp/receipts-a4/gate-d8NiW0Ct/pytest.json`一致：相同文件内层`-k leaf`1P，外层2P，外层唯一收据2P、gate0。toy revision `04727b45b44b8aee2b617e0a7a56073556b87940`，不是6eb12本体收据。两轴toy的conftest/shell/helper与候选逐字节相同，但`test-environment.json`都缩为合成契约；不能叫“完整生产契约复现”。

A2在同receipt根/相同target/不同-k计数下，经rendezvous得到独立1P/2P两份收据。A5覆盖成功/配置失败×原owner缺失/空串。A9测试的是直接pytest写收据失败后的观测警告，不等于所有shell IO故障路径验完。

A11保留多次fixture失败：第一次错误杀到gate本身(-9)，第二次pkill模式以`-`开头被当选项，第三次匹配不到子进程，最后改按gate子PID定位后gate4；但SIGINT最后为-2、无收据，未达到其原本期望的可校验exit2收据。先前轮次有exit2/校验拒绝，不能跨轮拼成最后一轮全绿；新失败仍属未解决控制，不据此报产品缺陷。

两轴都没有完成独立编写的动态backfill probe，Quality没有独立board probe。阅读源码和运行现有105例backfill参数不替代这些缺项。真实完整副本302132发布/恢复从来不在本轮已完成范围内。

## 证据与隔离纪律偏差（原文不修饰）

- Spec多条driver使用`python ... | tail; echo $?`，所得0只属于tail。初次ownership显示2坏、初次board显示1坏、git空提交设施异常仍打印driver0。原shell记录保留；必须看子进程字段/原日志，不能接受这个driver0。
- Spec初次O5误把`-k`当receipt.target；O8一方没进入rendezvous；后续改fixture。Board初次分节切片错误。Quality初次immutable未把PATH传入env、早期patch字符串SyntaxError等均是设施问题。
- 两轴有覆盖结果/删掉旧fixture目录后复跑，违背“首个失败单独保留”的要求。wrapper事件/日志保留首次失败与write版本，但删除的收据、旧toy Git对象不能凭空恢复。当前inventory只证明仍存那版。
- Quality确实执行过宽泛`pkill -9 -f ...test_slow`，直到最后才改为owned child PID；这是共享机器进程边界偏差。未审计所有进程当时匹配情况，不能保证无旁伤，也没有证据把其他会话退出归因给它。本operator没有执行这些探针。
- Spec列过runtime父目录文件名、读取过已安装pytest源码；未观察到读另一轴报告正文。直接file-tool根门是实际约束，shell仍只有任务契约，不是OS沙箱。
- 首尾干净只排除了端点漂移，不证明中途没有改后还原；收据归属仍不抵抗恶意同用户写者或pytest同进程多线程。

## 后续边界

本轮保持原始模型输出，另写operator结论，不伪造REPORT/verdict。封档的是“中断+部分证据”，不是验收通过。不把已取消的预算重新加回来。

先确认磁盘容量及拟处理路径的归属；删除/迁移需另定范围。新的恢复审查需明确授权，沿用固定6eb12还是另冻结对象须显式决定；不得重跑原launch/run脚本覆盖本次。最新main集成/合并/部署/生产回填/真实树删除分别授权，三单与组合不可重复合。
