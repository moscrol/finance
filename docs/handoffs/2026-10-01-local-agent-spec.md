# 本地 agent 任务书（2026-10-01，harness 优化第 7–17 号提交）

> 给在用户 Mac 上运行的 agent。云端 agent 只能改代码、跑 Linux 测试，碰不到真实知识库、真实 run 存证、模型 API 和 GitHub/Gitea。下面这些只有本地能做。
> 每节都写了：做什么 → 命令 → 验收口径 → 失败怎么办 → 回报什么。**按顺序做；标「需用户决定」的不要自行决定。**

## 0. 背景与硬约束

- 仓库：`~/finance-workspace-private`。远端 `origin` = GitHub，`gitea` = 本地 Gitea（`http://127.0.0.1:3300/...`）。
- 工作树：`/tmp/harness-opt`，分支 `feat/harness-opt-1001`，上面已有第 1–6 号提交。**所有操作都在这个工作树里做**，不要动主工作树的分支。
- Python：只用 `~/finance-workspace-private/.venv-workbench/bin/python`（下文记作 `$P`）。Homebrew 的 python3.14 会被仓库的解释器守卫拒绝。
- **2×2 实验进行中，归另一个 agent 管**。实验结束前：
  - 不合入 main；
  - 不改 `docs/prediction-ledger.md`（只能起草）；
  - 不跑会占用同一模型配额的大批量 eval。
- 不 force push（`AGENTS.md`）。Gitea 有镜像同步，往 GitHub 推之前先确认镜像方向，不要让 Gitea 覆盖 GitHub。
- 补丁来源：云端导出的 `harness-probe-v2.txt`（第 7–17 号，共 11 个）。用户通过 Cmd+A / Cmd+C 复制网页文本给你，**不能下载**。

### 提交清单（第 7–17 号）

| # | 提交 | 类别 | 合入时机 |
|---|---|---|---|
| 7 | fix(scripts): 脚本自己把仓库根加进 sys.path | 工具 | 随时 |
| 8 | feat(probe): 探针按 decide_turn 实际路由计数 | 工具 | 随时 |
| 9 | test: 在 Linux 上精确跳过仅限 macOS 的测试 | 测试 | 随时 |
| 10 | feat(eval): 内容正确性题集（三类 09-29 错误） | 评测 | 随时 |
| 11 | fix(routing): 两家公司没写比较词也走比较题 | 路由 | **实验后** |
| 12 | feat(eval): 内容正确性题集补单位 / 量纲类（+5 题） | 评测 | 随时 |
| 13 | fix(verifier): 短日期掩码不再吞掉带单位的数 | 核验 | **实验后** |
| 14 | fix(verifier): 列表序号剥离不再截断小数和区间 | 核验 | **实验后** |
| 15 | fix(verifier): 字段名里的单位（家数 / 倍 / 点 / 涨幅 / 净买入）+ `numeric_gate_replay_ab.py` | 核验 + 工具 | **实验后** |
| 16 | fix(routing): 题内先行词不再反问 + 口语行情词 | 路由 | **实验后** |
| 17 | fix(routing): 分析题不当定义题 + 题材左邻语法成分 + 调序盘面 + 冻结集 A7 修订 | 路由 + 量具 | **实验后，A7 需用户决定** |

第 3 号（finance_query schema 瘦身）同样是**实验后**才合入。

## 1. 打补丁（幂等）

用户复制好 `harness-probe-v2.txt` 后，执行下面这行。它会跳过已经打过的补丁，冲突时停下：

```bash
cd /tmp/harness-opt && pbpaste > /tmp/hp2.txt && rm -rf /tmp/hp2 && mkdir /tmp/hp2 && git mailsplit -o/tmp/hp2 /tmp/hp2.txt >/dev/null && ok=1 && for f in /tmp/hp2/*; do s=$(sed -n 's/^Subject: \[PATCH[^]]*\] //p' "$f" | head -1); git log --format=%s | grep -qF "$s" || git am -q "$f" || { ok=0; break; }; done && [ "$ok" = 1 ] && git log --oneline -12
```

- **验收**：`git log` 顶部是 `fix(routing): analysis questions are not definitions…`，分支上共 17 个提交。
- **失败**：`git am` 冲突时先 `git am --show-current-patch | head -30` 看是哪一个，然后 `git am --abort`，回报补丁标题和冲突文件。**不要手工改补丁内容。**
- **回报**：`git log --oneline -17` 的输出。

