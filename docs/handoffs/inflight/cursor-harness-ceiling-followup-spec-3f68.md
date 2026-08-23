# cursor/harness-ceiling-followup-spec-3f68

## 这个分支做什么
Harness 后续规格（GitHub PR #3）。只改文档。纲领：增加输入必要就加，限制输出只做减法。

## 当前状态
v3 已按用户判据改定。树 `/Users/a77/fwp-wt-harness-ceiling-followup-spec`。不合 main。

## 未验证 / 已知边界
产品代码未动。D0 周一复验未跑。D1 尚未回读有色 8796 的 `__cause__`，可能取证后关单。

## 下一步
从 D0 开做，另开 `gitea/main` 干净树。不要在本 spec 树改 runtime。

## 踩过的坑
v1 没对 prediction-ledger。v2 给输出侧加了第三扇门。Knevo A1 ≠ 周一题。
云端排查子代理 ID（会腐烂，只放这里）：`079a3f4b-6c91-40ce-969b-22381bcc58ce`。失效就重读 spec §0.3，不要写回 spec 正文。

## 已验证
R-05 confirmed；W1 #309+#334、W2 #307 在 main；开关板只在 `76ee1e89`。
