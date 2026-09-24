# 2026-09-16/17 local 复盘恢复与分层验收

记录于 2026-09-17。**两日复盘主链已恢复；不等于后续自动夜跑部署、方法前向实验或真实模型会话验收完成。**

## 背景与归属

09-15 另一会话从旧数据树推断机器不支持 local，把两个装机任务的 `REVIEW_SYNC_PLAN` 改成 auto。09-17 18:30 实际选 cheap，在复盘会/CDP 预检失败；staging 未发布。20:40 finalize 下载了 L2 日包，但股票行情缺失使 top100=0，L2/报告守卫继续失败。修复方向是恢复配置和日期化行情，不是重新登录已风控停抓的复盘会。

- 数据根：`/Users/a77/finance-workspace-private`，detached `b4a35fa2`，有他人文件和运行产物，本轮不整理/提交。
- 修复树：`/Users/a77/fwp-wt-nightly-review-0917`，`fix/nightly-review-0917`，基于 `gitea/main@0a1cb8c4`；代码终点 `5204bb32`。
- 实际同步树：`/Users/a77/finance-workspace-sync@6382c13b`；只覆盖指数防回退模块。
- L2 冻结根：`/Users/a77/.finance-runtime/finance-l2-d433b90788c0`，保留原装机根。
- 一次性生成根：`/Users/a77/fwp-wt-generation-root-guards-validation@387028b8`；没有部署该分支。
- 证据根（下称 RUN）：`/Users/a77/.finance-runtime/review-recovery-20260917/`。

## 发现顺序与决定

| 发现/方案 | 选择 | 否决及理由 |
|---|---|---|
| 模板本来 local，装机与生效环境为 auto | 备份后只改两个 plist 的目标变量，bootout/bootstrap，并比对模板/装机/launchctl 三态 | 不整份回滚 plist，避免倒退 L2 根；不凭旧 checkout 宣称能力不存在 |
| local 指数模块仍可隐式请求复盘会 | 参数与环境双边界拒绝 fallback；实际同步树最小覆盖该模块，验证主源空时 fallback 调用0次 | 不因跳过登录预检就宣称没有外呼；不整体替换运行树 |
| 历史日不能直接跑今天快照 | 09-17东财原始响应固定日期；09-16逐股取真实日期化Sina历史，再staging恢复 | 不改快照日期、不用 allow_misdated、不手写生产SQL补数 |
| 续抓缺身份且原始快照含空价占位 | 仅借后日正有限价行的身份；续抓保留已有有效行 | 不把后日价格当历史价格，不把退市/未上市占位当活跃全集 |
| 无前一根bar的两只IPO | 核对精确上市日和发行价，保留来源；恢复历史N名 | 不把一切无前收当IPO，不用后日收盘假造前收 |
| 689009.SH普通接口报JSON错误 | CDR专用历史API，独立source，缺turnover留NULL | 不强套普通A股API或补零 |
| 底表补回CDR，已success板块仍缺11条成分 | 恢复在staging显式 `--include-completed`，复用原代际writer，09-16→17顺序重算 | 不把旧success/rc=0视为输入未变；不另建删除/写入链，不修改常规默认skip |
| 历史拼接会拉今天腾讯市值 | 09-16始终 `--no-caps` | 不把现值市值混入历史 |
| 旧finalize存在生成代码/数据根错配 | 固定387028b8 launcher与canonical数据根，用户态保持外置 | 不把一次性成功当正式部署，不扩大L2变更范围 |
| agent-daily先于整轮summary落盘 | 整轮PASS后从agent-daily正式刷新，另存post-recovery摘要 | 不手删“仅作预览”警告，不覆盖原收据来伪装首次完整 |
| 方法daily rc=0但capture refused | 保留旧协议，记录v3/v6不兼容与拒绝 | 不改旧协议、不回拨时钟、不宣称登记了前向观察 |
| L3只有滚动days、无历史as-of | 只查09-17，dry-run；09-16不混入未来证据 | 不apply他人脏知识库，不把无公司回答的提问当公司事实 |

## 代码提交与生产动作

代码依次：`679007b3`（指数边界/受控恢复）、`5c04d5da`（身份续抓）、`307701d3`（IPO）、`8709ad7a`（CDR/身份过滤）、`5204bb32`（已完成成分刷新）。未push/合并。

