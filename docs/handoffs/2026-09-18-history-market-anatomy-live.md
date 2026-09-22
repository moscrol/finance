# 历史过程研究：两次真实失败、权限修复与固定版本收据

## 当前裁决与背景

用户要的不是「几个函数算得出」，而是同一段 Workbench 对话完成：市场阶段→历史参照→当时强势板块/股票→启动到峰值→接力→同口径特征。本次继续沿既有 Workbench/Episode/history_query/canonical DuckDB/RunStore 实施；原设计见 [09-17快照](2026-09-17-history-market-anatomy.md)。

固定运行代码 **`fbd8f2a656cf5618bef1791beaea74c354c70552`**，分支 `feat/history-market-anatomy`，独立树 `~/fwp-wt-history-market-anatomy`。**工程四叶通过，但第二次真实同会话四题整组仍失败；不是 merge-ready，不是部署资格。** 当前只封存这一节点，后续修复须新版本/新目录复验。

没有改生产行情库、每日复盘写入流程、用户视角/台账或历史标签库，没有补数。8792仍是 `bf662e9310ff…`；见新验证目录的生产health收据。首轮隔离发生EpisodeStore出口遗漏，下面明确记录，不能声称所有运行状态从未写共享目录。

## 按发现顺序

1. 初版506e1e23工程检查、手选真库查询已通过，然而真实第一组四题并未通过：来源误述、越截止、降级正文/规则误读，第四题崩溃。失败根为 `~/.finance-runtime/history-anatomy-live-20260917/`，保留原答与调用事件，不用后来重跑覆盖。
2. 最深错误不是网络：被冻结的工具参数含 `mappingproxy`，进展账的JSON序列化失败。摘要tool_calls=0遮住了此前成功的原件读取；durable事件仍能证实，不能据摘要抹掉局部成功。
3. 排查发现local历史工具接线、自然续问授权继承、范围与截止解析存在接缝问题；“如果窗口太短/如果要声称规律”等过程条件又被错标为虚构前提。用完整原始用户消息和可信合同恢复权限，而不是从旧助手正文猜。
4. 三个时间概念分开：总授权2026-01-01..09-15、当前观察/搜索窗、独立信息截止09-15。授权上界较晚也不得抬高信息截止。严格历史普通工具的未知/越界事实必须在交付前剔除，不以警告标签换取消费权。
5. 市场专属来源/单位接进finance_query；历史策略明确多板块同次同窗配对，源峰无需先回撤确认。此后真实模型仍误读这条规则，证明源码提示存在不是消费端正确的证据。
6. 补真实run_turn→controller、真实工具执行tripwire及整Episode rejected嵌套参数回归。临时库测试封网络/子进程/外部回退，库字节不变；它不是对live进程的OS网络隔离证明。
7. 扩独立算术为 `history-artifact-arithmetic-v2`：保存事实+冻结公式的第二实现，支持新特征、market输入映射、rank全集、trace信号/路径/成员/接力；未知定义不签过。重封印变异仍能被抓，不是只验文件哈希。
8. 固定提交fbd8f2a6后，在源码不变、干净树上并行运行四叶检查与原题原样真模型复验。第二组明确隔离用户根、EpisodeStore、部署账本和端口18896；启动health与实际served_model证明使用该版本及glm-5.3-flash。
9. 四叶全部结束；第二组四题均transport completed但report partial。第1题缺市场类型后错误归因、第2题改近期窗且模板偏题、第3题接力不成熟解释错、第4题只查近日finance而没有启动同口径原件。第4题不再崩溃，但不算业务通过。
10. 停止两组隔离服务和runner；只封存原答、事件定位/哈希、引用映射和收据，没有再加同一句提示或换题重跑刷成功。

## 决策与被否方案

| 问题 | 采用 | 被否 / 理由 |
|---|---|---|
| local历史读工具 | `history_query/read_history_result` 经审定local_read，映射既有finance_query生产者权限 | 扩大LOCAL_READ_CAPABILITIES或按工具名字猜无外呼；写案例工具仍不放行 |
| 授权续问 | 完整原始用户链+可信HistoryIntent/MaterialContract；缺基底拒绝恢复 | 从摘要、助手旧答、模型参数恢复full；这些不是授权源 |
| 时间合同 | 授权窗/单次观察搜索窗/信息截止正交保存，截止取有效最早上界 | 把本轮start/end或较晚授权终点替换cutoff；会给未来事实开门 |
| 假设识别 | 仅窄排除研究过程条件，保留真实虚构市场前提 | 删除所有“如果”检测；会把真正假设变成事实 |
| 参数冻结与JSON | 在 `research_progress` 序列化边界递归复制Mapping/list/tuple | 取消ModelToolCall冻结，或捕获后伪装网络错误；前者弱化合同，后者丢因果 |
| 日期过滤 | 普通工具逐证据过滤并重建observation；历史原件走专用递归范围门 | 只贴“晚于截止”仍投递，或用无日期prose绕过；但本实现吞参数诊断的副作用尚未修 |
| 接力语义 | 原公式不变；源峰后同5日观察，确认是另一个状态 | 改为确认后5日来迎合错答，或未成熟当没接上；都偷换定义 |
| 算术独立性 | 不导入产品公式、DB或网络，冻结定义、手算oracle和重封印变异 | 原函数再跑一次叫独立验证；第二实现同作者也不能叫独立人员QC |
| 验收裁决 | 保存失败原答，工程/调用/算术/正文分别记 | completed、非空、semantic passed、E号存在就整组通过；本轮各有反例 |
| 复验成本 | 封存当前可复核节点，先针对失败补离线回归 | 不改代码重复live直到偶然成功；结果选择偏差且烧配额 |

