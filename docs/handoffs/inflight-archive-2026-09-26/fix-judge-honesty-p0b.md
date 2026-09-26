# fix/judge-honesty-p0b

## 这个分支做什么

判官走 fail-closed gap 时，公开稿不得再说「证据不足 / 未完成核验绑定」。不放宽 RuntimeError 白名单，不放未分类故障的稿。

伞形 spec：`docs/superpowers/specs/2026-08-23-publication-and-contract-subtract-design.md` §6.2 v1.1

## 当前状态

代码已写。树：`/Users/a77/fwp-wt-judge-honesty` ← `gitea/main@3ac070a2`。

| 检查 | 结果 |
|---|---|
| session_projection + gap 中间档 + 本单 B2 + 既有 transient 回归 | 59 passed |
| degraded_fallback / rejudge / judge_degrade | 51 passed |
| ruff | 过 |
| 全量 `test_episode_semantic_verifier.py` | 未采信：本机 `judge_provider` 已配置时，短 deadline 夹具会走 leftover 放稿，干净 `3ac070a2` 同样红 |

## 做了什么

- 新成因 `judge_unavailable_held`：开口「复核服务不可用」，不说超时、不说证据不足。
- `_gap_answer(..., judge_unavailable=True)` 改 **body**（`:2632` 那句不再出现）。
- 只在「判官 report is None、未进放稿白名单」那一处调用传 `True`。
- 夹具 B2：`complete` 返回裸 `RuntimeError` → issue=`semantic judge provider error` → 稿不放、禁语不出现。

## 不要做

- 不要把 `"semantic judge provider error"` 或整类 `RuntimeError` 加进 `:989` 白名单。
- 不合 main、不切端口。

## 下一步

P0-A 仍等点头。P0-C 在 `feat/contract-honor-p0c`。
