# fix/prefetch-evidence-id

## 这个分支做什么
子单 C 两刀：① 开场预取打 `[E<n>]`（#288 已推）；② 问句里的精确 `sector_name` 优先于缩短 subject（未提交）。

## 当前状态
**已收口（2026-08-21）**：#288 已合入 main（merge `a68baee5`，含精确名刀），8792 已切 `6320b3bcbf82`。live 双臂（CXO 同题 / 减肥药新题）预取均锚精确名、判官零「发明历史行情」类 issue，台账 `R-20260821-03` → `confirmed`。收口详情见 `docs/handoffs/inflight/main.md` 2026-08-21 行与 `docs/verification/2026-08-21-tracediff-cxo-ceiling.md`。以下为合并前历史状态。

#288 open 未合，head `33b4ca95`。本树另有未提交：`asof_prefetch.resolve_prefetch_sector` + 1 测 + Gate 1 诊断。生产 8792 **未切**（`dfc25221b07b`）。判官未动。

## 怎么验收
1. `pytest intelligence/tests/test_prefetch_evidence_ordinal.py` → 5 passed
2. `pytest intelligence/tests/test_asof_prefetch_dual_red.py` → 含精确名优先；变异把候选改回 subject 优先必须红（清 `__pycache__`）
3. 预取标题须为长名时间轴，问句日数字须为长口径（诊断文表格）
4. #288 旧四步（`[E1]`、修前后创新药 run）仍成立

## 未验证 / 已知边界
`R-20260821-03` 仍 pending。精确名 live 预取过了，公开稿没过：主线工具仍灌短名，判官整段删把长口径问句日带走。`PCB` 6/29–7/24 同日两行（双 published）未修。与 #287 同改 ledger，后合方 rebase。

## 下一步
1. 不切 8792；合 #288 等用户。精确名刀未提交，要不要进 #288 等你定。
2. **下一刀只开一条**：子单 B（公开稿问句日锁 E1）或关发酵题 live `mainline_context`。不要开 A。
3. `CLAUDE.md:27` 七个模式已漂到九个+17，待另开。

## 踩过的坑
- `decide_turn` subject 收短（PCB概念→PCB）不是预取层的事；短名在表里有行会短路长名优先。
- `[E1]` 不进 `continuous-episode.json`。E2「已替换主线」只是文案，工具仍可调。
- 真话和编造绑同一段，判官整段砍——#288 镜像。数字必须进槽。
- `resolve_theme_alias` 的 None 双关仍在。

## 已验证
#288：TDD 5P、变异 3F、live 894→1027 字。精确名：修前红 / 修后 13P / 变异红；sidecar dirty live 预取标题与 4.74/3432 对齐。

## 工具沉淀
BUILD.md 第 9 条已有。本刀是「长名在问句里出现则先于缩短 subject」，未抽新模式。
