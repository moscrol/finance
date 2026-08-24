# 无主语的市场级问题恢复数值 backfill（2026-08-24）

> 前序：`docs/verification/2026-08-21-w3-numeric-anchor-backfill.md`（W3 / #303）
> 代码：`fix/numeric-backfill-market-scope` @ `3d5d80c2`（基线 `34fcbaaa`）
> 生产 `:8792` **未切**。live 未部署，不得 `confirmed`。

## 0. 一句话

W3 把 `NUMERIC_UNSUPPORTED` 的回填目标改成按 `subject_kind` 反推，`unknown` 一律不回填。
该规则把两档压成一档：**有主语但类型没认出来**（该 fail closed）与**压根没有主语**
（不可能补错）。第二档被一起挡掉的后果不是「缺口留成缺口」，而是市场级问题永远补不到数，
`NUMERIC_UNSUPPORTED` 于是只剩 deletion-only repair 一条出路。

## 1. Before（本单原件）

工件：`linxiaoqi5111` / `run_20260824_160340_773829`（8792，2026-08-24 16:03，
「基于周五的行情，周一该怎么操作」）。

- `contract.subject=None`，`contract.subject_kind='unknown'`，`question_type='general_finance_qa'`
- 模型草稿 4 条操作建议（13 句），`outcome.draft` sha256[:12] = `f6990fc777fd`
- 发布件 `answer.md` 3 条（12 句），sha256[:12] = `1f029e74de5f`
- `repair_cycles=0` / `repair_attempts=0` / `projection_dropped_field_chars=0`，
  却少了 93 字符；`judge_status='repaired'`

### 1.1 因果链（逐环 [实测]，离线复现台）

复现脚本按 `intelligence/services/*` 公开缝调用，不起 server、不调 LLM。
重建的 `TaskFrame.task_frame_hash` 与原件 `bd63fc40…` 逐字节相同（自证重建忠实）。

| # | 环节 | 实测结果 |
|---|---|---|
| ① | `_novel_numeric_condition_indexes(13 句草稿)` | `(6,)` —— **只判第 6 句**「若周一成交额回到 2 万亿以上…」（2 万亿不在证据里，周五实为 18791.51 亿） |
| ② | `plan_issue_backfill(subject_kind='unknown', subject=None)` | `None` —— 补数路死 |
| ③ | 唯一剩余出路 | `_repair()`，docstring 自述 `bounded deletion-only repair` → 第 6 句被删 |
| ④ | 语义判官在**删除后**的 12 句文本上编号 | 其 `第6句`=「跌停家数回升至两位数以上」、`第7句`=「8-26/27 事件 → 科技链波动」，与 `semantic_verifier.issues` 判词逐字对应 |
| ⑤ | 这两句走 `semantic` 分支（`_sentence_in_required_grounded_block`） | 不删、不标（`_annotate_semantic_rejects` 自 #358 起为空操作），仅记 issues + `judge_status='repaired'` |

**净效果：唯一阈值可判的建议被删（2 万亿 vs 周五 18791 亿，线真没到），
恒真的那条留下（周五跌停已 15 家，「回升至两位数以上」签发即成立）。**

## 2. After（离线 A/B）

同一脚本打两棵树，`subject_kind='unknown'` + `subject=None`（run 的真实取值）：

| 臂 | 树 | `missing_capabilities` |
|---|---|---|
| A | `~/.finance-runtime/finance-workspace-34fcbaaa8c93`（部署中） | `None` |
| B | `fix/numeric-backfill-market-scope` | `('market_data',)` |

签名探测（`inspect.signature`）自证两臂确为不同实现，非同一份代码跑两遍。

## 3. 改动边界

只把 unresolved 那一格劈开，其余分支一字未动：

