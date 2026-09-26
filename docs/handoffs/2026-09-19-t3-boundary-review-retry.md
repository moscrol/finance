# T3 同请求有界补审与新反例留证（2026-09-19）

## 结论与身份

**仍 hold：本轮外审返回了文本 `CHANGES_REQUIRED`，但原验证器判为 `INVALID_VERDICT / check_manifest / authority=none`。没有新增有效裁决。** 本地新比率量具为 **4P/10F**，未做业务修复；旧三量具仍 **6P/4P/16P**。真实金融会话与市场取数仍为0，旧自然效果 `not_passed` 不翻案。

- 原工作树 `/Users/a77/fwp-q-research-data-readiness`，分支 `q/research-data-readiness`。
- 审查业务提交 `d46c2c3b10221483c811426e99ad379314289871`，累计父 `d38dab3fea578f957794249a39d6b880d52f71f2`。
- 开窗文档 tip `b78dbe3be97b846ea2bd8093ae16f5d0bbfc73a8`；新只读量具提交 `52f6dee7e197d005442bda1da58f9f94f813c8a8`。
- d46→52f 的 `intelligence/`、`market_feature_store/` 差异为空。新增量具不等于修复，且未装成常驻 runner。
- d46原全量收据 `20260919T105730Z-d46c2c3b.json` 的12173P/87S/2x仍只签d46；本轮没有52f或后续留证tip全量收据。
- 未开PR、未合main、未部署；8792、夜跑、KB防写、其他T线、他人树与OPC shim封存均未动。

## 背景与本轮授权

上一窗ARL-0005单次600秒超时，没有最终信封或裁决。用户随后说“继续”，本轮将其落实为**同一请求的一次有界人工补审**：新独占目录、1200秒、$6上限，调用前固定，不中途续时，不自动重试、fallback或并行求绿。

旧状态根 `~/.finance-runtime/convergence-20260919/retention-repair/qc-repair-d46c2c3b/` 未覆盖。下文 `BASE` 指该 `retention-repair/`，新根为 `BASE/qc-retry-d46c2c3b-01/`，操作/诊断在 `BASE/boundary-review-retry-01/`。

先复跑原三量具，再核验历史归档；复制并逐字节核对21份继承文件（请求、claim、旧有效裁决、0004无效输出与0005超时等）。
请求SHA-256保持 `5fa3e7b7215bc83243e5f4a3e429cbca7770c791579cdce5d27d7a9cd13169d6`。
常规worker仍会选择未解决的0004；本轮沿既有operations脚本**显式靶向0005**，不是常规队列选择或聚合gate批准。没有改worker、validator、请求、claim、required checks或业务范围。

## 发现顺序与结果

### 1. 冻结预检：通过，但不是外部模型的工具行为

在精确、干净d46上：38个请求映射测试文件 **1301P**；原三探针 **6P/4P/16P**；46组撤保护全部执行，baseline/restored-full各601P。变异目录和每项日志保留。

全路径 `git diff --check` exit2属于已验证原始档案空白，fresh与archive-docs分别exit0。没有清洗原件。机械预检由隔离worker执行，外部模型不具备文件/执行工具，不能说“模型自行运行了1301个测试”。本轮未再跑全量工程或固定三仓门禁。

### 2. 外审在期限内返回，但检查清单身份不完整

| 项目 | 原始回执 |
|---|---|
| 调用 | 本窗口1次CLI；同请求第2次，旧600秒失败仍保留 |
| 开始/结束 | `2026-09-19T12:11:42.354474+00:00` / `12:31:31.626764+00:00` |
| 模型 | 请求别名sonnet，配置/消息/费用回执均 `claude-opus-5` |
| 耗时 | CLI 1189.272秒；派发适配器1312.493秒（含预检，不是模型延迟） |
| 返回 | CLI exit0、`timed_out=false`、success信封、原始总状态CHANGES_REQUIRED |
| 原校验 | `valid=false`、`errors=["check_manifest"]`、`authority=none`；直接校验exit1 |
| 费用 | CLI `costBasis=list` 报 `$1.5541615000000002`，非结算；本窗口上限$6 |

**失败不是“63项不够多”，而是检查对象错了。** 原合同要61个精确名称，模型返回63项，但只对上26项：漏35项（31个测试路径＋4个精确探针/变异名称），另造37个替代名称。35个缺失名称在原始提示中全部存在。JSON形状合法不代表检查清单完整，数量多不能补身份错配。原件未手工补齐、重命名或发布：

- `runs/ARL-0005/invalid-verdict.json` 保存模型原始裁决；
- `verdict-validation.json/.exit`、`dispatch-result.json`保存拒绝结果；
- `verdicts/ARL-0005.json` **不存在**；旧0001～0003有效CR仍在，0004/0005无效意见不算第四/第五份有效CR；
- 未另跑聚合gate，无权推断其通过或拒绝状态。

