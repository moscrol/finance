# 8792 边界组合：四次隔离真实会话，整体验收未通过

## 结论与身份

2026-09-18，用户授权“执行/继续”后，对精确代码 `3faf64fbadcfe45fdd0b306acd223d9e78c56525` 完成预注册的四次真实 Workbench 会话提交：**3 次 completed 有正式正文、1 次 failed；不是 3 项完整任务合格，更不是上线通过**。F1 登记退出和 F2 日期引用目标边界有证据；F3 路由正确但研究运行失败。完整任务质量仍有缺口，`promotion_eligible=false`。

- 候选分支：`fix/8792-boundary-integration`，原文档头 `e857d594`；本轮没有修改业务代码。
- 被验代码独立 detached 树：`~/.finance-runtime/reviews/8792-boundary-live-20260918/code/`，运行前后 clean，加载身份与代码匹配。
- 本轮原件根下文简称 **R**：`~/.finance-runtime/reviews/8792-boundary-live-20260918/`。
- 临时端口 **8828 已关闭**，自己持有的 live 锁已移除；数据、用户、工件和脚本均保留。
- 生产 **8792 仍 `bf662e9310ff751a4c31763815ee78fb7d6d5122`**，healthy、dirty=false、code_matches_repo=true；前后加载指纹、用户根和 agent_runtime 身份一致。
- 本轮未 push、开 PR、合 main、部署或切换判官模式。原工程四叶收据仍只属于 `3faf64fb`，没有重发新收据。

## 为什么这样验

| 选择 | 否决的替代做法 | 原因 |
|---|---|---|
| 单独固定代码树、临时端口和新用户 | 在 8792 直接试或只换端口 | 不能污染真人台账，不能把旧部署当修复版 |
| 沿用实际生产模型/判官配置 | 按旧记忆切模型，或关闭判官便于通过 | 验的是候选边界，不混入另一组变量 |
| 每题一次提交；失败留原件 | 换题、重采样直到绿 | 失败是结果，不能通过重试筛掉 |
| Workbench 会话 HTTP 合同 | CLI ask 或直接调用 `/api/runs` 代签 | 必须压到建会话、编排、最终 assistant 消息与实际写口 |
| live 正反登记 + 同答案离线对照 | 只看拒绝题没文件 | 全部禁写、没触发写口也会“没文件” |
| 真证据上的三个离线谓词对照 | 额外诱导模型生成坏事实 | 有界验证门仍有效，不把离线变异冒充真实模型效果 |
| 先停止候选验收、归档阻塞 | 当场修改固定代码后覆盖本轮结果 | 新代码需新 revision 和新验收，旧失败不可改写 |

## 事前冻结与运行边界

`R/protocol.json` 在首题前生成，保存原题全文/hash、四个独立非豁免用户、执行顺序和判据；`register_protocol.py`、`run_cases.py`、probe hash 均留档。最多四个首条消息，零澄清回复、零重复提交。自动 skill 选择、neutral 视角；服务预算 900 秒、客户端等待 960 秒。

