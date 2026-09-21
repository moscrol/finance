# 固定归属候选 v4：K3 无预算复审中断证据

**状态：BLOCKED_INFRASTRUCTURE / NO_INDEPENDENT_SIGNOFF。不是通过报告。**

- 被审对象：`6eb12c1b8a41071fd4af8bee343950fe0b85b221`，tree `e99dad14cb946a112d92537289854d914e558936`。
- 冻结基线：`c615adbd2f861e23f2c8d03631833f98b3ae5aba`；#812/#813/#814组合，包含a092调用级收据修复。
- 原件根：`/Users/a77/.finance-runtime/reviews/ownership-k3-v4-20260921/`。
- 本轮只读候选；没有合并/部署/生产回填/删除真实树，也没有重启异常退出的审查。

## 本轮发生了什么

用户先“启动”，后明确“不用给k3设置预算，随便用”。新授权、两轴prompt、实际runner均撤掉总时长/请求/token/强制报告截止点；旧v3限额历史不改。仅既有Plus订阅`mirasim-kimi/kimi-k3`，不购买、不换路由、不重试、不增开代理。离线设施19项通过，另有installed Pi stub无真实模型请求；原始两次设施错误保留。逐命令120秒、resolver35秒防卡死并非总预算。

两轴于2026-09-21 08:07:40Z启动，Spec于08:40:39.231815Z退出1，Quality于08:40:37.949713Z退出1。**各50准入/49完整assistant消息，没有REPORT/verdict/completion。**

Spec stderr明确`ENOSPC: no space left on device, write`；Quality空stderr且流式输出中断，同因可疑但未证实。50是实测数而非新限额。磁盘时点观测从启动前21GiB到08:44的3.5GiB，随后共享机器可用量回升；本任务没有做清理，未归因全机空间变化。

## 证据入口

- `operator-qc/review-qc.md`：operator语义QC，独立于原模型文本，列部分结论、设施失败、隔离偏差和缺项。
- `operator-qc/stop-state.json`：身份/进程/保留文件规模/历史归档复核。
- `operator-qc/{spec,quality}-mechanics/`：原始tool-result行、write版本与机械审计。
- `{spec,quality}-k3/execution.json`、`events.jsonl`分片、`stderr.log.txt`、`shell-records/`：实际退出/原始日志/有效timeout。
- `{spec,quality}-k3/probes/`、`evidence/`、`logs/`及精选toy文本/收据：只代表仍保留的fixture版本，不能恢复被审查者覆盖或删除的早期版本。
- `audit-tests.log.txt`：operator审计设施六个离线测试通过，非候选验收。

两轴首尾及复核时源码净同revision/tree/十二源哈希，冻结输入和记录输出哈希一致。75份shell记录完整且哈希匹配。七档旧证据成员/哈希30/30/86/26/450/115/82不变，旧v3三个树保持原样。

## 部分支持证据与不能推出的结论

Quality现有定向测试71P + 139P/1S = **210P/1S**，真实`PYTEST_RC=0`；receipt显式关闭且输出被tail截取，不能叫完整门禁收据。独立same-target嵌套pytest小仓库探针确实保持外层2P、gate0；这是toy revision证据，不是新的6eb12全量门禁。

Spec最终45条readback参数、9条execution、8条ownership、12条board断言；Quality17条结果中16个PASS字面true、signal一条为`[]`而非通过。分母不同不相加为端到端场景。两轴都未完成独立动态backfill probe，Quality未做独立board probe；已有测试不补这些缺项。无完整独立终审，无后来main签字。

原错误与偏差保留：错误pipeline退出读数、fixture覆盖/删除、Spec board切片错误、Quality宽泛pkill后才改为owned child PID、未解决SIGINT控制等。shell没有OS沙箱；无证据保证无旁伤，也不凭空指控已发生旁伤。最终QC没有把任何这些设施错误改写成候选产品缺陷。

## 归档合同

只复制精选文本、日志、收据和设施源码，不提交DB/Parquet/Git对象/缓存/依赖。大JSONL仅按LF原字节切成≤4MiB片，按manifest顺序拼接应等于原件SHA-256；不parse/reserialize模型原文。文件增加`.txt`后缀只为仓库门禁，不改内容。README是归档说明，纳入成员；manifest不计自身。保留文件inventory记录约1GiB本地测试夹具身份，不等于把其二进制入Git。

异常退出后不自动重开。先确认容量与归属，再另定恢复审查授权/对象；不得覆盖本轮或重新加旧预算。latest-main合流/合并/部署/生产回填/真实树删除分别确认，三单与组合不可重复合。真实完整副本302132父子发布恢复仍未演练，Arena仍另线。
