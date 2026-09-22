# 恢复授权快照：保存旧许可事实，不抹执行位置

## 背景与结论范围

用户授权沿 OPT-08 按最优顺序推进：吸收行为合同，保留自有 runtime + ResearchHarness，不叠框架。实施枝 `fix/runtime-contracts-0918`，树 `~/fwp-wt-runtime-contracts-0918`；本片首冻 **`576d4764892d7be3d9218f7b38e05a29fde963a0`**，补丁冻结 **`6b70e54034b0fab736430d7e3d00d6f4f7fd617a`**。

[P0](2026-09-18-runtime-contracts-p0.md)、[子研究存储](2026-09-18-runtime-contracts-p1a.md)、[恢复保存确认](2026-09-18-runtime-restore-confirmation.md)、[根预算](2026-09-18-runtime-root-budget-snapshot.md) 已分别留固定工程证据。本片补的是**继续执行前，核对保存时的许可与入口此刻重新提供的许可**。它不授予新权限，不恢复全部执行现场，不构成跨进程自动续跑许可。

固定6b70的新22项撤保护、旧四组及全仓工程检查通过。金融未push、未合main、未部署；没有生产kill/restart、付费模型请求、独立复核或质量对照。实施枝仅以ff-only收入本任务隔离补丁枝 `fix/runtime-authority-pc-0918`，不是合main；补丁树保留，无需重做该修复。

## 按发现顺序

1. 预算可以还原，不代表权限可以沿用。原configure是诊断摘要，缺完整材料合同、当前policy和实际装配工具声明；把保存的摘要反解成当前context，会形成“磁盘数据给自己重新授权”。新增独立schema v1的 `EpisodeAuthorizationSnapshot`，复用领域parser后再做规范JSON精确往返，拒绝默认补全、类型强转和未知字段丢弃。
2. 快照保存完整任务合同（含显式material_contract）、当前policy、information_cutoff、trace_parent_id，以及按当前context授权后的真实registry数据声明。含read_scope、工具capability/IO/replay/query_scope/参数/产出/最小窗口等，规范排序并保存SHA256；不序列化runner/parser闭包。`EpisodeState`深冻结，导出深复制。
3. `_EpisodeLedger`在 `_with_episode_bound_tools` 后保存实际registry；修复续轮跟随合同降级与registry重绑刷新。动态sub_research因此在父快照中、但不出现在子权限中。source存在而registry或快照缺失、编码/校验失败都通过每树共享fence阻新效果，不能省略字段装成durable。
4. `restore_episode(..., context=...)`及Episode静态入口增加当前context。所有非终态恢复须snapshot/context/registry齐全，在 `_Synthesizer` 创建、任何补写之前核任务及事件身份、再精确匹配当前许可。权限收紧或声明改变也拒绝；过期/取消闭合不绕门，材料边界未决亦拒绝。plan/closed保留原授权和原预算捕获位置。一致terminal只读查询保留，关联树仍拒恢复。
5. 曾考虑保留“旧日志缺授权就绕过”兼容，但缺快照无法区分真旧格式与损坏的新日志，撤掉该旁路。旧日志仍可load诊断，不得非终态续跑；当前context也不能从saved payload解码自证。
6. 格式与漂移测试之后增加承重反例：恶意registry声明**重算摘要**仍必须被scope/能力/IO语义门拒绝；完整材料questions/premise_marks/source_turn和EvidencePlan理由须往返；9格planning/tools_pending/done×raise/missing/invalid压保存故障与整树fence。tuple与list直接比较的两项假红改为同格式 `to_dict()`，不修改产品合同。
7. PLAN子研究反例先红：升档决定后、新授权尚未保存，child已调用一次；首轮2F/1P。初修在mode promotion后立即 `put_state(phase="planning", context=promoted)`，失败路径父1/子0/工具0，确认成功才可启动子效果。先解决了确认顺序，但该写法还会丢执行位置，见下。
8. 首冻576d的新21项及旧四组变异、前端/E2E/registry均通过，**全仓11F/11674P/81S/2X**。11项全在 `test_research_harness.py`：旧fixture的 `query_scope="turn"` 从未属于生产 `Literal["query", "episode"]`。冻结现场不动，另开隔离补丁树，将默认及显式旧值改为原意对应的query；同类historical fixture一并修正。未扩大生产枚举、未放松授权校验。
9. 新增两个真实升档前缀反例（PLAN-only、PLAN+tool_calls）：在standard→deep实际保存点记录前state及事件，等活run结束后复制到独立crash store，用独立保留的当前context/registry恢复。**两格先红**：都给 `model_turn`，本应是 `interpret_turn` / `dispatch_tools`。原因正是初修把model_pending/turn-1抹成planning，跳过已收到的回复或待派工具。
10. 补丁6b70保留旧state的phase/reserved_ids/retry/cancel，只刷新授权、预算、截止和捕获前缀；仍在PLAN子效果前确认。缺原checkpoint直接拒绝。两格继续核turn-1，带工具时call-1，以及deep授权/24调用硬帽和此前无tool_request。增加第22项变异，把保位置的保存改回planning，两个反例重新变红。
11. 定向扩大回归701P/3S/1X后提交6b70，ff-only收入实施枝。重新冻结，全量期间树前后干净；新22项、旧P0/子/恢复/预算四组和全部工程叶子同revision验收，不借首轮或预算旧收据。