入口为 `scripts/workbench_probe.py`：`POST /api/conversations` → `POST /api/conversations/{id}/messages` → 轮询返回的准确 `run_id`，只验返回的 `assistant_message_id`。不是本轮浏览器点击验收，也不是隔离外部评委/盲评。原 probe 输出的 `~/.local/share/...` 工件路径是通用提示；本轮实际用户根是 **R/users/**，不能跟错文件。

运行壳为 `continuous_glm`；生产 health 与成功 run 的结构化 writer 元数据为 **glm-5.3-flash / zhipu**。终稿判官私有回执 `judge_mode=llm`、`correlated_judge=true`；evidence judge 保持 auto。通用 `LLM_MODEL=glm-5.3` 与 writer 配置不是同字段；本轮没有逐调用判官身份，不据环境替它补认证结论。凭证只由生产启动器经内存传入子进程环境，没有配置持久 BYOK 或写入密钥。

### 隔离不是只改端口

代码、用户、FINANCE_WS/DB/exports、部署账本、L3 cache、vault 均有 R 下独立根；禁用持久 Keychain。前两题结束后发现条件写口 `FINANCE_REJUDGE_PENDING_INDEX` 尚可能回落共享默认路径，暂停 coordinator，确认两 run 终态，停止自己的旧 PID 54084，再以该索引隔离根重启 PID 84905；随后继续后两题，**没有重复前两题**，业务代码和模型/判官模式未改。

共享 pending 索引未发现本轮 run 行，关停时 size/mtime 与审计前一致；R 下也无 pending 行。生产/共享记忆用户根下未出现四个测试身份。不声称对全系统做了禁止写入沙箱，也没有逐字节审计所有真人文件或停止其他 agent。

### 固定了什么数据

市场 DuckDB 为独立 inode 的 APFS clone，源只读连接锁下完成 hash 核对；拒 WAL，快照普通文件只读，不用硬链接。DB、market exports 和 market_snapshot 同根且前后 hash 不变：

`2d192a78205d94a1f7bcef9d90f82ed2d9ecee8b1e7a9d1e30dfe23da0eb6b89`

`fact_market_daily` 最新 09-17；**不是所有表都到 09-17，更不是值级全满**：竞价/龙虎榜等仍 09-02 或 09-08；`fact_mainline_sector_daily` 当日 amount 为 0/39 非空，`fact_stock_daily` amount 为 5552/5553 非空。逐表读数见 `market-snapshot.json`，本轮未补库。

财务 `financial_data/F10`、知识库、检索索引、网页与 L3 公告仍为共享/在线输入，**不属于冻结市场快照**；保存实际取回证据而非宣称可原样重跑所有外部输入。

## 四次结果（保留失败在分母内）

| 题 | run_id | 交付 / 报告 | 服务持久时间* | 实际判据 |
|---|---|---|---:|---|
| F1 拒登记仍研究 | `run_20260918_085354_182061` | completed / completed | 142s | track_intent=true，有研究与清单；0 checkpoint、0 judgment。登记退出成立；清单触发条件被删后残缺，完整任务不合格 |
| F3 格式化财务请求 | `run_20260918_085619_685299` | failed / blocked | 71s | 主体中际旭创、financial_analysis、原请求保持；`mappingproxy` JSON TypeError，中断交付 |
| F2 日期 + 引用计划 | `run_20260918_085854_333533` | completed / partial | 174s | 2026-10-21 复查计划和 E45/E43 保留；E43 发布日 2026-08-22，已知且绑定；目标边界通过，不代签完整财务质量 |
| 明确登记阳性 | `run_20260918_090149_835284` | completed / partial | 203s | 真实写入 1 条 track_next_watch，session_id 对应该 run，due=2026-10-21 |

\* 服务 `created_at→finished_at` 的持久时间，非浏览器可见延迟；客户端分别 145.458 / 154.602 / 175.484 / 205.637 秒。F3 的客户端时长含 coordinator 暂停等开销，不拿 155 秒当模型耗时；n=1 不证明快慢或稳定性。

每题 conversation/message ID、公开消息、API projections、私有 continuous-episode/context、原 trace、probe exit、用户 manifest 都在 `R/cases/<id>/`。失败题的非空正文仅“本轮连续研究未取得可公开答案”，`answer_nonempty=true` **不构成成功**。

### F1：安全拦截成立，答案闭环不完整

判官前置数字门删除了无绑定依据的 `0.3` / `0.8` 净现比阈值。删除是正确保护，但公开清单剩指标和复查日，缺少用户要求的触发条件。不能把“坏句已删”当作“任务已经完成”。

同一份公开答案进入实际 `ingest_next_watch` 的临时文件对照：拒登记 0 条、显式允许 2 条，证明原答案能触发写口。但第二条误收了清单后面的“缺口”段，due 变成历史日期 2026-09-11，暴露 **清单解析结束边界** 缺陷。这是离线临时写，不是额外 live checkpoint；真正阳性题仅写 1 条。

### F3：路由修复并未保证研究能交付

路由轨迹与离线原题投影均保持 `financial_analysis/中际旭创`、material_count=0、question 等于完整输入。真实运行仍失败：

`TypeError: Object of type mappingproxy is not JSON serializable`

`mappingproxy` 是只读映射，JSON 编码器不能直接序列化。末条请求是 web_fetch，前面已有计算/工具活动；**错误原件没有 stack**，目前不能把最后一个工具名直接认作根因，也不能认定与旧 manual 样本故障同源。后续应从留存 trace 做不联网最小复现，抓住跨边界对象类型；本轮没有修代码或重新发这题。

### F2：实际计划保留，坏句门另做明确标注的离线对照

公开终稿中复查时间 2026-10-21、E45/E43、披露日 2026-08-22 与报告期 01-01～06-30 分列。E43 有 source_date；E45 source_date 为空，不因 URL 含日期替它补成已知值。两引用都真实存在且绑定。

实际模型没有同时产出全部坏事实形状，所以另对取回的 E43 真证据执行只读谓词：两种合法计划、正确来源日放行；错来源日 08-21、虚构业务阈值 987654321、未知协议引用 E999 各被对应门抓住。**6 个离线对照通过、网络 connect 尝试 0**；不是再次调用模型，也不是完整 verifier/最终公开答案变异重放，后者承重仍看原组合工程测试。

## 不可用本轮签收的项目

1. **金融语义质量**：F1/阳性把“最近两期”选成 2025 年报+2026 中报，但取回证据也有中间的 2026 一季报；期间选择未解释。现金流本地缺值、网页转录与研究笔记不能自动替代一手核验。
2. **输入截止期**：四个 research_context 的 information_cutoff 均为 runtime_default 2026-09-18，用户分别问截至 09-16/17。路由 timeframe 有原日期，但上下文未同值；本轮没有证明发生了截止后证据泄漏，也没有据此签收时点合同。
3. **使用量/费用**：三份成功 writer 收据分别记录 303716/3755、266951/3725、387542/4119 输入/输出 tokens；5 次判官调用没有 tokens。失败题 report.llm.used=false/tool_calls=0，但 provider_attempts=9、trace 有 10 次请求/9 次结果；这是计量缺口，不是零成本。`run-inspection.json` 的本地 `glm-5.3*` 价目参考不是 flash coding 套餐账单，缺判官/缓存/失败计量，**不给整轮费用数字**。
4. **状态语义**：run completed、report partial、structural partial、semantic repaired 可以并存；不能只看最外层 completed。F2 的计算产物 ID 曾被模型判官降级又经 guided rejudge 恢复，不把中间拒收当最终删除。
5. **其他工程线**：#770 跨轮材料/local_only、RE06/#53 真人结果、#56 关闭判官后的连续观察都未签收；旧 sector 样本 81%/46.875%、区间 invalid_query 仍非本轮修复范围。

## 失败原件与验收仪器修正史

按发现顺序保留，不能只留最后 exit 0：

- 前端 static 复制曾嵌成 static/static，首次 launcher 被脏树守卫拒绝；修正辅助代码又 AssertionError，而 shell 继续启动。最终逐资产 hash/UI readiness 通过；错误副本存 `frontend-miscopy/`，时间线存 `launch-attempt-history.json`。
- 条件 rejudge 写口遗漏先审计再重启，见 `restart-for-sink-isolation.json`；不把最初两题说成从启动起全写口完美隔离。
- 首次 offline control 误用 **E99999**；协议仅认 E1..E999，因此命中的是业务数字门而非未知引用门，6 项中 1 项断言红。保留初始脚本/JSON/log/exit；仅修夹具为 E999 后 6/6，不改业务规则、不改 live 题。
- 扩展 SecretScanner 从公开 API/私有 episode（零命中）扩大到所有保存文本后，首次 finalizer 被 Python dotted import / `SecretScanner()` 构造表达式的词形误报拦下。保留初次 exit1；逐条核对原文/hash，不用全文件豁免。最终 184 份文本、122395 个字符串、5 条来源/规则命中均为代码形状误报，未解决命中 0；见 `preserved-secret-scan-final.json`。这不是全系统安全证明。
- `finalize-final.exit=0` 表示原件核验和归档完成，**acceptance-summary.overall_acceptance 仍为 not_passed**。

## 收尾与后续路径

09:10:15（+08）已 SIGTERM 自己的 PID 84905，核端口释放后移除自己的锁；没有 force kill、删除测试树或清理历史资源。市场快照、exports/snapshot hashes 仍一致，生产身份不变；见 `closure.json`。

优先处理：**F3 序列化中断 → 清单结束边界 → 删坏条件后必需输出的完整性**。同时补失败用量和信息截止期的实际合同核对；每项以已有失败原件复现，先写承重反例，不用 live 重采样代替定位。涉及业务改动要新 revision，再跑适用工程检查；新增模型预算、远端交付、合 main、切流和判官模式分别确认。

工具沉淀：继续使用仓内 `workbench_probe.py`、SecretScanner、usage 投影和原组合回归；本轮特定 revision/路径的一次性 launcher、收据检查、离线对照均存 R 并有 hash，不在 /tmp 失散。它们不是通用安全启动框架，原运行脚本默认拒复用现有工件，**不要原样重跑**；本轮也未动脏 harness 仓或新造另一套产品入口。

索引：[本轮验证](../verification/2026-09-18-8792-boundary-live/README.md)；[原工程验收](../verification/2026-09-17-8792-boundary-integration/README.md)。
