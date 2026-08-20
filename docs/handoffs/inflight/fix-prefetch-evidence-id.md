# fix/prefetch-evidence-id

## 这个分支做什么
成功路径稿 **子单 C（挪约束）**：给开场预取行打 `[E<n>]`，让模型引用得到，判官不再把预取来的真话判成「发明历史行情」。改一处呈现层 + 5 条离线测试 + Gate 1 落档。

## 当前状态
已提交未推。基线 `gitea/main@dfc25221`。生产 **8792 未切**，仍 `dfc25221b07b`。
产物：`intelligence/services/asof_prefetch.py`（+24/-2）、`intelligence/tests/test_prefetch_evidence_ordinal.py`（新）、`docs/verification/2026-08-21-gate1-prefetch-evidence-id.md`（新）、台账新号 `R-20260821-03`。

## 未验证 / 已知边界
- **n=1，没过方差门**，`R-20260821-03` 记 `pending` 不得 `confirmed`。
- 只验了创新药一题。其他发酵题、`market_forecast` 题未跑。
- `[E1]` 标签**不落盘**（开场 user 消息不进 `continuous-episode.json`），靠直接调函数 + 模型引用行为双向确认。下一个人别去 episode 产物里 grep `[E1]` 然后以为没生效。
- ⚠ **台账会冲突**：`docs/8792-dfc25221-cutover` 分支（也未推）同样改了 `docs/prediction-ledger.md` 的行 3 与 `-06`…`-11`。两条都从 `dfc25221` 长出，后合方 rebase 重解。这是 acceptance-workflow 写明的常态热点。

## 下一步
1. push + 开 PR（**未做，等用户拍**）。合并等确认，不切 8792。
2. 合完再看要不要开 **子单 A**（发酵轴起涨/补涨分层）。§6.1 第二触发条件确实成立，但**必须在 C 之后**——C 之前加行只会被同一把刀删掉。
3. 遗留见 verification 文档「遗留」节，都不是本改动引入。

## 踩过的坑
- **初判根因错了一次**：写成「E1/E2 从没发号」。实际用 `evidence_ordinal_table` 复算，预取两条 hash 齐全、稳拿 E1/E2。误读来源是 `outcome.evidence[].evidence_id` 全 `None`——**那个字段本来就不落盘，号是终局现算的**。拿它当「没发号」的证据不成立。缺口在下一层（呈现层没写号）。
- 号只能有一处来源。变异测试专门锁这个：`evidence_ordinal_table(reversed(...))` 必须转红——错号比没号更危险，会把引用落到别人证据上。
- 变异前后各清一次 `__pycache__`，否则同长度改回会假绿。
- `resolve_theme_alias` 的 `None` 是双关（「解析不到」与「本来就是精确名」同值）。spec §6.1 让预取按「解析不到就 fail closed」，若照这个 `None` 判断，精确名会被误判。本次未触发，但迟早会咬人。

## 已验证
TDD 修前 3F/2P → 修后 5P；宽集 381 passed（收据 `20260820T181642Z-dfc25221`）；ruff 绿；变异 3F/还原 5P；live `run_20260821_021724_077535` 四组数与分析师侧逐位对齐。

## 工具沉淀
可迁移的一条：**跨信任边界投递事实时，事实和它的凭据必须同时发放**。harness 把数据放上桌却没给引用把手，下游验证器只认把手不认数据，于是自家投递的真话被自家判成伪造。任何「注入上下文 + 引用校验」的 RAG/agent 系统都会犯——注入片段没进 citation registry，模型引用它就被判 hallucination。够格进 `BUILD.md`（换项目仍会犯），**待用户拍板再写**。