## 方案取舍

| 方案 | 评价 | 选择 |
|---|---|---|
| 用configure摘要或policy默认值重建许可 | 缺材料/实际工具声明，默认补全会掩盖损坏 | 否；独立版本完整快照 |
| 从快照构造当前context再比自己 | 保存事实被升级为授权来源 | 否；入口重新提供当前context/registry |
| 许可变化时自动合并、收窄或迁移 | 本片没有证明任务语义、材料边界和未决效果仍相容 | 否；保守精确匹配，人工/后续显式流程处理 |
| 旧格式缺快照继续执行 | 无法区分历史数据与新日志字段丢失 | 否；非终态fail closed，load诊断和一致终态只读保留 |
| 只保存最初菜单 | 漏掉动态子工具、升档或修复重绑定 | 否；捕当前真实装配，修复时刷新 |
| 把声明SHA当代码签名或用户认证 | runner闭包和用户绑定不在摘要中 | 否；摘要只验证声明一致性 |
| 编码异常省略授权、继续保存 | 产生合法外观的无授权checkpoint | 否；共享fence，私留已收结果、不回滚可见前缀 |
| 等下一父意图顺便保存升档 | PLAN子效果会先发生 | 否；新许可确认先于子效果 |
| 升档保存统一回到planning | 已收回合及待派调用身份被抹，恢复会多问模型或跳工具 | 否；配置更新与执行位置推进分开 |
| 接纳非法fixture枚举以“恢复兼容” | 把历史测试错误写进生产合同 | 否；改fixture合法query，门不放宽 |
| 现在直接消费ResumePlan | 入口身份/证据消息/单写者/未知效果对账未齐 | 否；下一片继续补现场 |

本片未另建金融词表或ADR：新增的是通用持久化格式与已有恢复合同的约束，完整备选在本快照；金融领域术语表不堆实现字段。

## 固定6b70工程证据

证据根：`~/.finance-runtime/reviews/runtime-contracts-6b70e540/`。精确被测树：`/Users/a77/fwp-wt-runtime-contracts-0918`；`start-status.txt`、`python-before.txt`、`python-after.txt`均为空。以下结论绑定6b70，不包含随后文档提交。

| 检查 | 结果 |
|---|---|
| Python全仓 | **11687P/81S/2X**，17 warnings，1172.28s，exit0 |
| Ruff | exit0 |
| 前端 | offline frozen-lockfile安装，lint/typecheck/test/build均exit0；**107P/8 files** |
| E2E | **34P/2S**，约1.5m，exit0；8893/8894隔离端口且显式RE06_E2E_URL |
| registry/crosswalk | parseability/check/backfill-tables/generate-views及crosswalk均exit0 |
| 字段/目录门 | `check_unread_fields.py`、`gen_runtime_catalog.py --check`均exit0 |
| 精确收据 | `~/.finance-runtime/test-receipts/20260918T154311Z-6b70e540.json` |
| 收据核验 | 七项通过；revision/目标树/解释器/版本/依赖指纹一致，dirty=false、dirty_total=0、未绕依赖门 |

