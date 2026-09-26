# 2026-09-26 存证重放保留结构化观察值（PR #935）

分支 `fix/replay-rebuild-keep-observations-0925`，改动提交 `c9bd7b853`。

## 背景

`scripts/judge_loss_point_replay.py` 是判官修复 01（09-09，b7bf0d941）写的离线回放工具：从
`continuous-episode.json` 重建 contract 与 outcome，用当前代码重跑结构核验，标出首个损失点 L0–L5。
它的 `_rebuild_outcome` 被好几份复核脚本借去做数值门重放（`~/.finance-runtime/reviews/l6-numeric-replay-20260925/`）。

`_rebuild_outcome` 写的是 `_build(AgentEvidence, item, observations=())`，也就是证据的结构化观察值一律置空。
09-09 这样写大概不是有意丢数据：`_build` 把 list 原样转成 tuple，观察值会以 dict 的形态进
`AgentEvidence`，任何 `obs.value` 都会炸，置空是最省事的绕法。当时数值门还不读观察值，代价看不见。
09-21 的 00d35ae80 让数值门读观察值之后，这个绕法就开始让重放与生产分叉。

## 按发现顺序

1. **调用方**：仓内只有 `replay_receipt` 一处；仓外 5 份复核脚本。其中 `diff_replay_archive.py` 的
   `KEEP_OBSERVATIONS=0` 臂直接把 `_rebuild_outcome(payload)` 当「丢观察值」基线，**依赖旧行为**。
   这决定了必须留显式开关，不能静默改默认。
2. **静态查读者**：`verify_episode_outcome` 顶层 import 的模块里没有读 `.observations` 的，
   `_can_semantically_release_partial` 一路也没有。我据此以为首个损失点行不受影响，并写进了第一版提交说明。
3. **存档普查**（一次性 heredoc，没落脚本）：4222 份带 outcome 的存档，31253 条观察值；只有 23 条只有 `subject`、
   12 条值是 bool，全部出自复核目录里的 pytest 夹具，生产存档没有坏条目。有 1128 条整数值。
4. **动态 A/B**（`~/.finance-runtime/reviews/replay-keep-observations-20260925/`）推翻了第 2 步：复核目录
   有 8 份财报题的结构列变了。机制：`episode_verifier.verify_episode_outcome` 对
   `financial_analysis` + `metric_evidence` **在函数体内** import `financial_report_contract` /
   `financial_claim_checks`，`report_binding_gaps` 按观察值核「最近 N 期」的报告期与指标。置空后
   `available` 为空，报「尚无结构化报告期与指标可核对」，槽被判缺。顶层 import 的 grep 看不到函数内 import。
5. 据此把开关贯通到 `replay_receipt` 与 CLI（`--drop-observations`），汇总行标出口径，补了财报题结构
   重放测试，并 amend 了还没推送的第一版提交，改掉那句错话。

## 决策

| 决策 | 选了 | 否了 | 为什么 |
|---|---|---|---|
| 默认值 | 保留观察值 | 默认仍置空、新行为 opt-in | 任务本意就是让数值重放与生产同口径；opt-in 会让不自己补观察值的调用方（`replay_receipt` 本身、`replay_numeric_preflight.py`、`sentence10_quantities.py`）继续错 |
| 旧行为怎么留 | 关键字参数 `keep_observations=False` + CLI `--drop-observations` | 不留；或只留函数参数不进 CLI | 有调用方依赖旧行为（第 1 步）；首个损失点重放自己的输出也变了（第 4 步），旧读数要能从同一入口复现 |
| 坏条目 | 逐条跳过 | 整张卡失败；整份 outcome 报错 | 用户要求容忍；一条坏值不该连坐同卡的好值。判据照搬仓内两个严格加载器（`episode_evidence._atom`、`prior_evidence._original_atom`），只是跳过而不抛 |
| bool 值 | 视为坏条目 | `float(True)=1.0` 收下（生产 `f"{True:g}"` 确实得 `"1"`） | bool 不是量值；两个严格加载器都拒它；只在 pytest 夹具里出现过，生产存档 0 条 |
| 数值串（`"12.5"`） | 视为坏条目 | `float()` 收下 | 同上口径；数值门对 str 做 `:g` 直接抛 `ValueError`，生产若真有这种值会在数值门崩掉，不会当成支撑 |
| 非有限值 / 超大整数 | 跳过（`OverflowError` 单独接） | 收下 | 与严格加载器一致；NaN 支撑不了任何数 |
| 多余键 | 忽略 | 整条拒 | 与 `_build`「多余键丢弃」同口径，向前兼容 |
| 复用仓内加载器 | 不复用，写小函数 | 直接调 `_atom` / `_original_atom` | 那两个要求完整 `asdict(AgentEvidence)` 形状；存档走 `private_agent_evidence`（公开视图 + 观察值 + 历史来源），字段集不同，会整张拒 |
| `history_provenance` | 不动 | 顺手还原成对象 | `private_agent_evidence` 不存 `internal_locator`，还原了也过不了 `_valid_history_identity`；生产存档只有 1 份带历史卡、0 份契约开 `allowed_history_operations`，没有读数受影响；单独做要另想怎么补 locator |
| 仓外复核脚本 | 不改，在交接与 PR 里写迁移方法 | 直接改 `diff_replay_archive.py` | 那是别的会话的复核留档，产物按当时的树记了读数；改了会让记录与脚本对不上 |

