# 302132 第七轮前有限 Spec 复核

2026-09-20；工作流：code-review 的 Spec 轴。候选始末均为 `3736d5bfa9978dfa0a264bb2e44795c4bc29b27d`，工作树干净；产品代码 `00d64e373e04366b6bdb7602c5ce4397759adefd`；固定比较点 `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`。未改候选、未外呼、未打开或复制真实/历史大型数据库、未跑全量、未合 main 或执行生产回填。

结论：定向写入、staging 父子编排、独立基线 oracle、源表整表不变和逐轮输入绑定的设计方向合理，适合继续进入第七轮审阅；本次不能签通过，发现两项具体 P2 验收缺口。它们不证明写入器已产生错误生产数据，而是证明验收器仍可能签错对象或丢失失败收据。本次是有限 Spec 复核，不代表独立 Standards 轴通过，也不代表整分支当前主线准入。

## 两项发现

1. **P2：共同改写目标股票后，收据仍可借用原股票数据签绿。** `scripts/verify_302132_backfill_acceptance.py:186` 只检查 `spec.code` 的代码格式；`:303` 只检查子报告与 spec 一致；实际数据检查从 `:563` 起使用固定 `CODE`（`:95` 为 `302132.SZ`）。同一微型基线/结果库/parquet，正常对照为 `37/37 PASS`；仅把 apply/verify 两轮的 `spec.code` 和独立/嵌入 `child.code` 同步改成 `000001.SZ`，仍 `rc=0, 37/37 PASS`。这违反执行设计文档第 13 行的“同一输入同一合同下的幂等复验”，也漏掉了实际授权对象绑定。证据：`control/acceptance.json`、`spec_other_code/acceptance.json`、两目录的父/子收据。最小修复：专用验收器明确要求 `spec.code == CODE`，并逐轮拒绝另一合法股票代码；不能单纯改成从收据读取实际查询对象，后者仍缺外部授权锚。边界测试：合法但错误代码，两轮同步/仅一轮，原正常对照保持绿。

2. **P2：数值 schema 自身可溢出，异常仍以 rc=1 裸逃逸。** `scripts/verify_302132_backfill_acceptance.py:129`–`:132` 对任意 Python `int` 调用 `math.isfinite`；`:423` 调 `_validate_receipt` 时不在异常转换边界内。相同产物只把两份 spec 的 `pinned_technical_0911.ma26` 改成 JSON 整数 `10**400`，得到 `OverflowError: int too large to convert to float`、`rc=1`、没有输出 JSON。执行设计文档第 12 行要求结构错误归结构化 FAIL（rc=2），此处未覆盖。证据：`huge_numeric_pin/stderr.txt` 和 `probe-results.json`。最小修复：有限数值判定捕获转换溢出并返回 False；验证边界再确保 schema 错误被写成明确失败检查。边界测试：正/负超大整数、正常有限 int/float，以及现有 NaN/Inf/bool 反例。

## 已真实验证到哪一层

- 今日指定解释器跑 `tests/test_repair_backfill_stock_history.py -k acceptance`：**65 passed / 24 deselected，7.21s**。包括第六轮已知的源/输出共同变异、逐字段 schema、apply/verify parquet 对称臂及跨轮 spec 变异；这些旧反例的修复仍成立。证据 `acceptance-tests.log`。这不是全量门禁。
- 读取历史 v6 原件：`49/49 PASS`，revision 是完整 `00d64e37`，apply `3925f59c0281` / verify `9b2b60f7278c`。两份原始父收据用当前 schema 复验无错误，与独立子报告深比较相等。仅对小 JSON 的哈希复核：冻结清单列出的 **12 份旧收据 + 5 份历史验收 + 1 份备份收据，共 18 份全部相符**。没有重读大型基线、结果库或备份，故本次不能独立重证历史数据层 49 项。
- 历史全量原收据 `20260914T080259Z-00d64e37.json` 确为 **9706 passed / 0 failed / 77 skipped**、dirty=false、dependency_gate_bypassed=false；这是 09-14 的事实，不能当作 09-20 最新主线门禁。全部核对明细在 `historical-evidence.json`。
- 本地 `gitea/fix/backfill-302132-scoped` 已指向 `3736d5bf`。旧 inflight 的“未 push”过期；按上游已核验推送状态更正，勿重新写成未推。未发网络请求复查远端。

## 第七轮最小剩余工作与权限边界

1. 串行实施上述两项最小补丁，保留本目录正常对照和原反例原件；用新的输出目录、固定修复后 SHA 重跑，确认原反例变成结构化 FAIL rc=2。
2. 对修复后的最终源码做有边界的独立审阅。若需要完整 code-review 结论，Standards 轴仍应独立完成；本报告不可替代它。
3. 候选底比固定 main 落后 479 提交。整合到最新主线候选后，重核 CLI/父编排接口与最终源码身份，执行适用的本机等价 CI。不得用本次 65 项或旧 9706 项替代最终组合门禁。
4. 依据执行设计文档第 122 行，若合法日更改变基线，生产前重新盘点 spec 钉值并重做获授权的副本演练；原 v6 不覆盖今日生产状态。本次未确认生产基线，不能据此直接开跑。
5. **合 main 仍须用户确认；真实回填、canonical 换库及额外并跑表补齐另需其既定授权。** 生产验收角色继续使用换库前备份作 `--production`、换库后 canonical 作 `--clone`，并绑定当次备份 sha。修验收器不扩大生产授权。

## 可复跑命令

见 `commands.txt`；测试自动写全局收据只为遵守本次输出目录边界而设 `FWP_TEST_RECEIPT=0`，解释器/依赖门禁保留。微型探针构造 30 个市场日的合成数据，调用真实 child 写入函数和独立验收器；父收据是夹具，不冒充真实父编排重演练。`probe.py --tree <修复树> --output <新空目录>` 支持在固定新修订复用同一反例。首尾身份及六个候选文件 SHA256 见 `identity-before.json`、`identity-after-probe.json`、`identity-final.json`。
