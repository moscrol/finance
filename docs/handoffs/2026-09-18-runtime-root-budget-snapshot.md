# 根预算快照前置片：余额、授予身份与捕获位置

## 背景与范围

用户已授权按最优顺序执行 OPT-08。沿既有 runtime + ResearchHarness 吸收行为合同，不叠框架、不合 main、不部署、不做生产中断或付费模型对照。

此前的 [P0](2026-09-18-runtime-contracts-p0.md)、[子研究存储](2026-09-18-runtime-contracts-p1a.md)、[恢复保存确认](2026-09-18-runtime-restore-confirmation.md) 均有各自固定证据。恢复确认文档提交为 `5c4c96ef`；本片代码冻结在 **`610dcbeb1168db65638c571490dd46a919e7378a`**。以下新增结论只签本片，**没有实现跨进程消费 ResumePlan 的 driver**。

一个预算不只是余额：它还记录已经授予过哪些额度。重启后丢了 grant/promotion 编号，即使恢复了余额，也可能重复授予。另一危险是恢复程序补写中断结算，却把原来的预算余额贴到新的日志位置，伪装成已经对账。

## 按发现顺序

1. `research_contract.py::InMemoryRootBudgetLedger.to_dict()` 已有初始、硬帽、余额和累计分配；`_grants` 仅是编号集合，`_promotions` 不在摘要中。`sub_research_tool._root_budget_snapshot` 是前后观测的两项余量，不能当完整恢复格式。没有重写这两个诊断出口。
2. 先写 JSON 往返/拒绝损坏/唯一根/检查点接线测试，初轮28F留证。新增 `to_snapshot/from_snapshot` 及 `restore_root_budget`：schema_version=1、kind=root_budget；保存初始和当前帽、余额、累计分配、授予金额及两类去重身份。保存初始帽是为了发现升档记录丢失，而非只检查当前帽够大。
3. 严格读者拒绝版本/字段不符、错 episode、bool 冒充整数、负数/非有限秒数、余额超累计、授予记录与累计不符、升档帽交叉/不匹配。返回新对象，不持原 payload 引用；读取校验不登记活根。恢复工厂与新建工厂共享进程内锁和弱引用登记，两个并发恢复只能登记一个。
4. `_EpisodeLedger.put_state` 从当前有效 context 取根预算，而非只存初始 configure；真实 deep 升档与同进程 repair 都能保存最新状态。`EpisodeState` 深冻结快照并 JSON 往返；旧日志和 child view 保持显式 None，不能按 policy 猜出初始满额。子预算仍是共享父额度的非铸币视图。
5. 故障注入暴露：编码抛错/无效对象会硬退出；返回 None 则可能假装正常 durable。新增本地状态编码故障入口 `FencedEpisodeStore.fail`，复用锁外通知；生成/校验失败共享整树 fence，阻新模型/工具/兄弟写入，不写缺预算的假检查点。done 前已有稿/证据留私有；磁盘可有 finish，但没有被确认的 done。
6. 工具热路径在 `tools_settled` 后才扣账，repair 在扣账前写 state。调整为先扣已执行批次，再暴露步点或写正常/修复检查点。同时失败测试抓到旧 `_settle_batch_calls` 的秒数超支降级只结时间、漏调用槽：现在 `consume_call` 拒绝两个扣项后，分别扣已执行槽位及可结的时间；耗尽不扣负数，不把已执行当免费。
7. 增加 `budget_snapshot_sequence`，记录捕获时的前缀，必须在 checkpoint 内；恢复合成 plan/closed 时原样保留，不冒充已对账到新 last_sequence。**它只是捕获位置，不是事务性计费水位：相等也不证明所有在飞效果已结算。**
8. 旧 linked-tree 测试用最终余额配手工删 finish 的旧前缀，被新校验拒绝；改为记录真实非终态检查点前缀，保留“关联树拒绝且不改日志”的原断言。测试自身两处构造错误亦留首红：把共享执行 CancelSignal 当独立用户停止对象；把 mode_signals 误传 Episode 而非 FinanceResearchHarness。修的是夹具，不放宽保存/恢复合同。
9. 扩大回归通过后冻结610dcbeb。新17项撤保护和四叶独立完成；因触及共享 fence、state 和旧前缀夹具，同revision另复验旧P0/子存储/恢复确认三组变异，全部完成。

## 方案取舍

| 方案 | 评价 | 选择 |
|---|---|---|
| 按当前policy重建满额 | 丢已花费用与授予身份，可能二次发额度 | 否 |
| 直接复用to_dict或工具前后余量 | 是诊断摘要，不含恢复去重事实 | 否 |
| 版本化完整根快照，当前检查点接线 | 可校验余额/授予/帽，能保原身份；仍需未知效果对账 | 是 |
| child view还原成独立根 | 并行子任务凭空加额度、破父子共享 | 否；子快照暂缺席、关联恢复仍拒绝 |
| 恢复补日志后把预算位置也更新 | 没有新扣账却声称已对账，未知效果被洗掉 | 否；保原捕获位置 |
| 编码失败省略预算后继续保存 | 生成有效外观的缺现场checkpoint | 否；整树fence，不回滚磁盘前缀 |
| 只结平超时秒数、不扣调用槽 | 已执行效果免费，后续grant/恢复可重用槽 | 否；两类资源分别结算 |
| 现在直接消费ResumePlan | 授权/证据/查询/inbox/单写者和对账尚不齐 | 否；下一片继续补现场 |