## 已提交的修复边界

`fbd8f2a6`包含JSON进展账边界、local工具权限映射、三种时间合同、可信续问与过程条件、普通历史内容门、市场来源/单位、接力策略说明、独立审计扩展及相关回归；产品正门文档随代码更新。

未提交新一轮运行代码“修复”：诊断吞噬、market漏参恢复、接力状态解释、历史输出合同/原件主动读取等仅已定位并归档，**不能从本快照标题误读为这些都已修好**。

## 可复核证据

权威清单：[fbd8f2a6验收说明](../verification/history-market-anatomy/fbd8f2a6/acceptance.md)；文件哈希、call_id与事件行号：[live-manifest](../verification/history-market-anatomy/fbd8f2a6/live-manifest.json)。四篇原答与新CI/算术收据同目录。

- Python：11501P/81S/2X/17warnings；Ruff通过；前端107P及lint/typecheck/build；浏览器34P/2S；registry五项0（98条存量warning）。pytest收据 `~/.finance-runtime/test-receipts/20260918T012919Z-fbd8f2a6.json` 八项校验通过；源码测试前后clean。808P/12S是提交前相关回归，不替代该全量收据。
- 本机等价检查根 `~/.finance-runtime/history-market-anatomy-fbd8f2a6-checks/`。本机DuckDB1.5.4与workflow固定1.4.3不同，如实保留依赖；不是CI镜像环境认证。
- 真模型根 `~/.finance-runtime/history-anatomy-live-20260918-fbd8f2a6/`，会话 `conv_568a6d1b217b4a08be2fdf49becfc055`，四轮run分别092041、092341、092551、092658。全部保持real/local_only、严格01-01..09-15、cutoff09-15；实际菜单有history读工具，无save_history_research。
- live六原件独立算术：20845检查/29skip/0error；3 checked/1 partial/2 unsupported。旧七配方复算68457/98/0；3/3/1。analogues距离/排序等未支持；检查次数不是样本数，输入日历完整性也未独立证明。
- 公开E编号均存在，但则成电子E439无所引回撤数值、第3题immature原子不支持“必须确认”解释。引用身份核对不是全文语义认证。
- 服务已停；未在停服前保存最终隔离health，因此只有启动health、固定代码和干净树/收据证据，不编造后验health。生产health单独保留。

## 首轮隔离缺口（不得删除证据）

首轮只隔离users和部署账本，没有设置 `FORESIGHT_EPISODE_STORE`；EpisodeStore按 `$FINANCE_WS/state/episodes` 回退，写入了共享状态目录。第四题事件目录为：

`~/finance-workspace-private/state/episodes/run_20260917_234112_374567_msg_67af05100a464b3f8cb82f16ac9a2d94-d4317354931b/`

这不是生产行情库写入，也不等于生产用户画像被改；但“独立users即全隔离”的说法是错的。未删除这些失败记录。第二组显式设置独立episodes，验证写入新根；旧18895和新18896服务均已停。

## 下一步及不要做

1. 以保存失败补窄测试：market类型漏参和错误提示；工具诊断与事实observation分型；成熟度/未确认/未触发/缺数/收益失败分别投影；相同研究窗/启动特征与成员股路径锚；原件读取和最终引用。
2. 调查历史研究是否被公司矩阵/前向模板干扰，读实际TaskFrame/契约再改；不要再建第二研究链或把助手旧答当事实权限。
3. 冻新SHA后重验相关与四叶、原四题新隔离根，保留全部失败。独立QC、真实浏览器研究交付和完整方法前向认证仍未完成。
4. 不改原数学规则迎合错答，不放宽日期门换取诊断，不用临时TopN假装全集，不把观察成熟前当0/失败，不把日线因果或SPT/风远认证升级。
5. 不自动合main、不部署。每日收据/水位/运行代码根与前向方法回检是另案；本分支没有修它们。

## 工具沉淀盘点

- 重复真库/投影检查已在 `scripts/probe_history_queries.py`；它是开发探针，不是产品第二入口。KIT/TOOLKIT登记在独立 `~/hr-wt-history-query-probe`，共享harness的他人BUILD.md未碰。
- 独立原件复算已在正式 `scripts/audit_historical_research_artifacts.py` + `scripts/history_anatomy_arithmetic.py`，手算/变异/禁止产品依赖测试进仓。它归E档，不混同B档投影探针。harness登记 `docs/history-query-probe@fef36d6` 已提交推送，包含原探针8c902cb；check_refs 234引用/0缺失，保留26行数漂移/8未解析/1未核数，新分支路径另用git show/AST核验。harness与finance候选均待合入，保护镜像待既有流程。
- 这次包证据的 `package_evidence.py` 留在运行根，仅一次性封存已存在文件/哈希，不定义新裁决；可复用入口已是workbench_probe与算术审计器，不把手选业务结论伪装成通用判官。正文语义仍需按领域合同审查，故只记录逐条失败证据。
- 能力图谱/MOC已回写候选与真实拒收；本轮graph_audit exit 0，新路径仍是PENDING分支，非生产可达认证。vault_lint再跑仍19错误/17警告、exit 1，包含既有死链/元数据/TOOLKIT镜像漂移；没有擅修无关或保护区文件。
