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

**0922有界live验收：环境阻塞未发题，授权名额未消耗（首发0/重发0/续问0，provider调用0）。**
L=`~/.finance-runtime/reviews/research-preservation-natural-live-20260922/`。候选cdcbc5a8干净、收据校验绿、离线回放repaired复现（retained1/8发现/7类）、旧748文件零变动。数据按09-18口径新冻结（主库clone 3.70GB、快照合约PASS、746文件只读manifest），**旧库副本已被清理故非严格新旧对照**，题面显式写截至2026-09-18。
阻塞在产品自身fail-closed：`/api/readiness` 503，`missing_critical=['rag_worker']`。真因非内存非代码：**BAAI/bge-m3权重整机不存在**（`~/.cache/huggingface`、`~/Library/Caches/huggingface`均无，全盘无`models--BAAI`，清理归档清单亦无记录），而`HF_HUB_OFFLINE=1`禁下载 → 任何新进程预热必失败（12.7s即挂，非145s加载）。未绕闸、未降级hash编码器（512维与1024维索引不兼容且属伪质量）。
生产8792只读观测未动：其worker在权重消失前已加载故仍ready；**但8792一旦重启会撞同一失败**。另其readiness本就not_ready于`market_data_consistency`（库09-18 vs 快照meta 09-22），属既有夜跑数据链问题，未处理。
收尾：实例已停、自有锁释放、8849空闲；生产身份七字段逐项相同，冻结数据manifest复核不变，测试用户未落入共享用户根。

## 未验证 / 已知边界
- 仅证明保稿/七类有限发现/修订反馈通路；未证明真实模型自然改对，无独立金融QC。
- 未知投影、明确校准声明的真实性仍靠语义核验；子集/前瞻窗口不强套全表均值下限。
- 历史find_analogues参考窗口纠参未修；候选/发布跨进程恢复、旧用量/durable不一致未修。
- 上轮209 live是published/partial但质量未过；该轮retained0事实不变，本轮retained1仅离线。

## 下一步
先恢复检索模型再谈验收：需用户授权联网重新拉取`BAAI/bge-m3`（约2.3GB写入共享HF缓存，当前磁盘余16GB）——它同时解除8792「重启即坏」的隐患。恢复后可直接复用L的control.py（prepare已完成且幂等拒重跑，续跑launch/run/close即可），仍按首发1/重发0/续问0、600秒40步、四项分账判定。
不重发旧样本；合流/上线另确认，当前收据不覆盖后续revision。共享harness的BUILD.md他人在途，KIT/TOOLKIT登记暂缓，勿覆盖。

## 已验证
cdcbc：11769P/81S/2X，前端115P、E2E34P/2S，ruff/registry/收据校验绿；收据20260918T180956Z-cdcbc5a8。11撤保护各exit1，恢复66P。
封存原件2096字provider失败后仍保留、retained1/122证据不变，正式finish仍not_json_object；终稿8条发现覆盖7类、原稿不删且partial/rejected。旧新代码交叉期待承重；原Mapping/早期保稿/RAG回放过；9旧包逐文件不变。

## 踩过的坑
4d把后续5日与窗口内均值混比，主动中止pytest=-15/无完整收据，不拼绿；两次-k空选择exit5不算反例，正确3F后才修。扫描18模块词形精确核销≠全包零命中。工程绿/离线机制启用≠自然金融质量通过，收据不移绑文档tip。
0922三条：①launch后立刻探活撞启动窗口得Connection refused，是传输竞态非业务失败，已记`run-attempt-aborted-01.json`且未占名额；②首次手动复现把`--kb-root`传成wiki子目录（应为仓库根），得到误导性FileNotFoundError，改对参数才拿到真因OSError——复现参数错会把环境问题误判成代码问题；③worker进程级stderr被DEVNULL丢弃、真因只在JSON响应的stderr字段里，光看服务日志与readiness只能看到`RuntimeError`空壳。
