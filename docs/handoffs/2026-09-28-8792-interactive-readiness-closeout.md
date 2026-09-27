# 8792 交互进化收尾：代码、数据和部署验收

更新：2026-09-28，功能提交 `326aa553c571eeeb5342f091a9672a9a9993ac3c` 经 [PR #948](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/948) 快进合入并实际部署至 8792。其四叶门禁、两类独立复审、隔离六轮交互及生产查数均通过。收尾文档版本也须绑定自身检查后再发布，当前完整身份、收据与备份入口在 [final-release.json](/Users/a77/.finance-runtime/reviews/8792-readiness-20260927/final-release.json)，不能用本段的历史代码 SHA 冒充未来 main tip。

## 背景和授权

用户要求补齐 Claude 未收尾部分，整理并部署后开始交互进化；又明确要求个例从根因修，不能破坏通用能力。主代码树、KB 主树有其他人的在途状态，因此实现使用独立工作树，数据按 canonical 写入链恢复。最终候选已包含 Claude #877 的材料写手/判官设置、#945 的记忆缺口以及 #946 的主机睡眠观测；没有重做后两项，没有替用户启用语义判官或改全局模型预算。

以下证据均以 `E=/Users/a77/.finance-runtime/reviews/8792-readiness-20260927` 为根。长日志、真实 Episode 和失败探针留在本机 E；它们不是提交到 Git 的附件。这里记录观测范围，不声称每个金融回答均正确。

## 发现、修复与实际验收顺序

1. **持久学习根混用。** 学习 API 原先按代码根找台账，而 overview 按数据根找；代码快照切换会让两侧看到不同记录。现统一使用 `runtime_paths.finance_root`。两根隔离测试覆盖读取、批准、拒绝、规则状态和下一次消费；真实用户的旧 pending 候选未自动批准。
2. **个人纠偏写入和读取边界。** 明确纠正上一答才入账；去重检查与追加处于同一跨进程临界区。开场预取和显式工具采用同一有预算的投影，历史截止/缺日期/截断均可见，原台账不改。用户记忆不能为外部市场数字背书。
3. **KB 维护和消费根。** KB #158 已合入 `caaad20a`，完整维护门禁 911P；受管 generation `readiness-20260927-43430ddd` 的 manifest SHA256 为 `597487f23fb102894ad78627cbb8390e3a4ac977f552995602e9ecb329fe604e`。普通索引 168,920 块、全文 269,019 块；独立分母、四类过滤及回执实测（evidence_layer、fact_hardness、source_type、as_of；receipt 是回执而非第五类过滤）。完整只读资料根固定 `~/kb-wt-8792-readiness-0927/wiki`（43430ddd），仅 RAG 边界映射到封存代。查询前后复核加载身份，变化不被缓存掩盖。
4. **历史数据与消费者。** 09-21～09-24 L2 原包通过 `daily-full` staging 原子发布，父运行 `3a474fcfcb63`。累计资金记录 689 条、量化记录 190 条；历史流通市值/评分空值保持空值，不用现在的值补过去。09-22 星帅尔停牌用当日官方原件，休市日不造数据。正式资金流页面已更新并查看实际三标签页。研究队列使用 09-20 可追溯 KB 快照恢复四日，晨汇/IMA 缺档保留 WARN，未伪造全套夜跑 PASS。
5. **金融尾项回到生产者合同。** #78 原事实归因经冻结现场纠正：正的终点收益不能否定中途回调。#79 不把返回数量冒充候选全集。实际 query_basis 随执行结果交付，D10 标记交易日期限与累计终点；#80 按同日 published 板块全集核实体，历史码、未知目录和股票非闭集不误拦。42 日、16,926 日期×代码的真实只读核验误拦 0。新增自由文本关键词判断器因正常对照误伤而撤回。
6. **真实记忆演练进一步暴露合同错误。** 原件已经召回，纯回顾却被分入金融研究而缺必需行情槽。改为专用个人回顾合同，沿既有历史引用候选进入一次有界语义分类，保留金融问题原合同。完整原件绑定支持没有行内 E 的合法数字条件；显式错误 E、新数值/单位、错误 hash 不获得权限。
7. **最终质量复审两项 P2。** 文件锁等待原先会越过根截止/取消，改为非阻塞有界等待并在写前复核，去重原子性保留。混合研究中固定引言词表误删完整记忆引文，改为实际 prior_recall 绑定、原件身份与完整正文匹配；相邻金融断言不获得授权。5 个冻结探针（其中 4 个原先失败）原样全部通过，未改全局 claim splitter、parser、路由或预算。
8. **固定代码上线。** `326aa553c` 四叶通过、PR #948 快进后 main 保持同一 SHA。第一次 `launchctl bootstrap` exit 5，部署器恢复旧 launcher/软链并实际验证旧版 7a405e1b 健康；按运维规程等待 3 秒后重切成功。8792 readiness 全 true，health 三读 SHA 相同、clean、加载代码与仓库匹配，canonical 账本 homes 正常且无旧家。
9. **生产验证与夜跑安装。** `run_20260928_011332_274037` 经真实对话 Episode，19.665 秒完成；600584.SH 在 09-24 收盘 68.78、涨跌幅 -4.17%、成交额 37.5914 亿元，与只读 DuckDB 复算一致。`fact_stock_daily`、真实列名和数据日均在证据中，数据日等于库内 max，degrade/secret/public scan 0。18:30 sync 与20:40 finalize 四个装机文件哈希与仓内源一致，RunAtLoad=false、安装后 idle，未提前执行采集。

## 方案选择及被否理由

| 问题 | 采用 | 未采用与理由 |
|---|---|---|
| 个例金融措辞错误 | 真实指标/窗口/过滤/原件身份合同，配正常对照 | 扩充关键词或按答案形状拦截会误伤否定语境、历史码和合法引用 |
| 个人回顾缺金融证据 | 专用纯回顾合同，记忆仍只是用户先验 | 放松金融证据地板会让用户观点冒充市场事实 |
| 混合引用被删 | 完整实际绑定原件，显式 E 限定范围 | 引言动词白名单不能表示授权；把全部记忆数字并入事实池会越权 |
| 并发纠偏 | 同 inode 锁内去重追加，等待受根截止/取消约束 | 全局慢 IO 锁、锁外去重会分别拖住不相关请求或重复写入 |
| 代码切换后学习消失 | 原有 canonical 数据根 | 自动批准旧候选或复制多份台账都会制造另一事实源 |
| KB 脏树和双索引 | 独立固定资料树、受管 generation、查询身份复核 | 对脏主树重建、临时软链补封存代会破坏来源和索引一致性 |
| 历史数据缺列 | 保留空值与排序依据，按日核原件后原子发布 | 用即时流通市值补历史、拷昨天行改日期会制造假事实 |
| 模型偶发超时/文字越界 | 保留真实样本和限定结论 | 本次没有提高全局预算、偷偷开判官、同题反复抽样直到覆盖旧红 |

## 验证、旧失败与证据入口

- **最终代码完整门禁**：`gate-326aa553c/gate-HgUAhGdi/pytest.json`，18,362P / 0F / 72S / 2xf，收集18,436，未收窄；`check_test_receipt --require-full-scope --expect-revision <完整SHA> --base-drift-max 0` exit0。`frontend-326aa553c/frontend.json`：lint/typecheck/build0、125P、E2E34P/2S。`registry-326aa553c-receipt.json` 四项0。各收据均为相同干净 SHA；前后身份一致。
- **独立复审**：`memory-final-quality-followup-spec-review.md` 701P；`release-quality-final-review.md` 579P。覆盖有重叠，不把两个数字相加当作新增覆盖。原 `release-quality-review.md` 的6d HOLD、P2冻结脚本和基线对照保留。
- **六轮真实交互**：`live-326aa553c/receipt.json` 与 `live-326aa553c-manual-review.json`。纠正一次写入；跨会话带主题/无主题均完整召回；“连续3日未达标”保留；撤回后只有 user_memory_gap，partial 是预期如实缺口。使用隔离用户和独立 Episode store。
- **生产切换**：失败/回退 `deploy-326aa553c/`；成功 `deploy-326aa553c-retry/`；真实 API 收据 `prod-326aa553c-smoke.json`；独立只读数据库/证据核验 `prod-326aa553c-grounded-verification.json`。初始 health 收据中的 `grounded_probe_pending=true` 是该步骤当时状态，由后续独立探针收据完成，不回写冒充同步已验。
- **数据与任务**：`l2-recovery-parent.json`、`research-recovery-all.json`、`research-recovery-finalize.json`、`moneyflow-final-render-receipt.json`、`nightly-install-326aa553c/receipt.json`。正式资金流页面为主数据树 `复盘/moneyflow/index.html`。
- **旧候选**：98 的真实记忆失败、896 的全量中断和丢失数字条件、6d 的两次分类超时及两个 P2 均保留；旧全量红/中断不移签为通过。`candidate-98a7472a6-verdict.json`、`candidate-896b5f79c-verdict.json`、`candidate-6d9739535-verdict.json` 为当时裁决。

## 可以使用和仍有限制的部分

8792 已具备本轮验证的本地行情查数、受管知识检索、纠偏持久化、跨会话回顾和撤回退出；学习候选审批使用稳定数据根。交互进化指可追溯记忆、反馈和后续研究使用，不等于模型权重自动训练，也不等于候选规则自动生效。

实际查数曾在仅单日证据上额外写“放量大跌”，缺少比较数据。原样保留 `live-326aa553c-market-quality-note.json`，没有同题基线 A/B，不作新旧归属判断；生产这次答案未出现它，也不抹掉旧样本。judge off 下确定性核验不是全部自然语言语义认证。此前回顾分类 provider 8秒超时及30秒诊断样本见 `recall-provider-latency-note.md`，本次没有改变预算，N=1/N=2 不证明可靠性改善。

13个冲突 KB 页继续隔离，元数据警告未伪装消失；晨汇、部分 IMA/个股深读、卖方输入仍缺，canonical 卖方日期仍为07-05，未合的08-17材料不擅自提升。#75 的 endpoint_not_path 独立语义QC不在本次结案。下一次自然夜跑仍须看它自己的结果，本次安装成功不等于未来执行成功。

## 回滚和接手约束

当前 runtime、文档 PR、门禁和 Gitea 备份读 `E/final-release.json`；部署账本为 `~/.finance-runtime/deploy-ledger.jsonl`，端口8792。功能前回滚锚 `~/.finance-runtime/finance-workspace-7a405e1b096b`；原 launcher 位于 `E/deploy-326aa553c-retry/launcher.before`，受限权限保留，不要把内容贴入日志。运行版本切回仍按同一版本软链、launchd、实际 switch 账本和 health/readiness 流程执行。

保留完整 KB 读树 `~/kb-wt-8792-readiness-0927`、受管 generation、原L2包和 `.duckdb.bak-20260927T220312-3a474fcfcb63`。不在现用代码或封存索引目录 checkout/reset，不恢复退役双盲夜跑、不自动审批旧规则、不把测试纠偏写进实际用户。新问题从真实 Episode/原件的第一次偏离处定位，再决定补数据、改合同或修消费者。

## 工具沉淀盘点

可复用实现已归仓：纠偏有界锁、记忆投影/原件合同、KB消费身份、实体时态检查、真实query_basis、历史L2输入校验和夜跑读写根，均有正常与失败边界回归。部署、六轮和独立复算使用 E 内留证脚本；它们绑定本轮端口、用户、日期和批准的固定版本，不能直接提升成第二套生产写入/部署入口。通用经验归已有记忆纪律：判断权限看可验证原件和合同，功能检查与内容质量分别签收；没有新增重复能力清单。
