# 日期承接、数据消费者与结构减法接续 — 2026-10-07

## 背景与范围

A仍是逐张合入现有优化、部署并验收；B仍是提高真实回答质量，不以同步准备、测试数或可用工具数替代。
本轮只在独占review树维护取证/测试/文档，在sync树读取固定候选。没有改owner产品、合并、部署、生产写库、
删除或真实模型请求。等待#50单次许可不阻止B；历史凭据风险独立跟踪，不恢复为同步/推送的无限前置。
本快照承接[检查层取证](2026-10-07-ab-scope-and-check-layer.md)；旧快照里的#62红和数据“未实读”已过时。

## 按发现顺序

1. #62从8d61更新fd20，已迁移过时部署文档消费者测试，准确候选独立70P；#66的0703独立452P。
   两者均定向。首次在review树校候选收据因当前revision不符失败；移到准确sync树重校通过，未因此重跑测试。
   原checker把定向写“未收窄”的断言仍错误；#51独立scope逻辑明确四/六目标均收窄。
2. #66日期范围从裸日期集合升级为区间/边界，仍未区分显式含/不含当日。先看parser，再用真实登记原件加载器复现。
   第三fixture修正为“起（含当日）→之后（不含当日）”，使源证据本来就在源范围内；初版留存不改写。
3. 一次日期探针与本会话切换同一sync树并行，导入`query_time_scope`失败。失败目录02保留，归因审查方竞争，
   不是产品缺函数。停止换树，03顺序完成；04再使用真实context截止调用`PriorTurnEvidence.admitted()`。
4. canonical物理目录审计和两份夜跑plist配置审计已执行。物理审计提示的派生字段不能据此判工具坏，
   因而再通过真实`FinanceQuery.run`执行五组查询，并另外核估值/换手率覆盖和克隆形状规则。
