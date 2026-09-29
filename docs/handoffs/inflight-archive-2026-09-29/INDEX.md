# 在途交接归档 · 2026-09-29 夜间盘点

main 上 `docs/handoffs/inflight/` 挂着 20 份交接，对应的分支都没开 PR，最后改动在 08-21~09-24。
这里只归档**代码已确认在 main 上、分支只剩交接文档改动**的 4 份。其余 16 份的分类见 Arena 会话盘点（`finance-repo-triage-0929.md`），需要原作者或用户认领后再处理。分支都保留，没删。

| 交接 | 分支 | 为什么可以归档 | 归档用的版本 |
|---|---|---|---|
| fix-eastmoney-circuit-breaker-0922 | `fix/eastmoney-circuit-breaker-0922` | 文中代码提交 `82ce1bb54` / `b8415a377` / `faa480ec1` 都是 main 的祖先；分支比 merge-base 多出的 2 个提交只改了交接本身 | 分支上的较新版本 |
| fix-local-plan-gate-alignment | `fix/local-plan-gate-alignment` | 代码 `4fbc8c42` 已随 `07d42891c` 进入 main；分支多出的 1 个提交只改交接 | 分支上的较新版本 |
| fix-daily-swap-lock-all-callers | `fix/daily-swap-lock-all-callers` | 文中列的 7 个代码提交（`601db6dd` 等）都在 main；分支多出的 10 个提交只改交接，另外还有一份 `2026-09-14-302132-backfill-prep.md`，一并归档到本目录 | 分支上的较新版本 |
| codex-8792-readiness-closeout-0928 | `codex/8792-readiness-closeout-0928` | 分支已经完全包含在 main 里（0 个独立提交）；文中写明「功能代码经 #948 合入并已部署，此分支只收口文档」 | main 上的版本 |

判断方法：`git merge-base` 之后的 diff 只涉及交接文件，再逐个核对交接里点名的代码提交是否 `--is-ancestor gitea/main`。

## 第二批 · 2026-09-30 00:30 深度核查后归档其余 16 份

第一批之后，对剩下 16 个分支做了两层核查：
1. **逐文件比对**：分支改过的每个文件，拿分支版本去和 main 历史上出现过的每个版本对比。结论：大文件（`continuous_turn_adapter.py`、`episode_protocol.py` 等）经过多次整合合并，分支版本对不上很正常，这一层判断不了。
2. **测试落地核查（主要依据）**：把分支相对 merge-base 新增的 `def test_*` 都取出来，看 main 里还有没有。16 个分支共 1,271 个新增测试，main 里全部找得到；只有 `fix-runtime-evidence-closeout-0920` 的 2 个改成了参数化，换了名字（`test_v1_read_preserves_version_digest...` → `test_legacy_read_preserves_version_digest...(version)`，`test_v2_reader_rechecks_future_classification...` → `test_reader_rechecks_future_classification...`），内容还在。

另外 3 个没有测试的分支：
- `fix-rag-recovery-state-0923`：交接里写着 HOLD 的代码提交 `86543370f` 已经是 main 的祖先。分支上只多出文档，其中 `2026-09-24-rag-integration-and-live-acceptance.md` main 里没有，一并归档到本目录。
- `docs-closeout-workorders-0922`：main 里已经有 24 张 `2026-09-22-*-workorder.md`（分支是 20 张），INDEX 续表 #58–#77 也在 main 里。
- `feat-instruction-migration-agents-md`：3/3 测试在 main；分支唯一没落地的是 `skills/dispatcher/SKILL.md` 的旧版本，main 上已经更新过。

归档时，分支上那份交接比 main 新的，用分支版本；否则用 main 版本。16 个分支都没有开着的 PR，没有工作目录，最后改动都在 08-21 到 09-24 之间。分支全部保留，没删。

| 交接 | 新增测试在 main | 归档用的版本 |
|---|---|---|
| docs-closeout-workorders-0922 | 纯文档（工单已在 main） | 分支（09-24） |
| feat-finance-query-technical-daily | 8/8 | 见提交记录 |
| feat-history-market-anatomy | 110/110 | main |
| feat-instruction-migration-agents-md | 3/3 | main（比分支新） |
| fix-8792-boundary-integration | 66/66 | main |
| fix-8792-boundary-ttl-baseline-0922 | 190/190 | main |
| fix-8792-financial-r6-repair | 164/164 | main |
| fix-8792-readiness-boundaries | 14/14 | main |
| fix-ceiling-required-block-degrade | 10/10（逐文件比对也全部一致） | main |
| fix-citation-numeric-gate-0917 | 7/7 | main |
| fix-financial-comparison-0922 | 178/178 | main |
| fix-financial-ratio-units-0920 | 173/173 | main |
| fix-history-closeout-0920 | 115/115 | main |
| fix-rag-recovery-state-0923 | 纯文档（代码 `86543370f` 已在 main） | 分支（09-24） |
| fix-runtime-contracts-0918 | 113/113 | main |
| fix-runtime-evidence-closeout-0920 | 125/125（2 个换了名） | main |

归档后 `docs/handoffs/inflight/` 只剩 `main.md`。

注意：「测试在 main」说明功能已经落地，但不代表交接里列的每一条待办都做完了。交接里还没勾掉的事项，接手时以现在的 main 为准重新判断。