| `subject_kind` | `subject` | before | after |
|---|---|---|---|
| `company` / `stock` | 任意 | `finance_query` | `finance_query`（不变） |
| `market_pattern` / `index` / `external_market` | 任意 | `market_data` | `market_data`（不变） |
| `theme`（已解析但未映射） | 任意 | `None` | `None`（不变，W3 §5 点名） |
| `unknown` / `""` | **非空** | `None` | `None`（不变，R-05 A 臂那一档） |
| `unknown` / `""` | **空** | `None` | **`market_data`** ← 本单唯一变化 |

与 W3 §5 的关系：§5 写「不新造主体分类器」——本单复用 frame 已解析好的 `subject`，
未新增分类逻辑；§5 写「题材 / unknown / 空字符串走 fail closed，不猜 `finance_query`」——
本单不猜 `finance_query`，题材仍 fail closed。W3 全文动机均为防个股污染（R-05），
**「无主语的市场级问题」这一档未被讨论过**，故放开它不与原决策冲突。

## 4. 变异（先 commit 再改已提交态）

| 变异 | 预期变红 | 实测 |
|---|---|---|
| 抽掉 `_UNRESOLVED_SUBJECT_KINDS and not subject` 那一档 | 两条「该补」钉 | ✅ `test_numeric_unsupported_without_any_subject_backfills_market_data` + adapter 同名钉 |
| 调用点不透传 `subject=context.contract.subject` | 「不该补」钉 | ✅ `test_numeric_unsupported_unknown_kind_with_subject_skips_backfill` |
| 放宽成「整个 unknown 都补」 | R-05 守门 | ✅ 3 条（含 `test_r05_a_arm_replay_company_numeric_does_not_plan_market_data` 邻居） |
| 把 `theme` 放进 `_UNRESOLVED_SUBJECT_KINDS` | 题材守门 | ✅ `test_numeric_unsupported_resolved_but_unmapped_kind_stays_fail_closed` |

两个方向都做了：只验「该补的补了」会养出只会放行的假门禁。

## 5. 不做什么

- **不改语义判官的删/标策略。** 第 ④⑤ 环那两句（恒真阈值、事件因果）本单不碰——
  它们走 `semantic` 分支，跟本单的数字门是两条路。
- **不扩数字门正则去抓「两位数」。** 那不是「缺一个数」而是「阈值恒真」，补数补不出来，
  扩正则只会让 backfill 空转。正确判据是**恒真检测**（阈值已被当前证据满足），
  属新判据，另立。
- **不动 #358「公开稿不再盖质检章」。** 存疑句既不删也不标是现行有意决策，本单不翻。
- 不改预算、不部署 8792。

## 6. 复算命令

```bash
# worktree: /Users/a77/finance-workspace-private/tmp/fix-numeric-backfill
umask 022
env -i PATH="/usr/bin:/bin:/usr/sbin:/sbin" HOME="$HOME" \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_episode_issues.py \
  intelligence/tests/test_empty_pool_fallback.py \
  intelligence/tests/test_continuous_turn_adapter.py -q -p no:randomly
```

## 7. 全量门禁

- ruff 全绿
- pre-commit 六道全过（层级审计 ERROR 0；路径字面量 32 文件/47 处，较基线 34/49 下降；
  字段契约 39/96 较基线 40/100 下降；工具可达性 12 声明一致）
- `pytest intelligence/tests` **5665 passed / 2 failed / 11 skipped**

两条 failed 已在**干净 `34fcbaaa`** 上单独复现，与本改动无关：

| 测试 | 干净基线上是否同样红 |
|---|---|
| `test_codex_headless_runtime.py::test_installed_codex_sandbox_denies_network_and_unix_socket` | 是（`git stash` 后复跑，仍红） |
| `test_frozen_thirty.py::test_thirty_set_dry_run_has_no_contract_gaps` | 是（同上） |

## 8. 待验证预测（部署后回填，现为 pending）

见 `docs/prediction-ledger.md` 本日条目 `R-20260824-01` / `-02`。