5. 日期反例已发[评论6031265664](https://github.com/moscrol/finance/pull/66#issuecomment-6031265664)并GET回读。
   晚期outlook否定误删此前在[评论6030816919](https://github.com/moscrol/finance/pull/66#issuecomment-6030816919)交付；两个断点分账。
6. 取证固化提交`6b591e592c20913040f4093cb5aa79ed41107909`：新增
   `scripts/review_probes/prior_evidence_boundary_review.py`和15项取证前置/输出安全测试；
   比较草案补两模型档工作量及独立角色边界。干净树151P/4.59s、7目标，仍非全量。
7. 13:25平台回读#66已到`3f0cc758a7af2f55671688eb03b0573ffec536a4`。与0703仅一份handoff的5增3删；
   产品7份hash一致。独占sync树顺序切换并用同一探针重验，两个错误接纳和两个控制不变。
8. 读owner更新正文和私有`answer-quality-closeout-1007/simplification-audit-20261007/REPORT.md`：
   下一片优先撤系统分类附加必填义务，复用10-02 model-owned spec；日期实验270d未采纳，不继续堆词面补丁。
   本会话据此修订协作计划，反例保留为输入范围/保稿验收条件，不规定owner必须采用词表修复。
9. 13:32发结构协作评论前的head断言发现又更新，发送被拦、未产生评论。回读f03d9a97e仅再改handoff：
   owner记录用户再次明确要比Pi更全面，供给有效视角/证据/反证并检查重要遗漏，不能因Pi没有就删总览/主线/风险。
   因此四项→两项只作消融，不是产品目标；本会话已更正草案/交接和对用户说明。未在f03新跑日期探针，3f收据不移签。

## 日期反例：证明到哪一层

合成原件：现有`test_prior_evidence._source`登记真实RunStore/Episode，本地finance_query的09-14观察，
上涨家数3126为fixture，不是生产行情。调用`decide_turn(no_llm)`→`build_episode_context`→
`load_previous_evidence`→`.admitted()`；没有HTTP、自然模型或`_seed_prior_evidence`执行。

| 原范围 → 复核范围 | loader / admitted实测 |
|---|---|
| 截至09-14（含当日）→09-14之前（不含当日） | 均归before/09-14，返回09-14原件及observation |
| 相同截至含当日范围 | 正常接纳控制 |
| 09-14起（含当日）→09-14之后（不含当日） | 均归after/09-14，返回09-14原件及observation |
| 截至09-14→截至09-13 | 正常拒绝：unchanged date scope |

错误承接的context cutoff=10-07、source cutoff=09-18；上界筛选无法替代排除09-14的窗口合同。
材料仍`material_only`、allowed_capabilities=[]，未恢复新读权限。只能签输入筛选接缝，不能升级为最终答案污染。
两个准确候选各4份新隔离SQLite、27次连接；网络/DuckDB/其他SQLite禁止且越界尝试0，真实模型0。
前后HEAD/clean、7源码hash和probe hash稳定。脚本守卫不是OS沙箱，也不否认隔离SQLite写入。

复跑方式（替换占位路径，输出必须不存在且在两棵源码树外；执行期间不checkout）：

```bash
<生产venv>/bin/python scripts/review_probes/prior_evidence_boundary_review.py \
  --checkout <固定候选根> --revision <完整40位SHA> --output <全新私有输出目录>
```

测试只守测量合同，不断言错误日期必须接纳。capture exit0表示取证完成，不是产品通过。

## 数据消费者：新实读与剩余风险

准确review `df9552c742c52c79709e471793ac81f3a4e4c49e`、生产Python、canonical只读，观察04:55:07Z。
五个`FinanceQuery.run`使用截止2026-09-30，实际返回如下：

| 查询 | 实测 | 能说到哪里 |
|---|---|---|
| market_breadth_daily / 09-30 | 上涨2568、下跌2821、平170；本地观察5559、有效5559、缺收益0 | SQL聚合可用；不保证证券全集或供应商真值 |
| stock_daily / turnover+turnover_est / limit3 | 原值3/3缺失且明示降级，推算值返回 | 未补零、未自动替原值；另查全日原值0/5559，推算5531/5559 |
| global_index_daily / 09-30 | 5行 | 此切片可查询，不等于隔夜PIT正确 |
| global_stock_daily / 09-30 | 194行 | 同上；当前切片全部session_date=09-30 |
| stock_valuation_hithink / 09-28—09-30 | 90行，47只、3个采集日 | 采集日观察，不是五年估值或历史收盘定值 |

两海外表最新09-30，旧09-02落后叙述不能继续当现状。按真实`_stale_clone_pairs`截至09-30重查，
两表均flagged_rows=0、flagged_days=0；该规则仅识别“收盘/非零涨幅相同但源会话换日”，
零命中不证明供应商正确、历史已修或PIT通过，不能移用旧187/71、1944/14。
**时点仍有实质待验点**：两查询都返回trade_date=session_date=09-30；美股当地D日收盘在北京D+1，
因此仅检查日期≤A股日不能证明9月30日A股时段已知。当前日期级cutoff没有把这个问题验掉。
不据此改库或抓数；需先明确“截至当日何时”及现有映射/可知时间消费者。

6次DuckDB连接均唯一canonical且read_only=True；socket、SQLite和其他库禁止，越界0。
DB前后device/inode/size/mtime相同（3879743488bytes），这是元数据证明，不是全库hash。
所选投影可编译执行和返回不等于自然模型会选工具、HTTP答案正确、来源真实或PIT通过。

### 物理审计的七组提示逐项分类

72关系；56 fact/feature＝39语义＋17豁免；未登记0、登记但不存在0。exit1表示requires_attention，未自动修库。
以下非空数均针对**各表最新日期切片**，不能推成全历史都空。

| 关系（最新日均09-30） | 最新行数 | 提示与解释 |
|---|---:|---|
| fact_core_stock_daily | 50 | fund_flow_today全空；其他指标并非全空 |
| fact_leader_height_daily | 1 | fd_amount全空；不补0 |
| fact_mainline_sector_daily | 68 | 八暴露指标全空，只有名单不能证明量价/强度；local writer只插名单列与此相容，不据源码断言该次实际执行 |
| fact_sector_stock_daily | 52747 | fund_flow_1d/fund_flow_5d全空；其他指标仍有值 |
| fact_stock_daily | 5559 | turnover全空是真缺值；7项missing_registered_columns为breadth聚合/turnover_est投影，本轮真入口已验证，不能叫物理损坏 |
| fact_stock_high_daily | 295 | fund_today/market_cap全空；其余并非全空 |
| fact_theme_limit_stock_daily | 408 | circ_mv/fund_flow_1d/open_times全空；其余并非全空 |

空表：top_gainers/high_volume_gainers显式no_writer；stock_technical_snapshot为intentional_empty；
polymarket_macro_odds_daily为candidate豁免。空配置表不自动认缺陷；feature_l2_capital_flow_daily的通用语义合同待验，
不忽略既有D9消费者。这里只分类观察，不替来源owner签“所有缺值均合理”。

较旧数据：auction_stock_daily、dragon_seat/summary/tiger_daily和historical_mapping末日09-02；
event_daily最大event_date=09-03，regulation_event/pool最大effective_date=09-02；
sector_constituent_hithink采集日09-08。事件生效日/名单采集日不等于每日行情新鲜度，不能一律标停更；
这些消费者尚未本轮自然验收，不拿新海外末日覆盖它们。

### 夜跑配置审计不是执行证明

04:37:48Z两份sync/finalize plist均checks_passed/local，配置根`ffe1c60d84da1c36e3e5d27a53f3ecf43536905b`；
预期review为df9552c，两者**版本不同**，只是pipeline SHA相同。六表09-30行数分别5560/854/79/66/30/5584
（stock_hithink/sector_kline/limit_pool/dragon_tiger/hot_rank/auction）。plist前后hash、DB元数据未变。
没有运行launchctl/pipeline，没有另加与消费者探针相同的socket计数守卫；不能借其他探针的0尝试移签。
配置不是已加载launchd、步骤声明不是执行、行数不是字段完整性；新外盘写入步骤接线与G1–G8授权仍未完成。

## 结构片、C1与新留出分账

owner在3f曾优先提撤“系统推导→用户必答”；f03随后明确**保留有增益的覆盖职责**，删重复决策、僵硬套版与误伤交付。
四项→两项投影只作消融，不是产品目标或收益；相对Pi必须考察新增相关视角/有效证据/反证及重要遗漏，不比篇幅/章节数。
合并controller语义调用、覆盖职责调整与正文二次作者处置分别对照，不将三件事合成单因素结论。
本文[C1比较草案](../verification/2026-10-07-answer-check-comparison-draft.md)仍DRAFT，C1尚不存在；
后续若执行，C0/C1须共享同一义务语义，仅改变检查处置，不暗中增加第四臂。

24题/28轮仅配额，独立输入/gold尚未创建。144会话/168回合/288成对呈现是**每模型档**；
若两档完整各跑合计288/336/576，不是物理调用/费用帽。弱强档分别证明质量获益，不能混分或只证不退化；
不解除历史暂缓强模型、旧240批或取消12题。题作者/复算/运行/映射/盲评身份与挂载未冻结，本会话不兼任未见真值组。

## 决策与被否方案

| 选择 | 被否方案 | 理由 |
|---|---|---|
| 保反例、服从单owner结构片顺序 | 催逐词修日期或另造竞争核验器 | 缺陷事实不规定修法；减少重复语义重算才可能解决同类问题 |
| loader/admitted与episode seed、HTTP分层 | 因下游会调用就宣称最终污染 | 源码路径不是自然执行收据 |
| 同树checkout与运行串行 | 只在开头验HEAD就并行切树 | 中间文件变化可导致混合源码导入，02已实证 |
| 物理缺列后验真实语义消费者 | 把派生字段报错当查询不可用 | 编译层可能按需投影，breadth/turnover_est已有证明 |
| NULL保留并解释覆盖 | 补0/自动换源/按最新行数签完整 | 会更改金融含义并掩盖来源缺口 |
| 结构片与C1分别冻结 | 把所有减法打包成“无harness” | 变量混杂，无法判净收益与回退点 |
| 以有据增量视角/反证验全面性 | 把Pi的两项投影当产品终态，或奖励更多固定章节 | 比Pi更全面须有内容收益，减法不是目标本身 |

## 收据、协作与下一步

私有证据根`~/.finance-runtime/reviews/release-resume-20261007/`，不上传原始账号/事件定位：

- `pr62-fd20a3e-scoped.json/.log`：70P/53.56s；`pr66-0703ffae-scoped.json/.log`：452P/2.89s。
- 各`identity-correct-tree.txt`通过；错误树校验原件保留，scope独审结果优先于旧checker措辞。
- `boundary-review-6b591e5-clean-pytest.json/.log`：151P/4.59s、collected151、0F/0E/0S/0X；生产Python3.12.13，
  依赖e1c50cb821a30f00，准确HEAD前后clean；7目标scope=false。收据SHA256=f29b21e715a4a394d45f5da337fc0816a3d0fe67706828d1f2117147cf752778。
- `boundary-review-dev-pytest.json`：dirty28P/2.06s，只是开发读数；15新增测试不固化缺陷。
- `pr66-0703-date-loader-clean-6b591e5/report.json`、`pr66-3f0cc75-date-loader-clean-6b591e5/report.json`：
  两准确头各自完成，不从hash相同直接移签；probe SHA046eab9ca09b9dba9fe75fc42680fd7e31430b1baef13624520561cfd3e235aa。
- `data-audit-01/consumption.json`及receipt、`hithink-configured-runtime.json`、`data-consumers-01/report.json`为原件；
  `data-attention-summary-1330.json`为原件派生阅读视图，不是新的DB取证。
- `platform-before-boundary-push.json`观察13:25：main仍ea217633ceeaceeb41d3b3f30fa58708fe14ecc9/protected；
  #50@570142、#62@fd20、#67@df955五绿；#66@3f0cc75三叶绿/python进行中，聚合尚无结论。旧0703五绿不移签。
- `pr66-3f0cc75-followup.patch`、`pr66-post3f-followup.patch`均仅handoff；13:32最新f03d9a97e80d08383470324934ac05a28f8ed2fc
  仍Draft，registry/frontend绿、python/e2e当时进行中；当前状态另看`pr66-coordination-head-drift.json`。
  owner自述0703完整21133P/76S/2X，本会话尚未独立核原收据，不能写成本会话全量。
- `boundary-review-6b591e5-delta-summary.json`：ea217..6b新增可达历史默认规则0命中，不清除继承历史风险。
- `code-map-6b591e5-query.json`：ready、vault unavailable、structure ok、doors/narrative missing、recall untested；地图命中不签生产调用。
- FINANCEWORKS-1/-6已评论并回读，ID分别0c8d0290-3a96-4304-aad1-b2052063529c、3e72815c-de49-494e-9e1d-47df0655eca1，
  当时签12:55快照；后续#66新头/结构方向另更新，不改owner/status。

后续：同步本分支新头及当前检查；协调#66结构片与晚期门后续边界，不抢实现。#50@570142仍待单次许可，
每次main前进重新同步/验收；#63/#67邻接冲突、#30重合成、收据cwd缺口另账。最终main全量/本机前端E2E/
两档真实质量/批准部署/切后任务与回滚/备份仍未完成。磁盘18GiB可用，未经点名许可不删失败目录或门禁现场。
工具沉淀：重复日期排查已归仓内脚本与前置测试；既有数据审计工具复用，不新增通用审计平台。
共享harness-reference仍脏且落后，未写其树；门禁cwd缺口已记录但本片未承接，不伪称已经补齐。
