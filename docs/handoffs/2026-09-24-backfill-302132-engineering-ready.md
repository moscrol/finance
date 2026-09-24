# #83 / #813 当前 main 前向与工程就绪

## 后续状态

本文记录 ca4 的完整工程通过快照。发布前主线又合入 #884 至 `4cc15e703`，含门禁及测试变更；已前向到 `3c5b3c9a6`，在 `continue-08/` 完整重验通过。最新结论见 `2026-09-24-backfill-302132-current-main-ready.md`；本文ca4收据只对旧候选有效，实时状态以树外 `CURRENT.json` 为准。

## ca4 结论与入口

2026-09-24，作者工程验收与整库副本验收均已完成，状态为 **ENGINEERING_READY_PENDING_QC**。#75 独立审查未完成，保留 #813 WIP；未合 main、未执行生产回填、未重启 8792、未改 launchd，也未停止其它任务。

- 唯一被验 head：`ca4b33316c47862ecd3ec71a535a51d540ada986`，已推 #813 的 `fix/backfill-main-ready-0921`。
- 基线：`a54fed0d065ffdf025734a69420c1fe530615eb1`；收尾复核 main 未再前进，基座漂移 0。
- 被验树：`~/.finance-runtime/reviews/backfill-302132-0923/forward-01/tree`。
- 证据根：`~/.finance-runtime/reviews/backfill-302132-0923/`；动态入口 `CURRENT.json`；本版本原件在 `continue-07/`。
- 归仓证据索引：`docs/verification/2026-09-24-backfill-302132-ready/`。其中 verified-closeout 的哈希键相对于原始 `continue-07/`，原收据未改写路径或版本。
- 本文只提交文档分支 `fix/backfill-302132-0923`，不推进 #813。文档分支代码仍是旧版，不得从该树执行验收或生产命令；执行根只认上述被验树。

## 发现顺序

1. fd6 的 `continue-05` 整库演练通过；随后 Python 因磁盘保护在 1427.895 秒中断，没有终局收据。保留原中断记录和临时现场，不以定向绿补齐。
2. 容量恢复后，fd6 的 `continue-06` 完整结束：15004P/0F/0E/85S/2X，collected=15091，完整范围校验通过。此时 fd6 的四叶和副本验收都有效，但只属于 fd6。
3. 最终回读发现 main 从 `3bb81b963` 前进到 `a54fed0d0`，包含运行时、schema、写入路径、CLI 等源码更新，不能只按顶端文档提交判断无影响。
4. 从 fd6 新建 `codex/backfill-forward-0924`，合入固定 a54。仅 INDEX 与 QUEUE 有冲突：保留 main 的其它工单行，再更新/补入 #83。CLI 自动合并，回填修复未手改。生成 ca4，父提交为 fd6 和 a54，快进推 #813。
5. ca4 独占干净树上重新运行全部工程检查和完整副本演练；旧收据没有移签。本轮所有阶段正常结束，收据版本、日志摘要、完整范围和远端身份已重新核对。

## 本候选证据

| 检查 | 结果 | continue-07 原件 |
|---|---|---|
| 回填与演练定向 | 118P | focused-receipt.json、focused.command.json |
| Python 全量 | ruff PASS；15400P/0F/0E/85S/2X；collected=15487 | python-receipts/gate-QOq3gEkV/pytest.json |
| Python 收据 | expected-revision 全等、require-full-scope PASS、base drift 0 | scope.command.json、scope.log.txt |
| 前端 | install/lint/typecheck/120 项单测/build 全 0 | frontend/frontend.json |
| E2E | 34P、2 个既有跳过；超时标准不变 | 同一前端收据、e2e-results/ |
| registry CI | 工作流五项全 0；仅本仓，与 CI 的缺席跨仓跳过一致 | registry-complete/receipt.json |
| 整库副本 | 发布、复跑、37 项验收、金额异常对照、恢复全部符合预期 | rehearsal/summary.json、acceptance.json、amount-control.json |
| 合并预览 | a54 + ca4 无冲突，树 5bf5716f35a7c60fbb50404786c5e9bbeb3d670e | verified-closeout.json |

