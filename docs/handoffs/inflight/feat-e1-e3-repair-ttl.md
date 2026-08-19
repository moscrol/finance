# feat/e1-e3-repair-ttl

## 这个分支做什么
轨道 D（`docs/handoffs/2026-08-19-depth-gap-execution-dispatch.md`）：E1 把已有 `contract_missing_outputs` 送进 episode repair；E3 给判断加机器可读 `valid_until` 和过期降级（只标注不删）。判据真本源 `docs/learning/spec-continuous-depth-gap-r1.md` R5 §三 P1-E。不写第二套文案；不改 #224 的 issue 前缀。

## 当前状态
从 `gitea/main@c163ca7b` 新开。树 `~/fwp-wt-e1-e3-repair-ttl`。C（`feat/e2-revise-first`）开工时未存在，本枝避开 `conversation_orchestrator`；C 先合则本枝 rebase。

## 未验证 / 已知边界
- 从未 live。
- 未与 C 共存。
- 生产 8792 不切。

## 下一步
TDD：缺件 → repair admission → adapter 接线 → TTL 收据与过期标注 → sidecar 一发真 `theme_track`。

## 踩过的坑
- 只把 id 塞进 `missing_outputs` 不够：`grant_for_progress` 在首轮已有证据进展时会开工具。表达层缺件必须走 tool-closed delivery。
- 不要把 track 缺件写进 `issues`：#224 放行门吃前缀，生造文案会 fail closed。

## 已验证
（尚未）
