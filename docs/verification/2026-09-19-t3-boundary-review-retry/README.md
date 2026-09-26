# ARL-0005 有界人工补审与新反例

**hold：无有效新裁决，且新本地比率量具4P/10F，未改业务。** 同一d46请求第二次CLI调用在1200秒上限内返回原始 `CHANGES_REQUIRED`，原验证器以 `check_manifest` 拒绝，`authority=none`。没有修补、重发或发布裁决。

## 身份和结论边界

- 业务 `d46c2c3b10221483c811426e99ad379314289871`；开窗文档tip `b78dbe3b`；新只读量具提交 `52f6dee7e197d005442bda1da58f9f94f813c8a8`。
- 请求SHA-256 `5fa3e7b7215bc83243e5f4a3e429cbca7770c791579cdce5d27d7a9cd13169d6`，request/claim不变，21份继承文件逐字节保留。
- 本窗1次CLI、1200秒/$6上限；CLI1189.272秒，exit0，非超时；显式operations靶向0005，不是常规队列选择或聚合gate批准。
- 请求SHA不变，但提示SHA由首次的 `a002a150…` 变为本次的 `a087adcb…`（嵌入超时回执与重试政策、600→1200秒）；适配器两版SHA见 `qc-retry-d46c2c3b-01/adapter-provenance.json`。「同一请求」不指提示字节相同。
- sonnet别名→claude-opus-5；CLI list报价$1.5541615，非结算。`num_turns=4`不等于provider请求数，后者未知；StructuredOutput协议调用不等于模型执行测试。
- 61个精确必需名称只覆盖26，漏35项（31测试路径＋4探针/变异名）、多37个替代名。总返回63项不证明完整。
- 机械预检1301P、46撤保护/首尾601P与原三探针6/4/16P通过，不代外部批准或自然回答。
- 新五输入×两模式10F、两控制4P；三句完整外审原文，两句明确为作者补全片段。补充公告4P4F另计。
- 新探针只走真实核验/公开出口，judge off/成功替身，0模型；没有业务修复、金融自然会话、取数、合main或部署。旧自然效果not_passed保持。

## 原件导航

| 路径 | 说明 |
|---|---|
| `boundary-retry-closeout-outcome.json` | 本窗口结果与身份总账 |
| `qc-retry-d46c2c3b-01/retry-policy.json` | 调用前的期限/预算/一次性政策 |
| `qc-retry-d46c2c3b-01/inherited-chain.json` | 旧请求/claim/有效CR/无效输出/超时的字节继承 |
| `qc-retry-d46c2c3b-01/runs/ARL-0005/preflight.json` | 38文件机械预检、三探针、46变异 |
| `qc-retry-d46c2c3b-01/runs/ARL-0005/review-prompt.txt` | 512055字节原提示 |
| `qc-retry-d46c2c3b-01/runs/ARL-0005/reviewer-stream.jsonl` | 过程事件、压缩边界与最终result |
| `qc-retry-d46c2c3b-01/runs/ARL-0005/reviewer-envelope.json` | 原最终信封/用量/报价，不补造 |
| `qc-retry-d46c2c3b-01/runs/ARL-0005/invalid-verdict.json` | 无效原始CHANGES_REQUIRED，不是有效裁决 |
| `qc-retry-d46c2c3b-01/verdict-validation.json` / `.exit` | valid=false/authority none/exit1 |
| `qc-retry-d46c2c3b-01/dispatch-result.json` | INVALID_VERDICT及运维调度方式 |
| `boundary-review-retry-01/post-return-diagnosis.json` | 精确清单差集、旧文档身份、原探针字段、补全公告反例 |
| `boundary-review-retry-01/residue-*.json` | d46 4P10F、746 2P12F、79 6P8F，不能仅看总数推引入提交 |
| `boundary-review-retry-01/probe-tip-*.json` | 精确52f四探针有限复验 |
| `boundary-review-retry-01/input-accounting.json` | 分段字节核算，不是token/根因诊断 |

原探针实际已有哈希与目标不变字段；只是模型看到的末尾视图没有。d46冻结inflight旧内容真实存在，但b78在补审前已更新；两份Git对象正文保留。两条意见不照单改代码。

## 保真规则

`manifest.json`记录**331原件、7,684,433字节**；本README/manifest另计。来源根 `~/.finance-runtime/convergence-20260919/retention-repair/`，新状态根 `qc-retry-d46c2c3b-01`，旧超时根未覆盖。

历史225+796+681+561＝2263件及其runtime来源逐字节验证未变。`.py/.log/.diff`追加`.txt`后缀但不改字节；冻结工作树、锁、缓存排除。可能存在原始尾随空白，不清洗。运维脚本只惰性归档，不安装为第二runner；不含明文凭据。

没有 `verdicts/ARL-0005.json`，也没有给0004补伪裁决。旧0001～0003有效CR继续保留；本次无效CR不计作第四份有效CR。归档后新增的diff-check、提交、记忆审计等日志另存runtime，不能称已包含在本manifest。

详见[本轮交接](../../handoffs/2026-09-19-t3-boundary-review-retry.md)。旧d46全量收据不移签52f或文档tip。