## 2. 在 macOS 上跑相关测试

云端只在 Linux 上跑过全量（18797 passed）。macOS 专属路径（APFS clonefile、zsh、py3.12）只有本地能验。

```bash
cd /tmp/harness-opt && P=~/finance-workspace-private/.venv-workbench/bin/python && $P -m pytest -q -p no:cacheprovider \
  tests/test_market_feature_store_staging_swap.py tests/test_prediction_ledger_status.py \
  intelligence/tests/test_tool_surface_budget.py intelligence/tests/test_market_watch_colloquial.py \
  intelligence/tests/test_comparison_named_pair.py intelligence/tests/test_short_date_quantity_mask.py \
  intelligence/tests/test_field_name_units.py intelligence/tests/test_numeric_gate_replay_ab.py \
  intelligence/tests/test_in_question_antecedent.py intelligence/tests/test_colloquial_finance_routing.py \
  intelligence/tests/test_routing_probe_round3.py intelligence/tests/test_content_correctness.py \
  intelligence/tests/test_frozen_thirty.py intelligence/tests/test_turn_controller.py \
  intelligence/tests/test_query_resolution.py intelligence/tests/test_numeric_note_false_positives.py
```

- **验收**：0 failed。
- 如果时间允许，再跑全量：`$P -m pytest -q -p no:cacheprovider`。Linux 上约 30 分钟。
- **失败**：回报失败用例名和 `-x --tb=short` 的前 40 行。macOS 上若有用例被跳过、而 Linux 上是通过的，也要回报。

## 3. 真实知识库上的路由探针（第 8、11、16、17 号）

云端用的是注入的临时知识库，读数**不可引用**。这一步给出可以引用的读数。

```bash
cd /tmp/harness-opt && P=~/finance-workspace-private/.venv-workbench/bin/python && $P scripts/route_paraphrase_probe.py --json > /tmp/route_probe_after.json && $P scripts/route_paraphrase_probe.py
```

再在基线上跑一次，用作对照（基线是这条分支与 origin/main 的分叉点）：

```bash
cd /tmp/harness-opt && (git worktree remove --force /tmp/fwp-base 2>/dev/null; git worktree add -q --detach /tmp/fwp-base $(git merge-base HEAD origin/main)) && cp scripts/route_paraphrase_probe.py /tmp/fwp-base/scripts/ && cp intelligence/eval/cases/route_paraphrase_v1.jsonl /tmp/fwp-base/intelligence/eval/cases/ && cd /tmp/fwp-base && ~/finance-workspace-private/.venv-workbench/bin/python scripts/route_paraphrase_probe.py --json > /tmp/route_probe_before.json; echo done
```

- **前置检查**：输出里的 `anchor_hits` 必须大于 0，否则说明知识库没加载，读数作废。
- **验收口径**（云端临时知识库上的读数是：clarify 4 → 0，llm_fallback 2 → 0，一致率 0.711 → 0.889）：
  - `clarify_count` = 0；
  - `consistency` ≥ 0.85，且不低于 Mac v1 的 0.733；
  - `llm_fallback_count` 不高于基线。
- **重点核对**：
  - q04：两家公司的改写版应该走 comparison；
  - q05 / q07 / q10：题材是否认出来了。q10「空芯光纤」要看真实知识库的词表里有没有这个词；
  - q14：调序版应该走 market_watch。
- **回报**：两个 JSON 的这几个字段：`anchor_hits / consistency / consistency_by_style / clarify_count / llm_fallback_count / seed_fallback_rate`，再加修后的全部 `mismatches`。

## 4. 数值门禁重放 A/B（第 13、14、15 号）

`scripts/numeric_gate_replay_ab.py` 从真实 run 的 `continuous-episode.json` 还原核验器输入，在两份代码上各跑一遍。

```bash
cd /tmp/harness-opt && P=~/finance-workspace-private/.venv-workbench/bin/python && R="${FORESIGHT_USERS_DIR:-$HOME/finance-workspace-private}" && $P scripts/numeric_gate_replay_ab.py run --runs-dir "$R" --code-root /tmp/fwp-base --out /tmp/a.jsonl && $P scripts/numeric_gate_replay_ab.py run --runs-dir "$R" --code-root . --out /tmp/b.jsonl && $P scripts/numeric_gate_replay_ab.py diff /tmp/a.jsonl /tmp/b.jsonl --limit 200 > /tmp/gate_ab.txt; head -5 /tmp/gate_ab.txt
```

