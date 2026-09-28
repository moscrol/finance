# 2026-09-28 · pi 审查沙箱夹具在嵌套 worktree 必红（PR #957，已合 494de8b52）

## 背景

- 症状：从嵌在主检出里的 worktree（`/Users/a77/finance-workspace-private/.claude/worktrees/<name>`）跑 pytest，`tests/test_pi_review_repair.py` 的 6 条 `test_sandbox_preflight_collects_real_author_tests[*]` 和 4 条 `test_real_author_checks_execute_in_sandbox[*]` 必红，都停在 `configure_sandbox()` 的 `assert policy.count(anchor) == 1` → `assert 2 == 1`，anchor 是 venv 父目录 `(literal "/Users/a77/finance-workspace-private")`。同一提交放到主仓外（`~/.finance-runtime/reviews/<x>/tree`）全绿。
- 为什么一直没修：#954 的交接把它记成「嵌套工作树路径的环境红」，第二轮门禁改到主仓外跑；#955 的门禁也是第二轮换到 `~/.finance-runtime/reviews/pr955-gate/tree` 才绿。两次都绕开了，而且大多数会话的门禁树本来就不在主仓里，所以它一直藏着。
- 起因证据：`~/.finance-runtime/reviews/pr955-gate/run1-nested-603a1fd06-*`。那份日志里第 11 条红（`test_pipeline_p0` 飞书门禁）是 603a1fd06 的内容问题，已由 66af2cadd 修掉，与位置无关。

## 按发现顺序

1. 看 junit 里的断言文本：被计数的策略结尾是 `…(literal "/Users/a77/finance-workspace-private/.claude/worktrees"))`，也就是夹具自己换进去的 `sandbox_metadata(tree, folder)` 规则。
2. 同一提交 20d49970a 分别检出到两棵一次性 worktree（嵌套 / 主仓外），只跑这 10 条：嵌套 10 failed（全是 `2 == 1`），主仓外 10 passed。唯一的变量是位置。
3. 两处都把断言前一刻的策略原样打印出来 diff，**只有规则 14 不同**。规则 10（归档策略自带）里的 venv 父目录 literal 是真正的 venv 条目；规则 14 给被测树及其每一级祖先开 stat 权限，树嵌套在主检出下时，主检出本身就是祖先，同一个 literal 于是又出现一次。与 git 元数据无关。
4. 追来历：唯一锚点断言（acee7993f，写的时候被测树总是 tmp 目录）和「真检出当被测树 + 祖先 metadata 规则」（ff62eeeb5）是两条并行分支，09-25 在合并 167c9ffac 的冲突解决里第一次拼到一起（见 `2026-09-25-pr910-main9d5-gates.md`「冲突处理」）。两边各自都没有错。
5. 修夹具，加回归测试，再用变异确认新测试确实抓得住（见下）。
6. 位置对照：修后在两处各跑整个测试文件，各 75 passed，用例 ID 集相同；主仓外新旧夹具写出的 10 份已配置 `tools.sb` 逐字节相同。
7. 四叶都在 PR head 00cb83a78 上、从嵌套会话树跑（原症状位置），全绿（读数见下）。
8. 用户原话「合并」后，经 `gitea_pr.py merge` 合入 494de8b52：父提交为 20d49970a 与 00cb83a78，合入树 == 预览树 05e98c91。

## 决策与被否方案

| 方案 | 评价 | 结果 |
|---|---|---|
| 按 `prepare()` 生成的 metadata 规则切开策略：规则本身断言恰好一次；树路径与 venv 锚点只在其余部分改写，锚点仍各自断言恰好一次；最后按新树重新生成该规则 | 锚点只对准 venv 条目；原来规则没匹配上会静默跳过，现在直接红，断言变强 | **采用** |
| 把 `== 1` 放宽成 `>= 1` | 会把规则 14 里的树祖先一并改写，换解释器时剥掉祖先的 stat 权限；变异实测新测试报 `0 == 1` | 否 |
| `replace(anchor, new, 1)` 只换第一处 | 结果碰巧对，但靠「规则 10 排在规则 14 之前」这个位置假设 | 否 |
| 先换锚点、再换 metadata 规则 | 旧 metadata 规则里也有 `folder` 的祖先，basetemp 落在主检出下时照样撞 | 否 |
| 什么都不改，门禁继续换到主仓外跑 | 两个会话都这么做过，结果就是没人修 | 否 |

新增 `test_sandbox_fixture_rewrites_only_venv_entries_for_nested_tree`：用归档 venv 的父目录合成一个嵌套树路径，并把 `sys.prefix` 换成另一个 venv，断言只有 venv 条目被改写，树祖先条目留在重新生成的规则里。它**与检出位置无关**，也不需要 pi / macOS 沙箱。原来那 10 条只有从嵌套树跑才会暴露问题，而门禁通常不在嵌套树里跑，所以必须另有一条哪里都能抓到的。变异：套在旧夹具上报 `assert 2 == 1`（正是现场症状），套在放宽版上报 `assert 0 == 1`。

## 验证与收据

日志都在 `~/.finance-runtime/reviews/pi-anchor-0928/`。

| 读数 | 位置 / 提交 | 结果 |
|---|---|---|
| 10 条目标 | 嵌套 / 20d49970a | 10 failed（`nested-red-20d49970a.log`） |
| 10 条目标 | 主仓外 / 20d49970a | 10 passed（收据 `20260928T123646Z-20d49970-be7a4ea5c9bf.json`） |
| 整个测试文件 | 嵌套 / ef9d5ec67 | 75 passed（收据 `20260928T124154Z-ef9d5ec6-0d39fa57bf44.json`） |
| 整个测试文件 | 主仓外 / ef9d5ec67 | 75 passed（收据 `20260928T124342Z-ef9d5ec6-3a411f9c8d72.json`） |
| python 叶（ruff + 全量） | 嵌套 / 00cb83a78 | 18500 passed / 0 failed / 72 skipped / 2 xfailed，收据 `gate-nlrsi7fD/pytest.json`，`check_test_receipt.py --require-full-scope --expect-revision 00cb83a78 --base-drift-max 5` 判可采信 |
| frontend 叶 | 同上 | lint / typecheck / 125 tests / build 全 0，build 后树干净 |
| e2e 叶 | 同上 | 34 passed / 2 skipped |
| registry-check 叶 | 同上 | 5/5 exit 0 |

合入记录：`merge-record.json`（身份核对、预览树、授权原话「合并」及出处、合后回读）。

这些读数**不能**推出的结论：
- 这次只修了这一处位置依赖。`/tmp` 下的 Codex 沙箱测试是另一类位置红，不在本 PR 范围。
- 嵌套位置全量 0 失败是 00cb83a78 那个时点的读数，只保证当时的 main 如此。

## 后续要做 / 不要做

- **不要**把这个断言放宽，也不要改成「只换第一处」，理由见上表。锚点要改写的只能是 venv 条目，生成的祖先清单每次整条重新生成。
- **不要**再把「嵌套位置稳定复现」的红当环境问题绕开。先看分支里有没有这个修复（`git merge-base --is-ancestor ef9d5ec67 HEAD`）；没有，就是这个老问题，不是你的改动引起的。
- 盘紧时跑全量：一次全量 basetemp 在 `du` 里约 6.1 GB，实际占用约 6–7 GB（这次从 8926 MiB 可用降到最低 2180 MiB，期间另有一个会话也在跑 pytest）。可以用「先让自己退出」的看门狗，脚本在 `leaves-00cb83a78/run-python-leaf.sh`。
- 教训已记入 `.claude/lessons_learned.md`「位置依赖的测试红」。