## 验证与收据

- 新测试 7 条（`intelligence/tests/test_judge_loss_point_replay.py`），此前这个脚本没有任何测试。
  夹具经 `AgentOutcome.to_dict()` + JSON 写出，与生产存档同形。
- 变异：基线脚本上 7/7 红（收据 `~/.finance-runtime/test-receipts/20260925T155700Z-d844455a-*.json`
  是第一版 5 条测试的变异跑，`dirty_paths` 自证是改过的树）。保留新签名、只把行为改回置空：6/7 红，
  全部红在断言上；唯一绿的是开关等价测试，按设计两臂都空。去掉 float 转换、放行 bool：各只红对应 1 条。
- 全存档 A/B（`ab-rebuild-observations-c9bd7b853.json`，最终头；`-d844455a0.json` 是首跑，行差与门差逐条相同）：
  - 生产 users 根 931 份：损失点行 931/931 同；开关 931/931 逐字段等于旧重建；观察值 11603/11603 还原、坏条目 0；
    数字门 17 份解除 22 句、新增 0。
  - 复核目录 3291 份：8 份财报题结构列变，`structural_delta` 全部 True→False（回到与存证生产结论一致），
    `first_loss` 0 份变；开关 3291/3291；观察值差额 1184 条全在两臂都重建失败的 outcome 里，坏条目 0；
    数字门 11 份（6 份不同稿）解除 16 句、新增 0。
  - L6-T3：首条证据 90 个观察值，旧 0、新 90；数字门点名的 3 句两臂相同。
- **不成立的结论**：「解除 22 句」只说明重放与生产的支撑来源对齐了，不说明那 22 句在语义上是真的；
  它们在生产里本来就没被数字门删（生产一直有观察值）。
- 四叶（python / frontend / e2e / registry-check）在本交接提交之后的 head 上跑，读数见 PR #935 评论。

## 工具沉淀盘点

- 同一排查做了两次（全存档 A/B 跑了首跑和终跑）：仓内可复用件就是本 PR 加的 `--drop-observations`。同一入口加与不加各跑一遍，diff `--json` 输出，就是损失点 A/B。基线脚本对分支脚本的双臂对照只为这次改动服务，留在 review 目录。
- 只在对话里跑过的：存档形状普查（heredoc）。一次性问题，结论已记在上文，不落脚本。
- 门禁的洞：这个脚本此前没有任何测试，已补 7 条并做了变异验证。
- 可迁移模式：「谁读字段」只查顶层 import 会漏函数内 import，已写成
  `~/agent-memory/10_knowledge/who-reads-a-field-grep-misses-function-local-imports.md`。

## 后续

- 要做：`l6-numeric-replay-20260925/diff_replay_archive.py` 在含本修复的树上跑 `KEEP_OBSERVATIONS=0`
  前，改成 `_rebuild_outcome(payload, keep_observations=False)`（旧树上仍用原写法）。
- 不要做：别拿首个损失点重放在财报题上的「结构差异」当新缺陷。09-26 之前的 `structural_delta=True`
  有一部分是置空重建造出来的，要复核先加 `--drop-observations` 对照。
- 不要做：别因为「生产存档没有坏条目」就把跳过改成抛。复核目录里有 pytest 夹具形状的存档，一抛整批重放就停。
