## 这个分支做什么
复用Workbench/Episode/history_query与主库，完成市场参照→强势对象→启动/峰值→接力→同口径特征。

## 决策与被否方案
| 选 / 否 / 理由 |
|---|
| 可信用户链+三类时间合同 / 助手旧答授权 / 防扩权 |
| typed诊断+清洗，事实照常过门 / 错误或空evidence放行prose / 防事实洗入 |
| 状态/日数/原因同卡 / 只加全局提示 / 单卡引用仍须可解释 |
| v1.1显式日期、旧v1只读保存日历 / 猜日期或改旧原件 / 未知不装0 |
| 保留公式与业务失败 / 加峰确认迎合错答、重抽刷绿 / 分清证明层 |
展开：`docs/handoffs/2026-09-18-history-succession-delivery.md`。

## 当前状态
树`~/fwp-wt-history-market-anatomy`。代码ba281381、归档1528e917已推；WIP #783已更新，未合未部署。四叶runner已结束，无后台待验，18891/18894/18895/18896无监听；未动生产库/画像/每日链。
诊断纠错和接力限定交付已有确定性修复，没重跑真模型；最近fbd8四题仍整组失败。MOC/图谱e0a4ec66已同步，知识卡b4c7eddd；harness7801091已推未合，保护镜像/共享BUILD未碰。

## 已验证
ba固定clean：Ruff、Python11566P/81S/2X/17warning、前端107P及lint/typecheck/build、浏览器34P/2S、registry五项0/98warning；正式pytest收据八项过。7接力+4诊断内存变异抓住。实际240预算/单卡审核/跨轮禁DB读取/脚本Episode/12卡恢复已验；旧第三题原件SHA不变，复算0error/0skip。
入口`docs/verification/history-market-anatomy/ba281381/acceptance.md`：32份源/副本和19源码哈希核验。文档提交不代签新SHA全量。

## 未验证 / 已知边界
真模型自主纠错/正确解释未验，无自由文本自动判错器。异窗rank、启动时特征/控制组、主动读原件与前向偏题仍待修；保存合同是线索非根因。analogues排序未独立复算，无人员QC/浏览器真实研究交付/完整方法认证。首轮漏EpisodeStore、第二轮缺health-after已披露。每日水位/代码根另案。
graph_audit退出0仍有PENDING/UNVERIFIED；vault_lint20错17警告（较上轮新增他项insurance-copilot元数据错误），未扩大修。

## 下一步
修同窗/启动特征合同与跨轮原件主动读取，追实际prompt，不只补提示。业务片修完后新SHA四叶+新隔离根跑原四题，显式EpisodeStore和health前后；失败保留。合并/部署分别待授权。

## 踩过的坑
immature是源峰后不足5日，非失败；无需先回撤确认，双方收益同源峰后5日。成员路径≠个股启动。volume_ratio是百分数；cutoff非入库时点。
开发854P日志与故意变异同秒撞收据名：现存081828-edf JSON是0P/1F，不能代854P，未补造；通用唯一命名待另修。正式全量用082918-ba，别取全局latest。脚本/算术/semantic绿不代业务。
