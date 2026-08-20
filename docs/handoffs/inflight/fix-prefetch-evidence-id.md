# fix/prefetch-evidence-id

## 这个分支做什么
成功路径稿**子单 C**：给开场预取行打 `[E<n>]`，模型才引用得到，判官不再把预取来的真话判成「发明历史行情」。

## 当前状态
已推，**PR #288 open 未合**。基线 `gitea/main@dfc25221`，head `0cedd44f`，树 0 处未提交。生产 8792 **未切**（仍 `dfc25221b07b`）。
只改一处：`asof_prefetch.format_opening_prefetch_message`（+24/-2）。**判官侧未动**。

## 怎么验收
1. `pytest intelligence/tests/test_prefetch_evidence_ordinal.py` → 5 passed
2. 变异：`evidence_ordinal_table(hashed)` → `(tuple(reversed(hashed)))` 必须 **3 failed**；前后各清 `__pycache__`
3. 调 `format_opening_prefetch_message(evidence_from_prefetch(items))`，输出须含 `[E1]`
4. 比读数：修后 `run_20260821_021724_077535`（sidecar）vs 修前 `run_20260821_015459_794701`（生产）
展开全在 `docs/verification/2026-08-21-gate1-prefetch-evidence-id.md`。

## 未验证 / 已知边界
n=1 未过方差门 → `R-20260821-03` 记 `pending`，**不得 `confirmed`**。只验了创新药一题，`market_forecast` 未跑。
⚠ 与 `docs/8792-dfc25221-cutover`（PR #287）同改 `docs/prediction-ledger.md`，**后合方要 rebase 重解**。

## 下一步
1. 等用户确认合 #288。不切 8792。
2. **合后**才开子单 A：§6 一次只开一条，§5 要求换一道没用过的新题重跑 Gate——创新药已是本单夹具，不能复用。
3. `CLAUDE.md:27` 写「七个模式+16 零件」，实际九个+17，已漂两代，待单开小 PR。

## 踩过的坑
- **根因误判过一次**：初判「E1/E2 从没发号」。复算发现预取两条 hash 齐全、稳拿 E1/E2。误读源是 `outcome.evidence[].evidence_id` 全 `None`——**那字段本来就不落盘，号是终局现算的**。缺口在下一层：呈现层没写号。
- `[E1]` **不进 `continuous-episode.json`**（开场是 user 消息，不是 tool 事件）。别 grep 产物然后以为没生效。
- 错号比没号危险（会引到别人证据上）。变异要锁**发号顺序**，只锁「有没有号」不够。
- `resolve_theme_alias` 的 `None` 双关：「解析不到」与「本来就是精确名」同值。§6.1 让预取按前者 fail closed，迟早咬人。本次未触发。

## 已验证
TDD 修前 3F/2P → 修后 5P；宽集 **381 passed**（收据 `20260820T181642Z-dfc25221`）；ruff 绿；变异 3F / 还原 5P；live 公开稿 **894→1027 字**，四段发酵弧保住，`E1` 引用 117 次（修前 0 且模型自陈「无证据序号」），6-29 / 7-15 / 8-3 / 8-7 四组数与分析师侧逐位对齐。

## 工具沉淀
模式已归位 `~/harness-reference/BUILD.md` 第 9 条「投递事实必须连同引用把手一起投递」，`KIT.md` 同步（八→九）。未抽脚本：判「注入片段有没有引用把手」要读具体注册表语义，样本仅 1，先留模式。
