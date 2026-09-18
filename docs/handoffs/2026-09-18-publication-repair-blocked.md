# Mapping 已整合、终态发布已修；新验收被 RAG 读取红灯阻塞

## 当前裁决

- Mapping 投影窄修复已在 `365627fd1350d87a9e9858cf0fb2fbc9d036daae`，不是“待整合邻枝”。
- 终态发布修复 `49fd8d726176a1e97eb43ed028bda93edc64f657`，配套前端静态产物 `7a9380bd0656916d46b7d2f1f136808649e618c2`。正式全量签的是 **7a9380bd**，不是后续文档/量具提交。
- 干净 7a9380bd：Python **11686 passed / 1 failed / 81 skipped / 2 xfailed**；前端115P、E2E34P/2S、ruff及注册表四项绿。**整体工程未通过**，收据校验exit0仅证环境/版本适用，不把失败变绿。
- 新的 Mapping/发布修复版 GLM 验收：**首发0、重发0、续问0**。没有 prepare/启动/发题；只有未执行的控制器，没有新协议、行情副本或用户写根。
- 旧 `5f3b5b59` 与 `35ee8a5c` 两个真实样本仍 not_passed，不 resume、不翻案。自然纠参、拒收候选保留和金融质量仍未验。
- 8792未切、未push/合main/部署；关闭核对仍为 `bf662e9310ff` 身份，启动器hash同旧GLM关闭时；8849/8851/8852均无监听，无所属锁。

[机器收据与原件索引](../verification/2026-09-18-publication-repair/README.md)。

## 背景与发现顺序

### 1. 用户授权“执行”：纳入 Mapping 小片

旧 GLM 会话 `run_20260918_213933_397262` 中，`history_query(find_analogues)` 缺 `end`，真parser正确拒绝；进度账却对冻结的 Mapping 调 `json.dumps` 崩溃。复用 `a969d30a` 的小片而非盲合邻枝：JSON边界将 Mapping 投影为新dict，未知对象仍拒绝，原冻结参数不改。加入嵌套参数、错误/超时状态、真Episode拒绝回传、原形状历史缺参回归。

开发阶段旧实现7处失败、修复定向246P；不是新提交全量收据。干净365627fd全量11674P/81S/2X，但E2E **33P/1F/2S**。旧原件重放反馈正确、44证据/参数/来源不变；保稿重放也过，错误使用`--episode`的首条exit2保留，正确位置参数另存结果。

### 2. E2E 揭示 completed 早于 report 发布

桌面测试 `real chat persists three fresh turns, skills, SSE, and regeneration` 第二轮缺“结构化对话报告”。run=`run_20260918_223223_071216`；网络轨迹：

| UTC | run状态 | 已登记产物 |
|---|---|---|
| 14:32:23.167 | running | 空 |
| 14:32:25.163 | completed | daily-agent-skill-result.json |
| 14:32:25.568 | completed | 再有answer.md/answer_spec.json，仍无report |

最终磁盘有report，但前端已经按terminal停止刷新。首次234文件浏览器现场完整保留；不是加长等待或重跑刷绿。Mapping提交未改App/编排器/该E2E路径。

### 3. 用户“继续”：修发布边界，不移动终态竞争

`_claim_terminal_run` 仲裁完成、取消、超时的归属，不能为了读侧简便移到产物之后。增加公开Run的 `publication={status,message_id}`：

- 对本用户会话中该run的assistant，只有消息终态与run相同，且对应 `message.complete` / `message.error` 的run/conversation/message/role/status全部匹配，才published。
- 看到发布事件后**重读run**，避免把事件之前读到的半成品产物列表标为published。
- 无assistant消息的旧 `/api/runs`（可有任意session标签）为not_applicable，不能冒充会话发布。
- SSE不再只等两次poll；在既有总时限内等发布，补排两读间新事件，超时不伪造terminal run。
- UI的SSE、断线轮询、重新打开会话都消费同一发布证明；成功加载匹配终稿及run bundle才关闭连接/轮询。缺标记、错ID、加载失败继续重试。
- probe新服务要求相同发布/会话/消息身份；旧服务缺字段只保留旧message_id合同，不证明产物完整。失败/取消不要求report。

