# feat/e1-e3-repair-ttl

## 这个分支做什么
轨道 D：E1 把已有 `contract_missing_outputs` 送进 episode repair；E3 给判断加机器可读 `valid_until` 和过期降级（只标注不删）。判据 `docs/learning/spec-continuous-depth-gap-r1.md` R5 §三 P1-E。

## 当前状态
1 笔 `aaba343c`，从 `gitea/main@c163ca7b` 长出。树 `~/fwp-wt-e1-e3-repair-ttl`。未合未推。C 开工时不存在，本枝避开 `conversation_orchestrator`。

## 未验证 / 已知边界
- 公开稿本发被零证据门禁收成模板；私有 draft + 收据齐。
- 纯 contract-rewrite（只缺四态、required output 已满）只有单测，没有单独 live。
- 与 C 未共存。C 先合则 rebase。
- 生产 8792 不切。

## 下一步
用户确认后开 PR / 合并。不要因本单去切 8792。

## 踩过的坑
- 只把 id 塞进 `missing_outputs` 不够：首轮已有证据进展时 `grant_for_progress` 会开工具。表达层-only 必须 `contract_rewrite_candidate`。
- 不要把 track 缺件写进 `issues`：#224 放行门吃前缀。
- `live_probe ask` 没有 `theme_track`，会话口才有。

## 已验证
sidecar `:8814` `run_20260819_164434_166829`：repair goal 含三个 `track_*` id；修后收据 `valid_until=2026-09-18`、`prior_verdict_check=信息不足`。E3 过期标注见 `e3-foresight-render.txt`。读数 `docs/verification/2026-08-19-e1-e3-repair-ttl-live.md`。定向 80 passed @ `20260819T084708Z-aaba343c`。