- **前置检查**：
  - `runs=` 必须大于 0。如果是 0，就用 `find ~ -name continuous-episode.json -path '*runs*' 2>/dev/null | head` 找到实际目录，改 `R` 后重跑。
  - `failed=` 应为 0 或很少。不为 0 时回报 `restore-failure` 的原因行，这说明存证格式和还原器对不上，**不要绕过**。
- **验收口径**：
  - 「只在 A 挂」那一栏（修后不再挂待核）：逐条看附带的证据片段，**应全部是对证据的正确复述**。只要出现一条模型自拟的阈值，就是第 15 号的漏洞，必须回报原句和证据。
  - 「只在 B 挂」那一栏（修后新挂待核）：应全部是证据里没有的数，来自第 13、14 号的日期掩码和序号修复。如果有一条其实是正确复述，就是误报，同样回报。
- 另外跑文本侧的对照：`$P scripts/date_mask_ab.py --runs-dir "$R" --limit 50`。
- **回报**：`/tmp/gate_ab.txt` 的前 5 行（计数），两栏各抽 10 条（不足 10 条就全部），以及你判定为异常的全部条目。

## 5. 内容正确性题集（第 10、12 号）——实验结束后再跑

需要调用模型，会占用配额。**实验结束前只做自检**：

```bash
cd /tmp/harness-opt && ~/finance-workspace-private/.venv-workbench/bin/python scripts/content_correctness_eval.py selftest
```

实验结束后：先用 `export --out /tmp/cc_questions.jsonl` 导出题面，用目标模型（弱模型 + harness，以及强模型 ReAct 作对照）答完，整理成答卷 JSONL，再跑 `score --answers <答卷> --json`。答卷格式见 `intelligence/eval/content_correctness.py` 的模块说明。

- **回报**：selftest 结果。实验后再回报两臂的分数。

## 6. 实验结束后的合入顺序

需要用户确认实验已经收口后才能开始。每一步合入之后都重跑第 2 节的测试集。

1. 先合「随时」类：第 7、8、9、10、12 号。
2. 第 3 号（schema 瘦身）。合入后要跑同一个 uq15 臂，对照台账草案 R-20261001-01。
3. 第 11 号（比较题），然后重跑第 3 节探针。
4. 第 13、14、15 号（核验器）。合入前第 4 节的 A/B 必须已经人工看过，而且没有异常。
5. 第 16、17 号（路由）。第 17 号带冻结集 A7 的修订，**等用户对第 7 节第 1 项做出决定后再合**。
6. 全部合入后，跑一次完整的 probe v2 和 uq15 两臂，作为新基线。

走 PR 合入，不要直推 main。推之前确认 Gitea 镜像不会反向覆盖。

## 7. 需用户决定（只汇报，不要自行处理）

1. **冻结 30 题集 A7-mainline 修订**：`required_outputs` 由 `direct_definition` 改为 `direct_answer`。原值是当年误判钉住的（「…主线是什么」被判成定义题）。如果用户要求保持原样，就把 `intelligence/services/query_understanding.py` 里 `_ANALYSIS_SUBJECT_TAIL_RE` 的「主线」去掉，同时还原这一条。
2. 分支 `feat/tool-usage-differential-p0-0929` 合不合。
3. `gitea-branch-cleanup.sh`：先 dry-run，给用户看预览，再决定是否执行。
4. **凭据**：聊天里曝光过 Mac 隧道 / MCP 的 URL 和 Bearer token，建议用户吊销并重新生成。不要把任何 token 写进文件。
5. 预测台账：交接文档「建议台账条目」里的 R-20261001-01..03 草案，以及第 13–17 号对应的新条目，要不要写入 `docs/prediction-ledger.md`（实验结束后）。

## 8. 回报格式

按节号逐条回报，每节一个小标题，标明 ✅、❌ 或「跳过（原因）」。贴原始输出，不要只写摘要。云端 agent 需要的关键数字是：

- 第 2 节：passed / failed 数量；
- 第 3 节：修前修后的 consistency / clarify / llm_fallback / anchor_hits，以及修后的 mismatches；
- 第 4 节：runs / restored / failed，disappeared / appeared，以及异常条目。
