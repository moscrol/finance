# 研究答案保留｜2026-09-19离线返修收口

## 这个分支做什么
同任务安全分析不因格式/质量问题整段删除；保留、准入、核验、交付分账。

## 决策与被否方案
- 仅顶层draft恢复LF/CR/TAB；否全局strict=False/猜引号，正式finish仍严格拒收。
- 已绑定D10/D4/finance_query做有限诊断；原文＋批注＋原会话修订，不删稿，不额外授预算。
- 判官passed不能盖过机械发现，补稿不能洗白仍在的错误原文。
详见`docs/handoffs/2026-09-19-draft-claim-offline-repair.md`。

## 当前状态
4d541a90实现、cdcbc5a8收窄统计范围均已提交；**cdcbc精确干净完整工程全绿**。离线返修已收尾，旧三个实际样本仍not_passed。
R=`~/.finance-runtime/reviews/research-draft-claim-repair-20260919/`，748文件封存；根层含4d中止轮，final/才是cdcbc最终轮。8792仍bf662e9310ff、启动器不变；8849/8851/8852无监听、无锁。未push/合main/部署。

**0922有界live验收已执行：首发1/重发0/续问0，四项分账——三项未触发，金融质量不通过。**
L=`~/.finance-runtime/reviews/research-preservation-natural-live-20260922/`，`audit.json`为结论件。数据按09-18口径新冻结（主库clone、快照合约PASS、746文件只读manifest），**旧库副本已被清理故非严格新旧对照**，题面显式写截至2026-09-18。run_20260922_191550_067475，102秒/6工具/77证据。
**前置阻塞与修复**：首轮readiness 503于`rag_worker`——**BAAI/bge-m3权重整机不存在**且`HF_HUB_OFFLINE=1`禁下载，任何新进程预热必败。用户授权后固定sha 5617a9f6拉回12文件/2189MB（排除未用的onnx 2.16GB）。两个坑：按sha下载**不会写`refs/main`**，离线解析main失败；补齐ref后又因hub要求**整仓完整快照**而报incomplete。最终用`RAG_BGE_MODEL`指本地快照目录绕开仓库解析（同一sha同一权重），已记`protocol-amendment.json`。
**生产遗留风险**：8792 worker在权重消失前已加载故仍ready，**但重启会撞incomplete snapshot**；要么补齐onnx（磁盘不够）要么给启动器加`RAG_BGE_MODEL`（生产配置变更，未做）。另其readiness本就not_ready于`market_data_consistency`（库09-18 vs 快照meta 09-22）。磁盘已到100%、仅2.6–4GB可用。
收尾：实例已停、自有锁释放、8849空闲；生产身份七字段逐项相同，冻结数据manifest复核不变，测试用户未落入共享用户根，旧748文件零变动。

## 未验证 / 已知边界
- **0922样本四项分账**：保稿=未触发（模型首次finish即被接收，无not_json_object拒收，retained0）；诊断=未触发且有一条漏报（findings 0，而人工核对发现`endpoint_not_path`类问题）；自然纠错=未触发（repair_attempts/cycles均0，无批注就无从纠错）。**未触发不计通过。**
- **金融质量不通过**（作者自查，非独立QC）：①交付是空指针——154字以「见正文」开头而**正文不存在**（report modules=0），必需输出`direct_assessment`/`evidence_boundary`缺失但仅observation_only、judge照样passed；②「两段先回调」与D10原数据不符（该两段后续5日均为正+0.30%/+1.08%，10/20日才转负，应为先走强后回落）；③选择口径未交代（09-18满足双红的85个板块中，成交额前列是芯片9277亿/电子6499/数据中心5740，答案只报半导体与AI算力且未说排序依据）；④模型自造实体`899050.BK`（北证50），冻结库无此码、特征全missing，仅入gaps未入公开答案。
- 已核实为真：反弹第1天（stage_day=1）、推荐板块确满足双红规则、半导体系居涨幅前列、D10确有三段真实计算窗口、D11个股类比如实标缺口。
- KB索引处stale（源文件已变），召回质量降级，属机器既有状态未动。
- 仅证明保稿/七类有限发现/修订反馈通路（离线）；未证明真实模型自然改对，无独立金融QC。
- 未知投影、明确校准声明的真实性仍靠语义核验；子集/前瞻窗口不强套全表均值下限。
- 历史find_analogues参考窗口纠参未修；候选/发布跨进程恢复、旧用量/durable不一致未修。
- 上轮209 live是published/partial但质量未过；该轮retained0事实不变，本轮retained1仅离线。

## 下一步
本线仍保blocked：三项机制未触发、质量不通过，不得以本样本为由宣布收口。优先级建议：
1. **空指针交付是新缺陷**（与保稿线同源但独立）：「见正文」而无正文、必需输出缺失仍能passed，建议单独立单；考虑把`answer_marker_coverage`由observation_only升为阻断条件。
2. 若要再取自然纠错样本，需**能稳定触发拒收的题型或注入点**；本次正常路径不进修复机制，再抽盲样本价值低。新样本仍须新授权与新证据根。
3. 机器层：磁盘100%、HF快照不完整、KB索引stale三件都会影响下一次验收，建议先清。
不重发旧样本；合流/上线另确认，当前收据不覆盖后续revision。共享harness的BUILD.md他人在途，KIT/TOOLKIT登记暂缓，勿覆盖。

## 已验证
cdcbc：11769P/81S/2X，前端115P、E2E34P/2S，ruff/registry/收据校验绿；收据20260918T180956Z-cdcbc5a8。11撤保护各exit1，恢复66P。
封存原件2096字provider失败后仍保留、retained1/122证据不变，正式finish仍not_json_object；终稿8条发现覆盖7类、原稿不删且partial/rejected。旧新代码交叉期待承重；原Mapping/早期保稿/RAG回放过；9旧包逐文件不变。

## 踩过的坑
4d把后续5日与窗口内均值混比，主动中止pytest=-15/无完整收据，不拼绿；两次-k空选择exit5不算反例，正确3F后才修。扫描18模块词形精确核销≠全包零命中。工程绿/离线机制启用≠自然金融质量通过，收据不移绑文档tip。
0922三条：①launch后立刻探活撞启动窗口得Connection refused，是传输竞态非业务失败，已记`run-attempt-aborted-01.json`且未占名额；②首次手动复现把`--kb-root`传成wiki子目录（应为仓库根），得到误导性FileNotFoundError，改对参数才拿到真因OSError——复现参数错会把环境问题误判成代码问题；③worker进程级stderr被DEVNULL丢弃、真因只在JSON响应的stderr字段里，光看服务日志与readiness只能看到`RuntimeError`空壳。
