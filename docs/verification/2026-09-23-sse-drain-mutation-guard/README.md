# sse-drains-between-read-commit：存活变异的处置读数（2026-09-23）

工单 #66 决策 3「存活变异合前修」。变异定义在 `scripts/review_probes/publication_mutations.json`
（不在 `research_tail_union_mutations.json`），目标是 `intelligence/api/app.py` SSE 循环里
终态 `run` 帧之前的那次排空读：`if pending: continue` → `if False and pending: continue`。

## 结论先说

- 归因报告（`~/.finance-runtime/reviews/mutation-timeout-attribution-20260922/ATTRIBUTION.md` §3.2）
  给了两个假设：等价变异 / 保护无人看守。**两个都不成立。** 保护一直有人看守——
  `test_sse_drains_delivery_events_before_terminal_run`（`e9bb34c37`，2026-09-18）在变异下必红，
  且 `e9bb34c37` 是 #835 头 `d82cb16b5` 与归因运行 revision `45c1a29df` 的祖先。它只是没有登记进该
  变异的 `targets`，runner 用 `-k` 只跑登记的见证，于是读成「存活」。
- 修法：把这条既有见证登记进 `targets`（`publication_mutations.json` 与本目录的单条子集）。
  另写过一条同交错的新测试（事件落在流读与排空读之间），手工验证变异下红、还原后绿，
  因与既有见证重复而**未提交**。
- 旧见证 `test_sse_drains_commit_event_observed_between_reads` 保留在 `targets` 里：在当前读序
  （先读发布态、再读流、再排空）下它注入的 commit 事件落在常规流读里，看不到排空路径，
  单独留它等于没有见证。

## 两次 runner 读数

runner：`scripts/review_probes/run_extraction_mutations.py`（main 版，180 秒帽、唯一锚点、
sha256 还原校验均未动）。机器负载 55–75、并行多个全量 pytest，`--tests` 用节点 id 只选两条见证，
不跑整文件（整文件 110+ 条在此负载下会撞 180 秒帽）；这样 baseline / restored-full 只证明
「所选见证在改坏前后为绿」，不证明整文件。

### Run 1：出厂 `targets`（只登记旧见证）→ 存活

```
python scripts/review_probes/run_extraction_mutations.py --revision HEAD \
  --definitions docs/verification/2026-09-23-sse-drain-mutation-guard/sse-drain-mutation.json \
  --tests intelligence/tests/test_workbench_api.py::test_sse_drains_commit_event_observed_between_reads \
  --output ~/.finance-runtime/reviews/sse-drain-mutation-guard-20260923/run1-stale-targets
```

- revision `49c73c9a32bc4c2c35213f574d64e0f48ba9af08`（本分支第一格，定义子集 sha256 `c55eca9e…480cb`）
- baseline exit 0 / executed 1 / failures 0
- **red exit 0 / executed 1 / failures 0 → 未击杀**，runner 在 `check_result(red, red=True)` 硬停，`complete=false`
- green exit 0 / executed 1 / failures 0
- app.py sha256 改前 `cbc420399639bbcc90183d3c0c377eea840b068f75503b20ad75239314b700a7`
  → 改后 `682880781e730ae28d94f6ff0c9aecace6d261a204d1ef126f90b22d032a9c8b`
  → 还原 `cbc420399639bbcc90183d3c0c377eea840b068f75503b20ad75239314b700a7`（与改前逐字节相同）
- 硬停后 runner 按设计保留冻结树，已手工 `git worktree remove`

### Run 2：登记既有见证 → 击杀

```
python scripts/review_probes/run_extraction_mutations.py --revision HEAD \
  --definitions docs/verification/2026-09-23-sse-drain-mutation-guard/sse-drain-mutation.json \
  --tests intelligence/tests/test_workbench_api.py::test_sse_drains_commit_event_observed_between_reads \
          intelligence/tests/test_workbench_api.py::test_sse_drains_delivery_events_before_terminal_run \
  --output ~/.finance-runtime/reviews/sse-drain-mutation-guard-20260923/run2-witness-registered
```

- revision `6ecb3f2da1252ddcddab995622839830446ae02e`（定义子集 sha256 `0aa72af5…251b51`）
- baseline exit 0 / executed 2 / failures 0
- **red exit 1 / executed 2 / failures 1**，红的是 `test_sse_drains_delivery_events_before_terminal_run`
  （`assert 'event: report.complete' in …`）→ 击杀
- green exit 0 / executed 2 / failures 0；restored-full exit 0 / executed 2 / failures 0
- `complete=true`，`final_status=""`（冻结树干净），冻结树已由 runner 自行移除
- app.py sha256 改前 / 改后 / 还原与 Run 1 逐字节相同（`cbc42039…` / `68288078…` / `cbc42039…`）

## 不主张什么

- 不主张 publication 套件其余七条的读数有变（本目录只跑这一条）。
- 不改变异定义的锚点、不改 runner、不改产品代码 `intelligence/api/app.py`。
- 两次读数只对上面两个 revision 成立；合入前四叶由主会话在预览树串行跑。