`recover_local_review.py` 复用 `run_daily_full_staged()`：旧夜跑目录锁、数据库mutex、child限定 `.staging` 与run_id、两日质量/跨日/基线检查、成功状态绑定run_id、换库前可读备份。先装09-17股票作历史次日锚，再按日派生。原失败staging另存取证，不恢复退役链。

三轮均 `swapped=true, rc=0`，每轮备份都保留在数据根 `db/`：

| 收据 | run_id | 备份后缀 |
|---|---|---|
| `recovery-receipt.json` | `3e92a484e7a4` | `.bak-20260917T214501-3e92a484e7a4` |
| `recovery-cdr-receipt.json` | `6ed28b9c7542` | `.bak-20260917T215303-6ed28b9c7542` |
| `recovery-final-receipt.json` | `cca104bedc85` | `.bak-20260917T215917-cca104bedc85` |

最终备份3676319744 bytes、66表只读可打开，SHA256 `a855e472ca97f46a7f533f3388d51d3909fb31facb47338d95ccd3ce91ed6e4d`。这是第三轮换库前状态，不是最初故障库。回滚需先协调全部读写者、校验对应收据，不能随手复制或清WAL。

主管曾因刷新成分协调而暂停，21:59:42已恢复；finish与closeout均已结束、目录锁已释放。**不要照旧摘要再次SIGCONT、清锁或并行重跑。**

## 主链验收

| 项目 | 09-16 | 09-17 |
|---|---:|---:|
| 股票日线 | 5549 | 5553 |
| 板块日线 / 成分行 | 403 / 52748 | 403 / 52769 |
| CDR成分 | 11条、价额非空 | 11条、价额非空 |
| local数据/报告/L2总门 | COMPLETE | COMPLETE |
| 跨日门 | PASS | PASS |
| limitup处理/失败 | 33/0 | 89/0 |
| top100处理/失败 | 100/0 | 100/0 |
| quant处理/失败、结果数 | 100/0、60 | 100/0、43 |
| 首次生成 | 19步骤PASS | 19步骤PASS |
| 队列刷新 | 10步骤PASS | 10步骤PASS |

口径：`--phase all --plan local` 查19/20张事实/特征表，**不是full计划全部表**；没有L2暂停/全空豁免。量化簇结果60/43不是漏处理，分母均为100个候选。

额外只读验证（不靠rc或行数替代依赖验证）：
- 两日各403板块：成员合计金额、相邻日边际变化、适用等权涨幅，与日表一致；0不匹配。证据 `derived-consistency-verified.log`。
- 两日L2实际股票集合与当前canonical候选集合一致；涨幅按真实writer的 `round(pct_chg, 2)` 一致；quant是top100子集。证据 `l2-input-consistency-rounded.log`。无需force-rescan。
- 09-17唯一空amount：`688496.SH *ST清越`（close=0.58、pct=0，volume亦NULL），保留缺口，不填0。
- 09-16前收链5547可比、0不符；次日锚5549可比、22不符；收益/量纲检查0异常。历史除权除息口径差异保留。
- 最终快照22:03:23发布，requested/served/source_data_date均09-17，provider=duckdb_exact、quality=complete、fresh。
- 22:22:20真实8792 `/api/readiness`：ready；market_database与snapshot均09-17且consistent。此证明服务读到新鲜数据，不是模型问答验收。

全股票sum(amount)为18521.3932/18362.6209亿元；市场表total_amount为18386.22/18227.57亿元。两者分母不同，不混写。

## 产物及不可变证据

两日 `复盘/daily/<D>/<D>-daily-review.html`、daily-review JSON/Markdown/MA5 PNG、题材候选、研究队列、策略一/三/四矩阵、工作台与 `复盘/index.html` 均产出；报告JSON日期正确、warnings为空，HTML/矩阵有目标日，PNG签名与实物非空已验。未做真人浏览器视觉验收；策略一仍是机械初稿待人工复核。

队列刷新后market_review ledger为PASS/missing=0，过期“先补齐daily workflow”提示消失。晨汇WARN仍真实存在，是有源才跑的旁支，不伪造补齐。KB本轮刷新接收文件为：
`/Users/a77/knowledge-base-private/wiki/raw/cross-repo-ingest-queue/<D>/<D>-kb-ingest-queue-2.json`，分别7/9个任务；只received，不等于apply。语义RAG本轮关闭，不以接收成功宣称检索/知识质量通过。

