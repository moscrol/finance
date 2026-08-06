# Handoff — `source_dirty` 口径不一致（2026-08-06c）

> 给 agent B。你那两条线（`feat/logic-market-match` / `fix/evaluator-scoring`）
> 的报告我核过了，结论在文末。这份是**新任务**：一条真 bug，主树上稳定复现，
> 但在任何新建 worktree 里都是绿的——这就是它藏到今天的原因。

## 0. 一句话

同一个「工作区脏不脏」，生产代码和测试用了**两种不同的 `git status` 口径**，
工作区一旦出现任何未跟踪文件，断言必挂。

## 1. 根因（已定位到行）

```python
# 生产侧  intelligence/services/runtime_provenance.py:55
dirty = bool(_git_output(root, "status", "--porcelain"))              # 含未跟踪文件

# 测试侧  intelligence/tests/test_run_agent_runtime_benchmark.py:515
["git", "status", "--porcelain", "--untracked-files=no"]              # 排除未跟踪文件
```

失败点 `test_run_agent_runtime_benchmark.py:537`：

```
assert payload["source_dirty"] is expected_dirty
E   assert True is False
```

当前触发它的是 `docs/span-io-trace-prd.md`（Devin 2026-08-06 11:54 写的 PRD 草稿，
一直未提交）。**但别把这个文件当根因**——删掉它只是让症状消失，口径不一致还在，
下一个游离文件会再触发一次。

## 2. 为什么三条线都没发现

**未跟踪文件不跟随 worktree。** 今天我和你全程在新建 worktree 里跑测试，那些 worktree
是干净的，这条永远绿；只有在主树跑才会红，而主树整天被 agent A 占着。

这条值得记进方法论：**在 worktree 里跑出来的"全绿"，不覆盖"主树工作区有游离文件"
这个状态**。收尾验证至少在主树跑一次，或者显式造一个未跟踪文件再跑。

## 3. 建议修法（但结论要你自己验）

**倾向改测试去对齐生产，不是反过来。** 理由：`build_runtime_provenance` 的用途是
「记录这次 benchmark 跑在什么代码状态上」，跑的时候工作区有游离文件，**确实不能算
干净的可复现环境**——生产侧含未跟踪文件是更保守也更诚实的口径。把生产改成
`--untracked-files=no` 会让一份 provenance 声称"干净"而实际不干净，那是往回退。

所以建议：测试侧的 `expected_dirty` 去掉 `--untracked-files=no`，与生产同口径。

**动手前请自己确认一遍**：`git grep source_dirty` 还有另外三个消费者
（`eval/ceiling_pit_fixture.py:878`、`scripts/check_rag_readiness.py:84`、
`scripts/run_agent_runtime_benchmark.py:1640`），确认它们期望的语义与"含未跟踪"
一致再动。如果其中某个消费者明确要"只看 tracked 改动"，那就不是改一处的事，
需要把两种语义拆成两个字段。

## 4. 验证方法（必须能复现红→绿）

```bash
# 1. 复现：在主树（工作区有未跟踪文件时）
cd /Users/a77/finance-workspace-private
touch /tmp/x && cp /tmp/x ./_probe_untracked.tmp     # 造一个游离文件
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_run_agent_runtime_benchmark.py::test_dry_run_records_exact_source_provenance -q
# 期望：FAILED  assert True is False

# 2. 修完再跑同一条，期望 passed
# 3. 删掉探针文件后再跑一次，确认两种状态都绿
rm ./_probe_untracked.tmp
```

**这一步是关键**：修完必须在「有未跟踪文件」和「没有未跟踪文件」两种状态下都跑一遍。
只在干净状态验证等于没验证——那正是它藏到今天的原因。

## 5. 顺带：你两条线的基点已经落后

A 的工作已合并进 main（`0b9d9f0d`）。你两条线都基于 `fc7b00a4`，**各落后 6 个提交，
且都还没 commit**（logic-match 7 个文件、evaluator 2 个文件悬在工作区）。

建议顺序：**先把手上两条 commit 掉**（今天已经发生过一次未提交改动被别的线 stash
掉的事故），再考虑 rebase/merge main。A 改的是 `ask.py` 的 fallback 段，你的
logic-match 也改 `ask.py`，**会冲突，但冲突面小且不重叠**（它在 fallback 标签，
你在证据渲染）。

## 6. 你那两条线的核查结论

| 你的说法 | 我的核查 |
|---|---|
| `test_continuous_episode_citations_…` 是顺序污染 flaky | ✅ **对**，我单跑通过 |
| 「第 14 条基线里没记，可能是新出现的」 | ⚠️ 你看到的第 14 条和主树上的第 14 条**是两回事**。主树那条是本文这个 `source_dirty`，你在 worktree 里看不到 |
| P0-2 根因是 `\b` 在中英混排失效 | ✅ **比我 handoff 里的猜测准**。Python 的 `\w` 含中文，「技」和「6」之间没有词边界，`\b` 直接失配。`(?<!\d)\d{6}(?!\d)` 的修法对 |
| 踩中 `_L4_TERMS`（「待确认信号」的「信号」）并改成「未确认线索」 | ✅ 这正是 handoff 预警的那个坑，你自己发现并修了 |
| 四分类描述不拼进证据行、只进题材级结论 | ✅ 这个设计决定比单纯换词更好——从结构上就不会再穿过 `classify_evidence_line` |
| 抽 `classify_market_logic` 纯 seam、不重跑检索 | ✅ 判据仍归原模块单点所有，没复制阈值 |

两条线我都没发现需要返工的地方。**实跑验证仍缺**——你提议重启 canary 跑一轮是对的，
但注意 **8801 现在是 A 的**（cwd 指向主树），要另起 8802 并用独立 worktree，
详见 `2026-08-06-parallel-lines-registry.md`。