全量用中性 basetemp、pytest 原生 `tmp_path_retention_policy=failed`，没有用例筛选或断言/超时放宽；runner 1208.914 秒，最低可用空间 79066021888 字节，未触发 4 GiB 停止线。门禁成功后清理本轮 basetemp。前后 revision 一致且全树干净；自有 runner/pytest 均已退出。

PR 相对 a54 的增量未命中 data-quality-check 工作流路径条件，不据此声称额外数据工作流执行过。注册表首次记录的 identity_before 为 runner 的固定期望值；外层 main() 在执行任何检查前实际核对了干净身份，after 为实际读数，未用缺省值补齐未知身份。

## 数据结论与边界

固定范围仍为 `302132.SZ / 2026-06-15..2026-09-11`：53 INSERT（并跑源 51 日、冻结 parquet 两日）+ 06-23 空壳 UPDATE，保留 09-11 钉值，其它股票和目标股窗外全列零差。

- 副本 apply run `61caddc4c789`；verify run `d3c8e3d56309`。
- 回填前窗内 11 行，close/pct_chg/amount 各 10 个非空；后 64 行，三项各 64 个非空，无相邻三项值整行克隆。technical=39，window=161，5/10/20/60 日窗为 59/54/44/4。
- 错误 parquet 的父命令 exit 2，无发布；注入 amount=1e15 后验收 exit 2，37 项中仅 keyset_fullfield_oracle 按预期失败。
- 生产前后 stat、各 fact 最新日期及完整 SHA 不变；恢复副本 SHA 与基线同为 `5f8e86cd854b7c6569cdcb62bfb5e9861d1d3a804d8f521480003185323dc91e`。
- 冻结 parquet SHA 为 `51f9ee9cba1ceb4a6ff50c4c4dce8267cb39f78add28d6a33699cbf90bf28d17`。成功后四个演练大库副本已按脚本清理，保留运行记录、值审计及输入。

这证明 ca4 对本轮冻结数据的副本操作，不证明未来生产基线仍不变。业务文本仍可能将含股票代码的来源路径误判为股票范围；中性测试路径只隔离测试输入，未修该产品边界。

## 决策与被否方案

| 决策 | 被否方案 | 理由 |
|---|---|---|
| 从当前 main 重新冻结 ca4 并全验 | 将 fd6 全绿移签 ca4 | 新主线含真实源码变化，旧绿不能证明新组合 |
| 冲突保留 main 其它工单行，仅改 #83 | 用旧分支整表覆盖新台账 | 不能倒退其它 agent 已完成的合入事实 |
| 文档与产品 head 分离 | 完成验收后再向 #813 加交接提交 | 保留稳定的收据身份；所有执行命令显式指定被验树 |
| 工程 ready 与独审/合入分开，WIP 保留 | 作者四叶绿就宣称独审已过或自动合入 | #75 是独立证人，合入和生产还各有授权边界 |
| 保留中断原件，重新整轮执行 | 把局部成功累计成全量 | 中断无终局，统计不可拼接 |

工具使用现有 run_main_gate / run_frontend_gate / CI 声明及正式 rehearsal 量具。仓外 runner 只是固定版本的启动与资源保护附件，不引入新的产品门禁；verified-closeout 是原件身份/哈希对账索引，不替代实际测试。原系统函数模拟缺陷已有作用域修复、恢复断言与撤作用域反例，方法继续复用 agent-memory 的 pytest-temp-paths-and-mock-lifetime，无新增重复框架。

## 下一步与禁区

1. #75 按 ca4 审查，工程已具备送审条件，但不宣称独立 Spec/Quality 结论。#802 已关闭且评论 6446 指向 #813，旧分支保留。
2. 审查通过后，请用户明确确认合入；重新读取 PR head/main/干净身份。main 或候选改变，先评估合流并重取相应版本收据，不能把本文视为滚动许可。
3. 生产另需对命令、日期范围、冻结输入、本轮备份回滚点逐字授权。授权模板归档于证据目录 production-authorization-draft.md，动态副本在树外证据根；CLI 没有 --record，授权另存 JSON。
4. 模板不是已授权命令。回滚只取本轮父收据 backup.backup_path / backup.backup_sha256，不用演练备份或“最新备份”；执行前无活跃写者、无 WAL，且确认不覆盖后续业务写入。不得自行重启 8792、修改 launchd 或扩大股票/日期范围。
