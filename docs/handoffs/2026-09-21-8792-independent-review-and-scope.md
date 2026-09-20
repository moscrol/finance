# 8792 独立复核与范围状态返修

本快照记录8792题设计算、跨轮状态、公开交付和行情证据修复的独立复核。修复树 `/Users/a77/fwp-wt-8792-premise-market`；生产8792仍是 `bf662e9310ff751a4c31763815ee78fb7d6d5122`。不合main、不push、不部署、不付费外审、不删除生产。

## 最终候选与代码复核

最终候选 `8810bac84f67ffd6179b744710f4a88f3b5c51ee`，分支树clean后冻结。完整Python：`12044 passed / 85 skipped / 2 xfailed`，日志 `/tmp/8792-premise-v19-full-pytest.log`；前端六项全过，收据 `~/.finance-runtime/8792-premise-market-v19-frontend/frontend.json`，revision和clean identity均匹配。v19短diff K3代码复核正常stop、非空JSON、PASS；只覆盖本轮题设状态/缺单位崩溃/范围冲突/重复issue修复，不覆盖任意财务prose。

v16 K3发现P1：缺单位修复的`invalidated_keys`混合None/年份时排序崩溃；同时发现静态范围冲突处理缺口。v17/v18分别修复混合排序、当前消息范围识别和历史指标误报；v19补冲突issue去重。定向最终118项通过。普通非静态PE仍不进入专用程序计算器；未识别数字文字仍是语义审核边界。

## v19 live 与公开交付

sidecar `18893`，用户根 `~/.finance-runtime/8792-premise-market-v19-users/`，健康指纹与候选匹配、clean，ready市场日期为2026-09-18，active/queued收尾前须归零。原三题各一次且无自动重试；首题/追问同会话 `conv_c3464ffaab0d4d039ef9e1d6d4165859`，行情新会话 `conv_0146e9335bce4549a3007ef707dc60da`。三run均completed、answer非空：

- 首题：25%、12.5%、10%、9%、-1个百分点、66.6667%、180亿元、20倍；明确不能仅凭PE判断便宜。
- 追问：240亿元、26.6667倍、7.2亿元、33.3333倍；保留不变指标并明确情景不是预测。
- 行情：4234/1151/168、79/0；前三板块功率半导体、集成电路设计、半导体设备及对应涨幅/成交额均与canonical一致，日期和`.FP`复盘会口径已公开。

`public-delivery-v19.json`正常3/3；wrong PE、吞表边界、涨跌互换三变异均失败。v19准入守卫正常3通过；`--disable-admission`为真实2失败/1通过，非TypeError/0测试。行情run的judge留下P3：句子“EDA、封测、存储、汽车芯片随后”未绑定到该句引用的E2/E3/E4/E52，不能把自由文字全量写成PASS。独立财务K3两次请求均HTTP 400 invalid_request，无有效报告，记INCOMPLETE；不能用它替代财务签字。完整原件均保留在 evidence 根。

## 决策与边界

题设授权不等于数学认证；程序只拥有有限静态PE合同。跨轮继承活动请求/情景，明确替换/取消可收窄，冲突留缺口；主体只做有限前缀规范化后精确比较；缺单位不沿用旧值，带单位更正才恢复。canonical不是第二供应商；代码、公开交付、财务独立复核分别签字。registry外部`kb/rag-query`漂移继续单独记录，不顺手修。

## 下一步

关闭sidecar并核ready active/queued为0；只读核对生产8792原revision/fingerprint仍未变。若要清理行情P3，必须另建候选、重跑完整工程/K3/live，不能编辑v19原件或移签收据。更新run汇总和manifest时保留所有失败/无效接线原件。不合main、不部署。
