# K3 桥接入口复核与审查证据异议

## 背景
用户指出「k3有额度啊」。原 18788 的 `429 credit_exhausted_5h` 只证明该入口、账户和时刻受限，不能推断 K3 整体无额度。纠偏已写用户台账。18790/v1 -> 8080 既有桥接最小请求成功；本轮仅使用既有配置，不购买额度、不修改生产配置。

## 固定输入
- finance PR #847：518ddf8d0fce7acdbcadd34e94234e956b2f76ec；base a2c8d1f90773fdf3dcb7cf53f5d9733590924ae1。
- KB PR #157：7a47a6dc45ba6e8a3bebe47131bbd198b2090540；base d0caf31146a30e2cea05e6549652afb16fe70cb8。
- 冻结树和会话目录：`/Users/a77/.finance-runtime/reviews/briefing-k3-bridge-20260922/`。候选及作者树首尾均未变；报告的 SHA 不是随后仅增加文档的 tip。

## 发现顺序
1. finance 第一会话 40 请求/46 工具、exit75，未产报告：请求上限耗尽，无模型错误，不能归因额度。
2. 加剩余请求提醒、预留报告预算；KB 新会话 30 请求/38 工具、exit0，交付 REPORT/verdict，模型裁决 BLOCKED。
3. finance 第二会话 27 请求/31 工具、exit0，交付 REPORT/verdict，模型裁决 CHANGES_REQUIRED。第二会话提示澄清了 backdate 反例，不能冒称完全盲审。
4. 协调者核验报告发现证据与结论不符，最终接纳状态为 `REVIEW_EVIDENCE_DISPUTED_NO_APPROVAL`，不是 PASS，也不是协调者代签。

## 核验异议
- Finance P1/P2 引用 `label_older_than_source`，该探针标签时间早于来源录入日，实际正确抛 `Backdated computed_at`；reviewer 却把期望写成 PASS，与送审合同相反。同日更早时间假说未独立复现，canonical extractor 的 recorded_at 是日期。此证据不成立不代表不存在其他缺陷。
- Finance 第二会话正向探针因缺 `strength` 列而失败，随后引用作者旧自证，不能替代独立正向控制。P3 两项主要是已声明的价量比较/历史回放范围，不是新增回归。
- KB I1 引用旧 index 文案；当前 644/645 行已是材料转述/待核线索，不含所指确定性文字。不能照误报再改内容。
- KB 未找到的 raw/0915、0918 实际存在；协调者核对两份当前文件与 BASE、HEAD 完全相同。文件定位补齐不等于逐句归因审查已补齐。
- KB 提示词误混事件 `market_confirmed` 布尔与教学聚合 `briefing_market_confirmed=None` 两层；不手改投影。旧 log 的 MD5 字符串与当前 Markdown MD5 不同，原来针对 PDF 还是 Markdown 未确证，不伪称旧摘要验证通过，不改 raw/历史。
- KB execution 将有 BLOCKED 报告映为 INCOMPLETE；原收据不改，coordinator-qc.json 分开记 report_delivered 与 reviewer_verdict。

## 决策
| 选择 | 被否方案 | 原因 |
|---|---|---|
| 使用已有桥接并保留原 429 | 宣称 K3 整体无额度 | 单路由故障不可外推 |
| 串行新会话、预算前置提醒 | 无限重试至 PASS | 控制消耗，不把未完成洗成成功 |
| 保留原报告、另附异议 | 覆写模型结论或照单改代码 | 审查结论也须由复现支持 |
| 本轮停止调用，继续 WIP | 用完整 JSON 当批准 | 交付完整不等于语义审查可靠 |

## 收据与边界
`docs/verification/2026-09-22-briefing-k3-bridge/manifest.json` 绑定白名单文件 SHA256；coordinator-qc.json 记录两轴及异议。原事件流仅留树外，以路径和哈希追溯；不提交凭据、数据库、raw 或 PDF。
三会话共97请求，无模型错误，事件标识 mirasim-kimi-bridge/kimi-k3；只能验证路由和返回身份，未独立验证上游权重。finance 第一会话6+6测试、第二会话12测试，KB 5测试及抽取1338行一致；不是新全量工程收据。隔离依赖提示限制和首尾指纹，不是 OS sandbox；桥接内部既有重试策略未改，外层无自动重试/fallback。
封存扫描首轮误把扫描器自身字符串当私钥，修成多行私钥格式检查后完成，未跳过门禁。
本轮无业务代码变更、无 main 合入、无生产/8792 部署、无行情重查。09-18 既有消费 BLOCKED 未解除。

## 下一步
先修审查输入定位和字段/日期契约，再明确授权新的有界补审；原报告不能放行。最终 head/base、日志号、合流工程门禁及用户合入授权仍需重核。当前无后台审查任务、无自动重跑排队。
这轮 runner 为一次性收据脚本，已随证据保全；尚未审计成通用工具，不写入共享 harness/记忆索引，不冒称全局预算门禁已完善。
