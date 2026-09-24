# 历史过程研究 completion 分支前向（工单 #68 代码与 PR 部分）· 作者验证证据

分支 `fix/history-completion-fwd-0923`，树 `/Users/a77/fwp-wt-history-fwd-0923`（本单新建，只在这棵树里操作）。
基座 `gitea/fix/history-completion-0922@807a75d88`（8 个 first-parent 提交），前向合并 `gitea/main@626d8a508`
得合并提交 `2d7a5d91f`，再加一个语义冲突修复提交 `907f7e90b`。解释器
`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（3.12.13）。

这份归档不是独立 QC，不是全量门禁：机器 load1 在 14–94 之间波动、磁盘 3.0–20 GiB 之间波动、同机有 10 个以上
别的 pytest 在跑，所有读数都带当时条件；四叶全量由主会话在预览树串行取。原始日志在
`~/.finance-runtime/reviews/history-completion-fwd-20260923/`（不入库）。

## 1. 前向合并：树干净，语义有冲突

```
git merge --no-edit gitea/main            # clean，无冲突标记；parents 807a75d88 + 626d8a508
git diff --name-only gitea/main HEAD | wc -l          # 30（非 docs 29）
git diff gitea/main..HEAD -- scripts/code_map.py tests/test_code_map.py | wc -c   # 0
ruff check $(git diff --name-only gitea/main HEAD | grep '\.py$')                  # All checks passed
```

定向集（下节）在 `2d7a5d91f` 上 **26 failed / 844 passed**，26 条同一根因：
`ValueError: evidence atom fields are incomplete or unknown`（`intelligence/services/episode_evidence.py::_object`，
路径 `put_state → capture_evidence_snapshot → to_recovery_snapshot → from_dict → _atom`）。main 在 `cb16cd463` 之后
用显式字段白名单校验每一条持久化的 `AgentEvidence` 原子（v3 加了 `io_effect`，白名单的注释写明「新增字段必须
让 capture fail closed，直到它的持久化/校验语义被明确选定」）；本分支给 `AgentEvidence` 加了
`history_provenance`（历史原件的不可变来源身份），两边各自成立，合起来每一次 checkpoint 都被拒。

解法按 main 自己引入 v3 的方式（同一提交的说明：「v3 严格持久化 IO 声明；v1/v2 保留原字节与摘要、只推断 unknown」）：

- 快照 schema **v4**：原子字段 = v3 字段 ∪ `{history_provenance}`，值为完整 `HistoricalEvidenceProvenance` 记录或 `None`；
  恢复时走 `HistoricalEvidenceProvenance.from_dict`（拒绝缺键/多键，并重跑 `validate()`），部分或未知形状 fail closed。
- v1–v3 快照保持原字节与摘要，恢复出来的卡 `history_provenance=None`（不推断来源身份）；带来源身份的卡没有无损的旧形状，
  降级写 v≤3 抛 `legacy evidence snapshot cannot preserve history provenance`。
- 测试：版本钉 3→4；`_legacy_payload` helper 现在能复现 v3（去 `history_provenance`）与 v1/v2（再去 `io_effect`）；
  `test_runtime_forward_seams.py` 新增 v4 往返、普通卡显式 `null`、恢复时身份重校验（5 种篡改）、v3 精确性与升级、
  不可静默降级；变异表新增两条部分/非记录 provenance 必拒；缺字段表新增 `history_provenance`。

提交 `907f7e90b`，只动 4 个文件：`intelligence/services/episode_evidence.py`、
`intelligence/tests/test_episode_evidence_snapshot.py`、`intelligence/tests/test_episode_evidence_presentations.py`、
`intelligence/tests/test_runtime_forward_seams.py`。

聚焦读数（修复后，11 个证据/恢复相关文件）：`399 passed in 11.46s`（14:19Z，load1 14.04，磁盘 3.0Gi，收据
`20260923T141942Z-2d7a5d91-44de13737494.json` —— 收据里的 revision 是修复前的 `2d7a5d91` 且 dirty，因为当时修复尚未提交）。

## 2. 定向测试（不是全量）

文件集 = 8 个提交新增/修改的测试文件 ∪ `tests/`、`intelligence/tests/` 下文件名含 `history|historical` 的测试，去重 42 个
（清单 `targeted-files.txt`）。命令：

```
grep . targeted-files.txt | xargs .venv-workbench/bin/python -m pytest -p no:cacheprovider -p no:randomly -q
```

| revision | 读数 | 条件 |
|---|---|---|
| `2d7a5d91f`（合并后、修复前） | **26 failed / 844 passed**，205 s | 13:57Z 起，load 54→67，磁盘 9.4Gi；26 条全是上节的原子白名单错 |
| `907f7e90b`（修复后，干净树 dirty=0） | **870 passed / 0 failed**，53 s，exit 0，收据 `20260923T142302Z-907f7e90-d4c6a48cbcca.json` | 14:22Z 起，load1 15.6→12.0，磁盘 22→24Gi（与修复前同一清单；总数 870 = 844 + 26，说明没有用例被跳过或删除） |

作废的两次尝试（诚实记录，不计读数）：13:51Z 一次 `no tests ran`（zsh 不给 `$FILES` 分词，42 个路径被当成一个参数，留下 0 计数收据
`20260923T135105Z-2d7a5d91-9a501608bf97.json`）；13:53Z 一次 bash 3.2 没有 `mapfile`，数组为空，pytest 无参数跑成了全量，
约 3 分钟后手动 kill，未产生收据。

## 3. `tests/test_code_map.py::test_structure_probe_daily_full`

机制：`code_map.py query` 结构层 → `search_graph()` → `uvx --from code-review-graph code-review-graph search`；子进程非零退出
→ `_graph_hits` 给 `search_failed` → `structure_state="unavailable"` → `hits=[]`，用例只断言命中内容，于是
`assert 'market_feature_store' in '[]'`。本分支对 `scripts/code_map.py`、`tests/test_code_map.py` 的 diff 均为 0 字节。

| 次 | 时间 | load1 | 磁盘 | 读数 | 说明 |
|---|---|---|---|---|---|
| 1 | 13:51:26Z | 80.17 | 9.4Gi | FAILED（21.8 s） | **无效**：图是从主树拷来的 `graph.db`，`code-review-graph search` 拒绝（"built for a different repository root"）→ `search_failed` |
| 2 | 13:51:52Z | 81.22 | 9.5Gi | FAILED（17.1 s） | 同上，无效 |
| 3 | 13:52:12Z | 78.70 | 9.5Gi | FAILED（30.0 s） | 同上，无效 |
| 4 | 13:55:50Z | 70.11 | 9.8Gi | SKIPPED | 拷贝已删除，本树无 `graph.db`，`code_map.py status` = `empty`，用例被 `skipif` 跳过 |

结论：本树取不到工单要求的「有图 + load ≤ 4 + 磁盘 ≥ 8G」读数；图是按仓根绑定的，不能跨树共用；作者树
`~/fwp-wt-history-completion-0922/.code-review-graph/` 已被磁盘清理整目录删除，原始 1F 的条件无法复查。1–3 次的三张收据
（`20260923T1351[52]…Z-2d7a5d91-*.json`）是「拷贝图」的读数，不是环境读数，不要当 1F 复现。低负载读数留给主会话在有本树
构建图的预览树上取；若仍红，`code_map.py` 未被本分支改动这一点已由上面 0 字节 diff 落盘。

## 4. 阳性对照（工单验收项）

在已提交的 `907f7e90b` 上，把 `compare_cases` 的规则型启动判据改回「按结果筛」（未启动窗口直接不进总体，控制组消失），
补丁 `positive-control-mutation.patch`：

```diff
@@ intelligence/services/historical_research/query.py @@
                 status = judged["launch_state"]
