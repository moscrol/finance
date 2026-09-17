## 这个分支做什么
复用历史问答正门，补市场类比、当时强弱、启动到峰值、候选接力及同口径特征。

## 决策与被否方案
| 选 / 否 / 理由 |
|---|
| 现有history_query+主库 / 新库与新引擎 / 不分裂日期授权和事实 |
| 前缀信号+事后峰值 / 倒看最低点与实时顶部称谓 / 防未来泄漏 |
| 启动日名单、全集留缺数 / 当前名单与只留赢家 / 保分母 |
| 日线候选接力 / 资金搬家因果或完整SPT/风远 / 证据强度不够 |
展开：`docs/handoffs/2026-09-17-history-market-anatomy.md`。

## 当前状态
代码`506e1e23`、验证`d5e6854e`已提交推送，WIP PR #783；未合并、未部署。独立树`~/fwp-wt-history-market-anatomy`。没有改每日流程、生产行情库、用户视角或台账。
能力图谱/MOC已由vault自动同步提交`a40a999b`。探针KIT/TOOLKIT登记另树`hr-wt-history-query-probe@8c902cb`已推未合，已完成日期快照里待登记那一步；共享主树他人BUILD改动未碰。

## 已验证
固定代码506e1e23：ruff通过；pytest 11464P/81S/2X，收据校验8项通过；前端四步含107测试通过；隔离浏览器34P/2S；registry五项过。收据在`docs/verification/history-market-anatomy/`，后续提交仅文档，不冒充main合流收据。
7项真库只读查询、真实投影、rank→trace作者选码路径；3项变异拦截。真实注册表/分页/日期越界、脚本模型Episode与run_turn→controller接缝已验。

## 未验证 / 已知边界
未做隔离Workbench真模型连续四题的自主选工具、跨轮追问、最终引用和正文验收；既有浏览器夹具回归不替代它。独立算术审计对market/trace/rank为unsupported。
日线代理非完整视角方法；峰值关联到窗尾才可知；接力非因果。主库水位不等于完整性；原件时钟非严格记录时点。
每日收据/代码根一致性和前向方法回检不在本次改动。vault全库仍19错17警告（既有死链等）；本次图谱audit通过。harness check_refs无缺失但有存量行数漂移；候选分支引用另用git show/AST核验。

## 下一步
先按日期快照验收四题与失败场景；补新算子独立复算。合并需用户确认，主干变动后重跑合流门禁，部署另确认。harness登记合入后按保护流程同步vault TOOLKIT镜像。

## 踩过的坑
market_stage看专属source：09-15实际本地分类模型；cycle_stage是供应商内层，空则未知，confidence非正确率。量比末日/此前均额非默认MA20；volume_ratio是百分数。预览不改变全集，NAV采样不是完整蜡烛形态。原件与运行日志在`~/.finance-runtime/history-market-anatomy-*`，旧中间query_id不要代签最终候选。