**共享产物会被后来任务覆盖**：收尾观察到09-17 canonical workflow summary已变为22:34:35–22:37:04的新一轮，KB也多出queue-3；不认领该轮。已从本轮独立日志抽取完整原摘要：
- `generation-2026-09-16-summary-frozen.json`：22:00:31–22:01:55。
- `generation-2026-09-17-summary-frozen.json`：22:01:56–22:03:23。
- `agent-refresh-<D>-summary-frozen.json`：22:21:54–22:22:17范围内。

`closeout-evidence-manifest.json` 哈希绑定上述原摘要、质量门、发布/配置收据、当前实物与知识库本轮接收文件。现场日志/大库不提交Git。

## 旧方案对齐能证明什么

只读对账08-14至09-02的14个干净交易日，10类指标全部达到既定阈值：成交额/量能三项/前三行业顺序14/14；涨家数13/14在±10内；逐板块涨停数一致97.9%，明细召回99.7%；连板181条、龙头高度14日全部一致。核心成交额前50历史覆盖20213/20250（405日），未命中37条均缺日线。

**达阈值不是完全复刻**：跌停只有85.7%交易日在±6内（门80%）；08-17涨家数复盘会4248、自算4334；20日新高数量相对误差中位11.8%；强度状态13/14一致。local还沿用最近真实成员身份，缺官方板块payload时涨幅为等权均值；主线/阶段是自家框架推断。旧资金流1d/5d字段两日全NULL，L2不自动填充它们。没有完整网络审计，不能把已封住的指数fallback推广为全链绝无复盘会请求的证明。

## 旁支状态与剩余边界

1. 方法：active绑定unset（rc4为允许默认study的状态），daily重建labels/outcomes水位到09-17，capture因旧v3协议/当前v6标签拒绝；recheck=nothing_due。历史2个共同日不足min_n20，standing为降权观察，不出胜率。须另走新协议登记与active切换，不改旧实验。
2. L3：09-17例行池9只、agent代码缺口0，dry-run1候选，是300112投资者问MFC量产、无公司答复；未apply。09-16未执行无as-of的滚动查询。知识库有他人WIP/UU，不碰。
3. 框架checkpoint新建与回检是两批；manual/unverifiable不是命中。未验真实Workbench `run_turn`、模型网关响应或episode合同。
4. 装机两plan已local，指数最小覆盖已验；**已安装finalize仍用旧的生成调用，生成根正式修复未部署**。下一次无人值守成功尚待该独立部署及运行验收。
5. 本枝无全仓pytest/前端/E2E/registry四叶验收、无独立QC，不满足合并凭证；用户未授权合main。既有pip依赖冲突未修，不推断与本路径无关即全环境健康。

## 测试、误诊与沉淀

- 5204bb32：全仓Ruff、diff检查、7文件定向114P；最新收据 `~/.finance-runtime/test-receipts/20260917T142352Z-5204bb32.json`，日志 `tests-closeout-5204bb32.log`。这不是全仓pytest。
- 将include_completed判断在独立进程内存中移除，刷新回归按预期1F；磁盘未改。恢复原实现定向重跑通过。`member-refresh-mutation.log` 的红是刻意反例，不是未修测试。
- 保留错误量具：首次派生诊断最后误用ts_code（正确stock_ts_code）；首次L2诊断忽略writer两位小数。这两次rc1均不算通过；分别有修正后的完整rc0收据，未调业务门槛。
- 可复用原则写入 agent-memory `gate-covers-only-its-return-value.md` 的“成功凭证必须绑定输入”；能力图谱/项目索引已回写，graph_audit rc0（其他分支UNVERIFIED不被本轮冒认）。原指数函数名早就存在，图谱改钉新增行为测试，防止符号存在被误读成修复已合。
- 可重用恢复逻辑与回归已进仓，不把runtime主管当第二条常驻链。一次性身份抽验/证据归档只留RUN；本次没有另造跨项目通用检查框架。KIT已有该方法论笔记索引；harness-reference/BUILD.md有他人782行删除WIP，本轮未改KIT/BUILD/TOOLKIT，若要抽通用工具另树处理。

## 接手顺序

1. 先看inflight和RUN不可变原摘要；不要从已覆盖的canonical摘要认领本轮结果。
2. 优先走生成根分支的独立复核/正式部署，保留L2根；同时另办方法协议版本迁移。
3. 本枝准备合并时按固定revision跑四叶本机门禁，取得用户确认；产物JSON、数据库/备份和他人改动不入提交。
4. 未来任何底行情修订都要证明受影响派生/候选已刷新；本次显式重建不是全链自动输入指纹机制。
