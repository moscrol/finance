# fix/replay-rebuild-keep-observations-0925

## 这个分支做什么
`scripts/judge_loss_point_replay.py::_rebuild_outcome` 重建存证时保留证据的 `observations`（09-09 版置空），让数值门与财报题结构核验的重放与生产同口径。PR #935。

## 决策与被否方案
| 选了 | 否了 | 为什么 |
|---|---|---|
| 默认保留；`keep_observations=False` / `--drop-observations` 复现旧重建 | 静默改默认；默认仍置空 | `diff_replay_archive.py` 的 `KEEP_OBSERVATIONS=0` 臂依赖旧行为，本脚本结构列也会变 |
| 坏条目逐条跳过，判据同 `episode_evidence._atom`（拒 bool / 数值串 / 非有限值） | 整卡失败；收下 bool | 容忍旧存档又不编数；生产存档坏条目 0 |
| `history_provenance` 不动 | 顺手还原成对象 | 存档没有 `internal_locator`，还原了也过不了身份校验；生产 0 份受影响 |

展开：`docs/handoffs/2026-09-26-replay-rebuild-keep-observations.md`

## 当前状态
- 改动 `c9bd7b853`，交接单独一个提交；PR #935 open，**合入等用户确认**。
- 四叶在交接提交之后的 head 上跑，读数见 PR #935 评论。

## 未验证 / 已知边界
- 历史卡（`history_query`）的结构重放仍不保真，原因见上表。
- 仓外 5 份复核脚本没改，也没在新树上重跑；A/B 只比了本脚本入口和数字门。

## 下一步
- 用户确认后：`scripts/gitea_pr.py merge 935 --yes --expect-head <四叶 head> --record <json> --authorized-by "<原话>" --authorization-source <出处>`。
- 要在含本修复的树上跑 `l6-numeric-replay-20260925/diff_replay_archive.py` 的 `KEEP_OBSERVATIONS=0` 臂，先改传 `keep_observations=False`，否则两臂静默相同。

## 踩过的坑
- 「谁读字段 X」只 grep 顶层 import 会漏函数内 import：`episode_verifier` 对财报题在函数体里 import `financial_report_contract`。这个结论要靠真实存档 A/B 定。

## 已验证
- 新测试 7 条；保留签名、只把行为改回置空时 6/7 红，都红在断言上。
- 全存档只读 A/B（`~/.finance-runtime/reviews/replay-keep-observations-20260925/`）：生产 931 份损失点行全同，开关逐字段等于旧重建，观察值 11603/11603 还原；数字门 17 份解除 22 句、新增 0；复核目录 8 份财报题结构列变，`structural_delta` 全部 True→False。