原提示512055字节。stream出现13条status事件和1条compact_boundary；有2个 `StructuredOutput` 协议工具块，不是文件/命令/网络工具。配置tools空，无MCP、插件、hook或持久session。信封 `num_turns=4` **不是provider请求数**，后者未知；整体usage与modelUsage原样保留，不自行混加。压缩事件与漏清单同时出现，不能据此断言单一因果。

### 3. 无效裁决可作线索，但先复现，不照单全收

新增 `scripts/review_probes/check_ratio_review_residue.py`，真实 `SemanticEpisodeVerifier.verify` + `recheck_material_public_delivery`，judge off/成功替身各一遍，无网络模型。三条完整原句逐字保留；另两条来自审查片段，**明确标记为作者补全**，不冒称逐字复现。

| 输入 | 来源口径 | d46实际 |
|---|---|---|
| `2026中报含金量为1.588，同比增长12%。` | 外审完整原句 | 正确主比率仍被残余扫描误降partial，产生无必要续修请求 |
| `2026中报含金量为1.588，样本量120。` | 外审写`…含金量为1.588，样本量120。`，作者补全期别前缀 | 样本量误报为未定位比率 |
| `2026中报含金量实际为158.7bp。` | 外审完整原句 | 无finding，仍completed；bp＝基点，不因未识别单位认证正确 |
| `收入可核[E1]，2026中报含金量待核对；该比率为1.587。` | 外审完整原句 | 四个连接词之外的续值未绑定，无finding仍completed |
| `〔比率对应关系**待核对**〕2026中报含金量为1.588。` | 作者给外审标记片段补匹配期别/值 | 去格式视图识别旧标记，raw视图却再插一个普通标记；第一次改写不幂等 |

每例两模式均失败；单一正确比率与已修“实际为”分号控制各两模式通过，总计 **4P/10F，exit1**。失败断言原样保存，不加xfail、不放宽判据。量具只证公开出口请求续修，**未单独测本轮新例的实际预算消费或自然修复成功**。

同一量具、同一财务夹具与原题在三份干净历史目标上对照：

| 目标 | 结果 | 限定解释 |
|---|---|---|
| 79dba348 | 6P/8F | 百分比/样本量尚不误报；无续值与标记支持；旧分号控制也失败 |
| 746b716f | 2P/12F | 新两类残余误报已存在；旧分号控制仍失败 |
| d46c2c3b | 4P/10F | 已修的分号控制转绿；五个新线索未解决 |
| 52f6dee7 | 4P/10F | 新量具提交后复验，业务未变 |

这不是质量抽样统计，也不是d46新增10个回归：两类误报可追到746；其他跨版本行为需逐例解释，不能用总数推断唯一引入提交。每次目标前后身份不变、模型调用0。

补充公告诊断另计 **4P/4F**：作者给“深交所互动易显示…”与“本期无任何披露文件”片段补完整查询失败上下文，和巨潮/零披露控制成对比较，确认误删来源句及漏拦否定句。它们不是外审逐字原题，不进入比率4P10F分母；未扩大公告词表。续修提示确实未明说“移除旧标记”，只签提示文字检查，不签自然作者是否会移除。

### 4. 两条审查观察必须按身份校准

- **“边界探针没有probe_sha256/target_unchanged”不成立。** 原脚本及完整回执都有，两次哈希相同、target_unchanged=true；模型看到的5000字符末尾视图恰好没有。摘要缺字段不等于源数据缺字段，原探针未为此重写。
- **“inflight仍746/4P12F”对冻结d46成立，对当时文档tip b78不成立。** b78在补审前已改为d46/16P。完整两份Git对象正文和哈希保存在 `post-return-diagnosis.json`，不抹历史、不假装当前仍欠同一文档修补。

## 决策对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 修改原裁决名称或以预检结果补齐35项 | 由作者代写外部审查，破坏权威边界 | 否 |
| 再发一次模型直到清单正确 | 超出本窗口一次调用，掩盖首失败 | 否 |
| 将无效意见全部丢弃 | 会漏掉可独立证伪的真实问题 | 否；仅降为线索，逐条复现 |
| 看到单位就统一当错误、或全豁免相邻数字 | 易把独立金额/差值误删或把真错值放过 | 本轮不实现；后续先定值槽角色与配对控制 |
| 跨句号任意继承比率主体 | 会猜主体/期别，超出原有限规则 | 否；句号边界仍显式列未覆盖 |
| 现在修业务并追加外审/自然会话 | 混合验收窗口、改动授权及预算不可追溯 | 否；本轮留红、归档、交接后停手 |
| 独立可复用反例量具入scripts，运维脚本仅归档 | 便于精确复验，不再造常驻系统 | 采用；未修改validator或其门槛 |

