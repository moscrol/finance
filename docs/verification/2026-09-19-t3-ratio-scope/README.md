# T3 值槽返修证据 · 2026-09-19

**状态：hold。** 业务 `746b716ff95d40898697628e197fd266a9473bf6` 的既有完整工程套件通过，
原占位四例4P，但随后新边界探针4P/12F。ARL-0004模型写PASS却有5项必需PARTIAL，
被既有门禁拒绝为`INVALID_VERDICT / failed_check_for_pass`，authority none。
不是有效外审PASS，也不是第四份有效CHANGES_REQUIRED；旧三份CR未被有效裁决覆盖。

本目录 **681件原件 / 9,620,137字节**，另有本README与manifest；逐件与runtime来源字节比对。
原日志、提示、diff的尾空白/末尾空行不清洗；新说明另做diff检查。`.py/.log/.diff`仅追加`.txt`后缀，
不改变内容。排除冻结工作树、锁和缓存，不安装第二永久runner。不含明文凭据，设置仅本机helper路径。

## 导航

| 目录/文件 | 证明什么，不证明什么 |
|---|---|
| `hedge-repair-01/original-before.json` | 留证58原占位0P4F，未改输入 |
| `hedge-repair-01/tests-before.log.txt` | 新回归首红51F/186P；另有并列标记2F、披露2F，首红不覆盖 |
| `candidate-746b716f/result.json` | 完整工程套件通过，仅该精确revision |
| `candidate-746b716f/full-python-receipt.json` | 11988P/0F/0E/87S，日志另记2xfailed；已验证身份/完整target/干净树/base drift0 |
| `candidate-746b716f/original-*-probe.log.txt` | 原保真6P、原占位4P，替身/0模型，非自然回答 |
| `candidate-746b716f/mutations/results.json` | 36组真断言检出并逐项还原，首尾416P，不替新红针签字 |
| `qc-repair-746b716f/` | 首调本地Prompt too long；0 API ms/token/报价，无裁决，221件封存清单 |
| `qc-retry-746b716f-01/requests/ARL-0004.json`、`claims/` | 同请求完整字节/hash，依赖并supersede前三轮，累计d38..746，未缩范围 |
| `qc-retry-746b716f-01/runs/ARL-0004/invalid-verdict.json` | 原模型PASS+5PARTIAL，自相矛盾，未发布到verdicts/ |
| `qc-retry-746b716f-01/verdict-validation.json` | direct validation valid=false / authority=none / failed_check_for_pass |
| `qc-retry-746b716f-01/scope-boundaries-746b716f.json` | 新探针4P12F；三类新误报+三类旧漏检均原样×两模式失败 |
| `qc-retry-746b716f-01/scope-boundaries-79dba348.json` | 同题旧79对照8P8F，区分新回归与既有问题，不算总体质量统计 |
| `qc-retry-746b716f-01/gate-after-timeout.json` | 后置gate120秒无输出超时，无决策，不能借空文件签通过 |
| `hedge-closeout-outcome.json` | 本轮总账：hold，未合/未部署，自然金融会话0/取数0 |

两次隔离artifact-tests均1116P；worker机械执行，不说成模型自己用工具跑测试。
补试580.771秒，CLI报价$2.1568412500000003（list估计，非结算），信封报告claude-opus-5；
实际provider请求次数未知。本轮共两次CLI dispatch，其中首次本地合成错误；不是“本轮零模型”。
无tools/MCP/plugins/hooks/持久session，无第三次重试或后台worker。

历史1021件原档案以及前三份有效CR逐字节不变。完整工程收据只认证746业务提交，
不移签到后续留证tip，也不推翻新红反例和旧自然金融not_passed。

决定、完整原输入、复跑方法与授权边界见
[交接快照](../../handoffs/2026-09-19-t3-ratio-scope-review.md)。
