# 外盘换源接续：本机门禁、复权失败保护与部署边界

## 背景与身份

接手时 GitHub #65 为 `data-source/overseas-akshare-1006@2bc118a712d245bb78fee6c739dd5ecab52ef420`，基线 `ea217633c`。Claude 已完成外盘回填、用户二次确认后的原子换库及删除过期提示的源码修改，但全量本机门禁尚未运行。主目录有大量其他任务改动，未碰它们；在原分支继续源码工作，测试使用两棵固定提交的独立 detached 工作树。

本次源码补修：`d9c352d50`；回归测试隔离修正：`3c57aab6a5d0cd709c8dbc220f8f83da33c487fe`。以下完整工程结论只签 **3c57aab6a**，随后纯文档/证据提交不冒充同 SHA 测试。GitHub #65 已推送该源码，未合并、未部署。

## 按发现顺序

1. 核对 `~/.finance-runtime/backfill-overseas-rebuild-1006/swap-result.json`：22:27 换库 `swapped=true`。保留原授权记录、APFS 备份和哈希，不重复换库。
2. GitHub #62/#65 的失败注释明确为 **account payments / spending limit**，job 未开始。不是测试红，也不能拿本机绿绕过远端门禁。
3. 环境核对发现共享 `.venv-workbench` 的 httpx=0.25.2，与依赖锁 0.28.1 不符。只读复用 `finance-workspace-ffe1c60d84da/.venv-workbench`，`workspace.py doctor` 无依赖漂移；Node 固定 22.23.3、pnpm 10.12.1。没有修改生产共用环境。
4. 离线反例发现：原写入器吞掉前复权异常，回退裸价收益，在一拆四夹具上 `status=ok`、`skipped=[]`、涨跌幅 **−74.8762376%**。这与“拆股不会假暴跌”的承诺矛盾。
5. 补修要求实际价/前复权最近六场会话窗口一致，复权价格为正有限数；缺数据、错场、窗口缺场时跳过受影响目标并记 `adjusted_*`，计入原有 5% 缺口门。完整值源仍写实际收盘、复权一场/五场收益。未扩大回填范围、未改截止日语义。
6. 新增八个用例在旧实现 **8 failed / 11 passed**，修后 **19 passed**。变异初轮 17/18：缺前场用例被更早的错场目标遮住；把该用例计划起日挪到拆股日，最终 **18/18 killed**，还原后树干净。原红记录保留。
7. 原头完整 Python：20702P/1F。唯一失败是本次 runner 把 TMPDIR 放进 `.finance-runtime`，触发 `test_default_index_is_redirected_away_from_home`。将临时根改为 `/private/tmp/pr65-final-*`，不修改该保护或测试；三项定向通过，再对最终源码跑完整门禁。

## 最终验证（3c57aab6a）

| 项目 | 结论 |
|---|---|
| Ruff | 通过 |
| 完整 Python | **20711 passed / 0 failed / 0 error / 76 skipped / 2 xfailed**，1003.41 秒 |
| 收集面校验 | `check_test_receipt.py --require-full-scope --expect-revision 3c57aab6a…` exit 0；collected=20789，无 ignore/k/m/deselect/maxfail |
| 前端 | install / lint / typecheck / **210 单测** / build 全通过 |
| 端到端 | **52 passed / 2 skipped**，独立 18981/18984 服务与测试用户态 |
| 注册表 | parseability / check / tables / views 四项 + ledger crosswalk 全通过；缺席配套仓按 CI 的单仓范围跳过 |
| 写入器 | 19 单测；18/18 变异；8 新反例修前均红 |

精简原件已入 `docs/verification/2026-10-06-overseas-takeover/`（checks、Python/前端收据、变异定义/结果、原始输出、生产只读核验和 GitHub 失败注释）。完整日志、JUnit、首轮失败现场及重放脚本在：

`~/.finance-runtime/backfill-overseas-rebuild-1006/takeover-20261006/`

其中最终门禁在 `final-3c57aab6/`。每份收据自带树、revision、依赖指纹/日志哈希；临时测试树会正常移除，收据中的旧路径是历史身份，不是待复用生产根。

## 主库只读复核

- `fact_global_index_daily` 2120 行；`fact_global_stock_daily` 82256 行；均到 2026-09-30。
- 19 个断档日每天 5 指数 / 194 美股；两表复制判据命中均为 0，会话晚于主键日均为 0。
- 与换库前备份比较：非本次回填的旧行无变化、旧主键无丢失。
- 本次按新浪值写入的 **247 指数行 + 3692 美股行**逐行与冻结缓存相同；美股一场/五场复权收益窗口均匹配。本轮审查未发现复权失败回退污染本次数据。
- 新代码只读重算换库前备份，targets / computed / written_as / skipped / samples 均与原 apply 报告相同；这是计划摘要一致，不冒称逐字段写入重放。
- 前后主库 inode/mtime/size 一致。本轮没有写生产库，也没有再次抓源数据。
- 备份 SHA256 重新核过：`58f01a1c2f10be830c2104a750da1892bb6849de5a96100a9a2a5d32083f9e44`。

## 决策与被否方案

| 选了什么 | 否了什么 | 原因 |
|---|---|---|
| 复权失效留缺口，沿用 5% 阈值 | 裸价收益兜底；一只失败就停全批 | 裸价会制造拆股暴跌；全停会扩大既有授权。21 只缺 1 只的回归锁住局部跳过。 |
| 用原缓存和备份只读验证 | 为证明修复重新回填主库 | 已写数据与源一致；重复写入增加风险且没有必要。 |
| 借匹配依赖的现有环境 | 升级生产共用 venv | 服务确实使用共享环境；测试准备不该变更线上依赖。 |
| 修 runner 临时目录后完整复跑 | 删保护、ignore 失败测试、宣称全绿 | 失败由本次运行配置引入；保留旧红，新收据单独签固定源码。 |
| 注册表只更 duckdb-backfill 哈希 | 缺配套仓时强行 scan | 正文变更不影响元数据；全扫会删除缺席仓登记项。check 已验证。 |
| 保留部署/CI 边界 | 用本机绿绕过 Actions，或直接切 8792 | 仓规要求 Actions 绿与用户确认；本轮是接续检查与修复，不是新的上线授权。 |

## 仍然没完成的事情

1. **GitHub Actions**：用户处理 Billing & plans 后重跑 #65 与 #62；没有改套餐、支出上限或 workflow。
2. **合并/部署**：用户确认后才合入。8792 health 本轮读回 healthy、源码仍 `d5d7c5f6017e`。过期警告只在 PR 源码里删除，旧服务仍可能说那句话。未发新模型请求。
3. **截止日可见性**：旧 57.4 秒探针证明本地数据能返回，不证明“D 日开盘前隔夜”正确；答案用了 D 的美股场次，实际北京时间 D+1 才收盘。文案已解释但工具硬过滤仍未改，不能把该答案签成无前视。
4. **夜跑接线**：本 writer 未接 local 日更；09-30 后 A 股日还需后续执行/接线。
5. **存量差异**：未纳入原授权的约 3000 条美股基准/原因不明差异仍留待专项；本轮不把全库存量称为全部对账一致。

## 工具沉淀

保护与回归已进产品源码，操作边界进 duckdb-backfill 正文与 runbook，18 组变异定义入库可复跑。本次运行包装器/冻结缓存审计是带本机路径的单次执行记录，保留在证据根，不升格为通用工具或增加第二套门禁；正式门禁复用仓内 `run_main_gate.sh` / `run_frontend_gate.py`。未修改共享 harness/记忆仓或加入新的定时任务。