| 方案 | 评价 | 决定 |
|---|---|---|
| 把claim移到最后 | 可能改变取消/超时竞争，掩盖所有权与发布的差别 | 否 |
| 固定sleep或放宽E2E | 慢机器仍可撞窗口，不能证明资料完整 | 否 |
| 给消费者明确发布证明 | 复用已有最终事件，不另造写入链；保持终态仲裁 | 采用 |
| report文件存在即完成 | 单个文件不代表列表/消息完整，失败/取消可没有报告 | 否 |
| 跨进程自动补发布 | 需独立崩溃恢复/身份合同，本次不猜稿 | 未做 |

测试先红后绿；真编排器测试用Event卡住report登记，证明“消息已非空＋run completed”仍pending，释放后SSE交付report；另有错误身份、旧入口、超时测试。开发后端235P、随后完整API/probe组合145P，前端115P，这些仍是开发读数。

### 4. 编译产物必须与源码一起冻结

49fd8d72首轮前端/E2E已绿，但`pnpm build`改了受版本控制的`intelligence/api/static`。主动中止尚未结束的Python，exit2，1518P/3S/1X仅已执行部分；收据dirty、校验exit1，全部保留。不把它标全绿，也不移绑新提交。

提交产物7a9380bd后重新全量：构建不再弄脏树。四组隔离撤保护（terminal冒充published、不重读列表、跳消息ID、SSE提前结束）各exit1，恢复后选择测试exit0且干净。不是独立QC。

### 5. 全量新红灯：RAG worker 缓冲响应误超时

干净7a9380bd唯一失败：
`intelligence/tests/test_rag_worker.py::test_warm_worker_survives_first_timeout_and_drains_the_late_response`。
预热成功、首次放弃慢请求且保活成功，下一请求2秒窗却`TimeoutError`并杀进程。`rag_worker.py`、其测试和`rag_query_worker.py`与365627fd零差异；不能因此称它无害或只怪负载。

量具提交 `18c7c7fcaeba8e1a7c6c1a71696bcc729deffb2f`：
`scripts/review_probes/replay_rag_buffered_late_response.py` 使用真 `_query_locked`、合成process和真实OS管道，一次写入迟到旧响应与当前响应。`TextIOWrapper/BufferedReader.readline`预读两行；丢旧后再`select`只看内核空管道，当前响应留在Python缓冲，导致超时。诊断读取器只逐字节取一行，同样输入正常返回。

干净18c7量具exit0：旧响应drained=1、当前响应ID匹配但滞留、timeouts_killed=1；控制组正常、无kill。它证明**未改消费者中可确定复现的缺陷**；原全量现场未探测缓冲内容，不能声称逐字节证实那一次的所有调度。首个未提交版诊断保留；新量具记revision/dirty/源码hash。量具没有起子进程/调用KB/模型/网络/DB，逐字节方案不是生产修复。正式全量失败不重跑。

## 原件、封存与边界

根都在 `~/.finance-runtime/reviews/`：
- `research-progress-repair-20260918/`：365627fd检查与首次E2E红，296文件。
- `research-publication-repair-20260918/`：开发红绿、49fd中止及dirty收据，338文件。
- `research-publication-live-20260918/`：7a9380bd全量、四反证、RAG诊断与关闭收据，341文件。目录名live不代表已发题。

三包扫描初次分别10/11/24个词形命中，均逐文件hash＋marker＋匹配hash核销为已检查代码引用；未决0，**不是零命中或独立安全认证**。扫描UTF-8及zip文本成员；图片/SQLite/DB等仅hash，源码/行情副本按revision或manifest，后续closeout不在分母。旧214/44/90/6/82包及两个新前序包逐项hash一致。

汇总脚本第一次把旧44文件索引的list误当dict，exit1原日志保留；解析两种格式后另写纠正日志exit0，不修改索引或原件。

## 下一步与禁止项

1. 单独修RAG按行消息读取：考虑无缓冲二进制非阻塞读取＋显式换行缓冲，或专门reader队列。必须测合并两行、半行/UTF-8切片、旧响应丢弃、ID错误、EOF、绝对deadline与连续超时保活/自愈。不能只加timeout，也不要把诊断逐字节reader直接装生产。
2. 新干净revision（含静态产物）四叶全过才冻结一次GLM协议；现有控制器只是准备稿，新revision需更新并核对所有前置。保持一次首发、零重发，不增加“试通模型”调用。
3. 本次不跨进程恢复候选，不补失败用量/durable终态，不合邻枝财务/数据改动，不切8792。
4. 学到的可迁移点：错误/审计投影不可把可恢复拒绝升级成整轮崩溃；终态归属不等于公开资料完整；OS可读与用户态缓冲可读是两种状态。回归进仓，实例编排/扫描脚本留私有证据根，避免造另一套产品入口。