本片不另立平行词表或 ADR：新增的是通用预算持久化字段，不是新的金融领域术语；详细取舍在本快照，既有词表不混入实现说明。

## 固定工程证据

证据根：`~/.finance-runtime/reviews/runtime-contracts-610dcbeb/`。
规定解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python3.12.13、依赖指纹 `3328bed61f3e21ea`。被测实施树全量前后均干净；全量期间没有改其源码。

| 检查 | 固定610dcbeb结果 |
|---|---|
| Ruff | exit0 |
| Python全仓 | **11598P/81S/2X**，17 warnings，521.68s |
| 前端 | offline frozen-lockfile安装、lint/typecheck/test/build均exit0；**107P/8 files** |
| E2E | **34P/2S**，59.4s；8893/8894隔离端口，显式RE06_E2E_URL |
| registry | parseability/check/backfill-tables/generate-views及crosswalk均exit0 |
| 精确收据 | `20260918T130950Z-610dcbeb.json`；dirty=false、未绕依赖门、七项核验通过 |

本机Node26/pnpm10.12.1，不能外推为Linux/Node22完全同环境。

### 撤保护

复用 `scripts/review_probes/run_extraction_mutations.py`，不复制runner。以下每组独占临时树、固定完整SHA，逐项实际执行并红→还原绿，`complete=true`。局部测试不生成全仓收据。

| 定义 / 证据子目录 | 项数 | baseline/restored-full |
|---|---:|---|
| `root_budget_snapshot_mutations.json` / `budget-mutations/` | 17 | 各61P，仅新单文件 |
| `runtime_contract_mutations.json` / `p0-mutations-regression/` | 13 | 各167P，仅原三文件 |
| `sub_research_persistence_mutations.json` / `child-mutations-regression/` | 14 | 各67P，仅原三文件 |
| `restore_confirmation_mutations.json` / `restore-mutations-regression/` | 7 | 各32P，仅原两文件 |

新17项依次覆盖：余额、grant身份、promotion身份、episode匹配、授予累计一致、升档帽一致、同进程唯一根、检查点接线、必需快照不消失、编码失败共享fence、深冻结、恢复plan保预算、closed保预算、原捕获位置不换新、工具步点前扣账、repair检查点前扣账、秒数超支不退调用槽。

每项至少一条实际断言失败，不是导入/collection/语法红；检查点接线变异的第二条deep测试另有None下标TypeError，同项第一条已在值相等断言红，原日志完整保留。变异的restored-full都是所选集，不是全仓；各组和全仓有重叠，不加总。

## 首红与局部读数不抹掉

首轮及修复过程日志复制到上述证据根 `prefreeze/`，原 `/tmp/runtime-contracts-budget-snapshot-*.log` 亦在：

- `red.log`：28F，API/接线尚未实现；收据 `20260918T120834Z-5c4c96ef.json`。
- `first.log`：85P，早期五文件，不覆盖后续边界。
- `boundaries-red.log`：10F/32P；编码故障九格和工具扣账步点反例。
- `regression.log`：九条取消夹具误断言，修为独立用户谓词；不是产品混淆用户取消。
- `order-red.log`：1F/49P，超时漏调用槽；`missing-red.log`：3F/56P，根快照None假成功。
- `wide.log`：1F/564P/3S/1X，旧手工截断prefix带新预算位置，改真前缀；`promotion.log`：1F/84P，mode_signals构造位置错误。
- `prefreeze.log`：**567P/3S/1X**，14.34s，dirty收据 `20260918T125755Z-5c4c96ef.json`，不冒充固定全量。

旧 e336093e 首轮 provenance 单项红仍未定位根因；7f/371/610全量绿均不是对应产品修复，证据和未明状态继续保留。

## 沉淀及状态

- 产品门页和执行计划随代码更新；本快照及≤3K inflight后置写入，不提前声称完成。
- 工具包独立树 `docs/runtime-contracts-0918@e2c249b` 同步 BUILD/KIT/TOOLKIT：恢复预算保身份与原位置、超时不退款，仍不是driver。编辑前核工作树干净、对gitea/main落后0，正文以main提交读，不碰共享主树脏文件；未合main。
- vault既有能力图谱原行和项目一行索引更新，提交 `756fe35d`（本机非受保护区小回写，未手工push）。图谱80行/193断言无漂移，142条在途/未校验；类名存在不代表本片行为已合。
- vault本片前后均20 errors/17 warnings，错误集合无新增/无移除。未修受保护作者枚举/镜像或别人的死链，不称全绿。

## 下一步与禁止误用

1. 补完整授权合同/策略与registry重验、证据E号/owner/日期/原件、QueryLedger去重/缓存准入、Inbox正文/目标/身份/回执和绝对截止/取消。
2. 完善单写者/重复启动与父子预算、未知在飞效果对账；然后由同一loop消费ResumePlan，仅临时目录真实进程中断验收。当前工厂的进程内唯一根不是跨进程lease。
3. 有快照不代表事件与预算是原子事务。模型结算、工具事件、扣账、checkpoint之间仍有崩溃窗口；新驱动必须保守对账。未知请求不能因无结果/合成interrupted便视为免费或安全重放。
4. 旧日志None不补猜；child view不可单独恢复；快照验证不是防恶意篡改签名，不证明原授权或外部计费真实性。
5. 继续原顺序：压缩原件回读、Workbench插话、P2逐工具执行属性。保持能力/IO限制、原绝对窗口、父子共享预算及子研究无发布权。
6. 真模型质量、独立双审、合main/部署均另需证据或授权。本片没有生产kill/restart、真实模型请求或公开答案送达认证。
