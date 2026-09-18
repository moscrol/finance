# 研究答案保留｜2026-09-19离线返修收口

## 这个分支做什么
同任务安全分析不因格式/质量问题整段删除；保留、准入、核验、交付分账。

## 决策与被否方案
- 仅顶层draft恢复LF/CR/TAB；否全局strict=False/猜引号，正式finish仍严格拒收。
- 已绑定D10/D4/finance_query做有限诊断；原文＋批注＋原会话修订，不删稿，不额外授预算。
- 判官passed不能盖过机械发现，补稿不能洗白仍在的错误原文。
详见`docs/handoffs/2026-09-19-draft-claim-offline-repair.md`。

## 当前状态
4d541a90实现、cdcbc5a8收窄统计范围均已提交；**cdcbc精确干净完整工程全绿**。本轮离线返修已收尾，新live0，无后台检查/服务待收取。旧三个实际样本仍not_passed。
R=`~/.finance-runtime/reviews/research-draft-claim-repair-20260919/`，748文件封存；根层含4d中止轮，final/才是cdcbc最终轮。8792仍bf662e9310ff、启动器不变；8849/8851/8852无监听、无锁。未push/合main/部署。

## 未验证 / 已知边界
- 仅证明保稿/七类有限发现/修订反馈通路；未证明真实模型自然改对，无独立金融QC。
- 未知投影、明确校准声明的真实性仍靠语义核验；子集/前瞻窗口不强套全表均值下限。
- 历史find_analogues参考窗口纠参未修；候选/发布跨进程恢复、旧用量/durable不一致未修。
- 上轮209 live是published/partial但质量未过；该轮retained0事实不变，本轮retained1仅离线。

## 下一步
本轮无需再跑/封存。若继续产品验收，先明确新的有界live授权与验收范围、新建证据根；不重发旧样本。合流/上线另确认，当前收据不覆盖后续revision。共享harness的BUILD.md他人在途，KIT/TOOLKIT登记暂缓，勿覆盖。

## 已验证
cdcbc：11769P/81S/2X，前端115P、E2E34P/2S，ruff/registry/收据校验绿；收据20260918T180956Z-cdcbc5a8。11撤保护各exit1，恢复66P。
封存原件2096字provider失败后仍保留、retained1/122证据不变，正式finish仍not_json_object；终稿8条发现覆盖7类、原稿不删且partial/rejected。旧新代码交叉期待承重；原Mapping/早期保稿/RAG回放过；9旧包逐文件不变。

## 踩过的坑
4d把后续5日与窗口内均值混比，主动中止pytest=-15/无完整收据，不拼绿；两次-k空选择exit5不算反例，正确3F后才修。扫描18模块词形精确核销≠全包零命中。工程绿/离线机制启用≠自然金融质量通过，收据不移绑文档tip。