解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python3.12.13，依赖指纹 `3328bed61f3e21ea`。本机Node26/pnpm10.12.1，不外推为Linux/Node22等平台证据。17 warnings的具体原件保留，不称无警告。

### 撤保护（作者工程反证，不是独立审查）

复用已提交 `scripts/review_probes/run_extraction_mutations.py`，每组在固定6b70的独占临时树运行；不复制runner家族。

| 定义 / 证据子目录 | 项数 | baseline / restored-full |
|---|---:|---|
| `episode_authorization_mutations.json` / `authorization-mutations/` | 22 | 各89P，仅单文件 |
| `runtime_contract_mutations.json` / `p0-mutations-regression/` | 13 | 各167P，仅原三文件 |
| `sub_research_persistence_mutations.json` / `child-mutations-regression/` | 14 | 各67P，仅原三文件 |
| `restore_confirmation_mutations.json` / `restore-mutations-regression/` | 7 | 各32P，仅原两文件 |
| `root_budget_snapshot_mutations.json` / `budget-mutations-regression/` | 17 | 各61P，仅单文件 |

五组均 `complete=true`、`final_status=""`；每项red实际执行非空、exit1、有失败、errors/skips=0，还原green及前后所选集exit0；文件 `before_sha256 == restored_sha256 != mutated_sha256`。所选测试相互重叠，**不能加总，也不是全仓计数**。

22项覆盖：领域格式严格往返、policy确切类型与有限非负值、registry scope/IO/能力/摘要、当前许可精确匹配、未决材料、深冻结、实际装配registry、缺快照与编码共享fence、repair刷新、升档前确认、升档保执行位置、legacy/current输入门、验证接线、事件身份、plan/closed保授权。定义中有精确锚点和测试选择，不在快照抄第二套参数。

检查red时保留两个语义差别：P0 `tool_intent_fence`显式 `pytest.fail("unpersisted intent reached executor")` 是有效执行针；`nonstream_finish_reason`在 `assert result["_finish_reason"] == "length"` 处因必需字段丢失而KeyError，是实际运行时数据丢失，不是collection错误。补充核验脚本最初只接受AssertionError式消息，错误拒绝后一项；`mutation-verification-first-incomplete.log`保留，读原日志后按该精确字段断言核验，最终见 `mutation-verification.log`。未修改产品或测试去洗红，不能用“消息中有assert”充当通用语义裁决。

## 首红与局部读数

首冻证据 `~/.finance-runtime/reviews/runtime-contracts-576d4764/`，精确失败收据 `20260918T145722Z-576d4764.json`：11F/11674P/81S/2X、17 warnings、791.07s。五组变异及非Python工程叶子通过，但不能据此宣布那一版整体通过。

开发日志已归档最终证据根 `prefreeze/`（前缀 `runtime-contracts-authorization-`）：

| 日志 | 事实与归因 |
|---|---|
| `initial-red.log` | 新模块缺席，1 collection error；开发起点，不是变异红证据 |
| `wiring-red.log` | 63F；local_only夹具错误把外部能力当本地能力，修fixture、不改权限门 |
| `wiring-red2.log` | 16F/47P，初始接线尚未完成 |
| `wiring-first.log` | 14F/160P，旧恢复调用缺当前authority等，保原件 |
| `wide.log` / `strict.log` | 2F/460P/3S/1X → 462P/3S/1X；两条race漏传当前authority |
| `seams.log` / `seams2.log` | tuple/list假红2F/217P/3S/1X；同格式比较后单文件84P |
| `plan-red.log` | 真保存顺序漏洞2F/1P，child先于授权确认执行 |
| `prefreeze.log` | 120秒超时，无最终结论，不折算失败数 |
| `prefreeze2.log` | 618P/3S/1X，55.98s，dirty局部 |
| `final-focused.log` | 授权/恢复保存定向105P，1.40s，非全仓 |
| `harness-red.log` | 隔离补丁树复现11F/33P，非法query_scope夹具 |
| `pc-red.log` | 真执行位置两格2F/87 deselected，0.36s；预期interpret/dispatch却得model_turn |
| `pc-green.log` | 扩大回归701P/3S/1X，23.61s；仍是dirty局部 |