后续如优化外审材料，应保留完整语义范围、精确清单与不变请求；可减少重复源码展示、显式呈现哈希字段，而非丢业务差异。未在本窗口实施或重发。权威门禁本次正常拒绝，并非要改松的洞。

## 归档与复跑

当前档案 `docs/verification/2026-09-19-t3-boundary-review-retry/`：**331原件 / 7,684,433字节**，README、manifest另计。历史225+796+681+561＝2263原件及其runtime来源逐字节核对未变。`.py/.log/.diff`只加`.txt`展示后缀，排除冻结树、锁、缓存；不收明文凭据，运维派发脚本不安装。

关键导航：
- `boundary-retry-closeout-outcome.json`：本窗总账；
- `qc-retry-d46c2c3b-01/retry-policy.json`、`inherited-chain.json`：预定窗口与继承身份；
- `qc-retry-d46c2c3b-01/runs/ARL-0005/`：预检、提示、stream、信封、invocation-result、invalid-verdict；
- `qc-retry-d46c2c3b-01/verdict-validation.json`、`dispatch-result.json`：原门禁拒绝；
- `boundary-review-retry-01/post-return-diagnosis.json`：61项集合差、两项观察校准、提示文字与补充公告；
- `boundary-review-retry-01/residue-{d46c2c3b,746b716f,79dba348}.json`：新红针与对照；
- `boundary-review-retry-01/probe-tip-*.json`：精确52f四探针复验；
- `boundary-review-retry-01/input-accounting.json`：输入分段字节，不是token或根因诊断。

```bash
umask 022
cd /Users/a77/fwp-q-research-data-readiness
env -i HOME="$HOME" PATH="$PATH" LANG=en_US.UTF-8 FORESIGHT_LLM_KEYCHAIN=0 \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/review_probes/check_ratio_review_residue.py \
  --code-root /Users/a77/.finance-runtime/convergence-20260919/retention-repair/candidate-d46c2c3b/registry-pinned/finance-workspace-private \
  --expect-revision d46c2c3b10221483c811426e99ad379314289871
```

预期 **exit1/4P10F**，不是成功。换原三量具仍预期exit0/6P、4P、16P。原件量具SHA `34ea6608e4f19305befd1b428c3ac9cfdf326a6bb0622fc2e221eb35ff01b736`。

本次派发、自建审查树已退出/移除，三个记录PID核对均不在，无后台续审。归档提交后的检查日志另留runtime，不冒称预先包含在331件中。

## 补记（2026-09-19 晚 质检核对）

- 「同一请求」指请求对象不变（SHA `5fa3e7b7…`），不指提示字节：第二次调用的提示 SHA 为 `a087adcb…`，首次 600 秒超时那次为 `a002a150…`。差别只有窗口段落措辞、嵌入 `prior-timeout/invocation-result.json` 与 `retry-policy.json`、600→1200 秒与尝试计数；适配器 `qc_repair_once.py` 因此从 `793012a0…` 变为 `b3a8431e…`（`adapter-provenance.json` 已记两版 SHA）。验证器、请求、claim、必需项、业务范围未变。
- 「12173P/87S/2x」中的 2x 只见于 pytest 日志行「2 xfailed」；收据 `counts` 只有 passed/failed/error/skipped，无法从收据本身核出。
- 收据目录另有 `20260919T105310Z-d46c2c3b.json`：0 passed / 0 failed / exit 0 的空读数（疑为 collect-only），本交接从未引用；`check_test_receipt.py` 目前不拒绝零计数收据，列为后续守卫，不在本分支改。
- 本窗五类线索的修复见 [残余反例修复交接](2026-09-19-t3-residue-repair.md)（业务 `6fb37a6e`）。

## 下一步与禁止事项

1. 保持hold。沿原q线先以新量具固定五个输入，配对“错值被拦／独立事实不误伤”，决定明确续值及单位语义；公告新片段单列，不偷偷扩成通用解析。
2. 修复若产生新业务SHA，重冻工程全量、固定三仓、旧三探针、新红针与46组既有变异及新增保护。旧全量不能移签新提交。
3. 新外审窗口须另明确期限/预算/独占根；保留0001～0003有效CR、0004无效PASS、0005超时及本次无效CR，不补造有效裁决填洞。
4. 有效独立裁决之后，真实conversations仍须固定代码、原题、证据、GLM flash/5.3兜底与预算单独验收；不得拿机械预检或成功替身改写旧自然失败。
5. 合main、部署、8792切流、夜跑、KB解锁、其他T线继续另授权。