+                if status not in LAUNCHED_STATES:
+                    continue  # POSITIVE-CONTROL MUTATION: select by result, controls vanish
                 launch_states[status] = launch_states.get(status, 0) + 1
```

```
rm -rf intelligence/services/historical_research/__pycache__
.venv-workbench/bin/python -m pytest -p no:cacheprovider -p no:randomly -q tests/test_history_launch_control.py
```

| 状态 | 时间 | load1 | 磁盘 | 读数 |
|---|---|---|---|---|
| 变异（dirty=1） | 14:21:30Z | 17.31 | 20Gi | **3 failed / 7 passed**，exit 1：`test_control_windows_are_kept_and_the_denominator_stays_whole`、`test_undecidable_window_is_not_counted_as_a_control`、`test_rule_never_looks_back_before_the_window_it_judges` |
| 还原（`git checkout --`，dirty=0） | 14:21:36Z | 16.80 | 20Gi | **10 passed**，exit 0 |

控制组用例在「按结果筛」下必红、还原后绿，说明 `tests/test_history_launch_control.py` 真的绑住了「控制组留在分母」这条性质。

## 5. 关系表的数据来源

祖先：`git merge-base --is-ancestor <head> HEAD`；独有：`git log HEAD..<head> --oneline | wc -l`；内容命中：对每个非 doc 文件取
`git diff <merge-base> <head>` 的新增行（>12 字符、去注释、去重），数它们在 `HEAD:<同名文件>` 里逐字出现的比例（`grep -Fx -f`，
按唯一行计数）。结果见 PR 正文关系表：#845 两个多出提交仅 docs、`442476f7d` 是祖先；#833 是祖先；#783 98%；#841 71%（2 个测试
文件本树不存在）；#829 70%。

## 6. 没做 / 边界

- 没跑全量、没跑前端与 e2e、没跑真实模型；`test_code_map` 低负载有图读数未取得。
- 收据目录里以 `2d7a5d91` 开头的 5 张收据中，3 张是拷贝图读数、1 张是 0 计数（见上），只有 `…141942Z-…44de13737494.json`
  是有效聚焦读数（dirty，修复未提交时）。