701P局部收据 `20260918T152132Z-576d4764.json`，两格首红收据 `20260918T151952Z-576d4764.json`；只能说明当时工作树，不能替6b70完整验收。各局部读数重叠、不加总。

旧e336093e的provenance全量首红根因仍未定位；同版9P及后续全量绿不是对应产品修复，继续保留该限制。

## 沉淀与跨仓状态

- 产品门页已随代码说明完整授权重验和升档不抹位置；本快照、执行计划完成标记及≤3K inflight在验收后回写。
- 工具包独立枝 `docs/runtime-contracts-0918@8e5d4fe`：BUILD/KIT/TOOLKIT沉淀“保存旧许可不是新许可”“刷新配置不推进程序位置”，登记22项/89P及真前缀首红；未合main。编辑前核独占树干净、对gitea/main落后0，未碰共享主树脏文件。
- 脚本盘点：核心撤保护执行已复用仓内runner，新增的是定义及正式测试，无临时产品脚本待搬。补充失败消息复核暂留审计手法：判断是合同字段丢失、夹具错误还是导入故障需要阅读断言上下文，简单字符串门已被本次KeyError反证，不能将它包装成无误判工具。
- vault能力图谱原行、doing行和一行交接由自动同步 **`ea51078998e63579a9e7300a132ac4ad3786ccec`** 收录。手工pathspec提交时已无变化，因此没有第二个手工提交；没有手工push，不把自动同步归功于手工发布。其后其他自动同步提交不属于本任务。
- 本片同窗vault lint前后均 **20 errors / 17 warnings**，错误集合无新增/移除；graph从81行/197断言/146在途到81/198/147，通过。日志在证据根 `runtime-contracts-authorization-{vault,graph}-{before,after}.log`。不修受保护作者枚举/TOOLKIT镜像或别人的死链；graph通过不等vault全绿，符号存在不等本候选行为已合。

## 下一步与不能外推的结论

1. **补完整恢复现场**：入口用户/授权绑定，任务输入、证据E号/owner/日期/原件，QueryLedger去重及缓存准入，Inbox正文/目标/身份/回执，原绝对截止及取消。授权快照不是完整ResearchRunContext，也不是用户/代码签名。
2. **再做执行所有权与对账**：跨进程单写者/重复启动门、父子共享预算、未知在飞效果与费用对账，之后才由同一loop消费ResumePlan。进程内唯一根不等跨进程lease；只读恢复的零写竞态测试不证明合成写入路径可与活drive并发。
3. **只在临时目录做真实进程中断验收**：验证已确认工作不重做、预算不重置、消息不丢。当前测试复制真实checkpoint前缀，不是kill/restart验收，也未恢复完整PLAN continuation现场。
4. **原计划继续**：压缩原件E号回读、Workbench next_step/next_turn与wakeup、P2逐工具重放/并行安全/独占声明。保持能力/IO限制、父子共享预算、深度1与子研究无发布权，不开放任意shell/写库/下单。
5. **不把保存位置当事务水位**：日志、效果、费用、checkpoint仍可能跨崩溃窗。没有结果不等没执行/没计费；补interrupted、授权匹配、budget位置相等都不是重试许可。ACK丢失不回滚可见前缀，一致done也不证明上次ACK或公开送达。
6. **证据分账**：本片只签作者固定工程合同，不签外部exactly-once、SDK等价、完整费用现场、独立审查、研究质量提升、合main或上线。GLM真实验收可按09-18最新模型前提另组织，不能把旧GPT凭据限制当全局阻塞；本片没有做付费验收。
