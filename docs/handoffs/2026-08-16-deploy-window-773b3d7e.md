# 2026-08-16 部署记录：8792 已切 `773b3d7e`（台账已更正；快照卫生待办）

roadmap_ref: L1-8792；关联 L1-R24

> 观测台薄账 PR 收编。不要在 `docs/dsh-absorption-spec` 提交。
> 先例：冲突矩阵 row 8 / PR #70。

一句话：8792 于 12:09 被切到 `773b3d7e`（长尾对照窗需要现状臂=该 tip），但没走 R-24 的「新快照目录 + 链切」流程（在旧目录内就地切树），且切后 rag_worker 挂死约一小时无人发现；13:08 kickstart 修复并补齐三读数验收。台账 `L1-8792` 已改为 `8792=773b3d7e`。

证据等级：**[实测]** = 2026-08-16 当场读过进程/健康端点/git 树。

## 1. 部署事实 [实测]

- 12:09:51 服务重启（launchd `com.a77.finance-workbench`）。符号链 `~/finance-workspace-runtime` **未动**，仍指 `~/.finance-runtime/finance-workspace-437cd5e9aa1a`；该目录内 git 树被就地 checkout 到 detached `773b3d7e73d72ce933b09d11a33fb590c7aa633f`（porcelain 干净）→ **目录名与内容错位**。
- `773b3d7e` 含观点题四层（#72/#75/#79）、perspective #76、长尾注入 #77（默认 off）；落后 `gitea/main` 纯 eval/docs 提交（#78 冻结集、#80 收尾质检等），运行时行为等同 tip。
- 切换动机：长尾 live A/B 的现状臂必须是 `773b3d7e`（冻结收据明写 `do_not_use_as_off_arm: 437cd5e9`），执行归当日 A/B 会话。

## 2. 验收经过 [实测]

- 12:09 切后**没有 ready 验收**：rag_worker prewarm 失败并被 `_STARTUP_FAILURE_TYPE` 钉死，`/api/health/ready` `not_ready`（critical 缺 rag_worker）持续 ~1h。期间 `/api/health` 一直绿——**health 绿 ≠ ready 绿**，R-24 那次 503 的教训重演。12:50 起的 8793 sidecar（同索引）prewarm 成功，说明是切换时段负载/时序问题，不是索引损坏。
- 13:08:50 `launchctl kickstart -k` 同快照重启，t+60s ready 绿。三读数：`source_revision=773b3d7e…`、`source_dirty=false`、`code_matches_repo=true`；`ready` + `rag_worker=true` + `missing_critical=[]`。

## 3. 待办

1. **观测台 PR 更新台账**：**本 PR 已做**。`L1-R24` 行未动（历史准确）。
2. **快照卫生**：目标仍是 `~/.finance-runtime/finance-workspace-773b3d7e73d7`（与现行 8792 同 SHA）。`21dbf6c1d83f` 只是 main tip 停泊，**不要**切过去——#84 自书不切 8792，且不是 10 题第二道闸。顺序：长尾收口 → 停 8793、8792 先不动 → 若做卫生则 `ln -sfn` 到 `773b3d7e73d7` + kickstart + 三读数。**现在不要做**。
3. **回滚梯子**：**已补**。`773b3d7e73d7` @ `773b3d7e`（卫生目标 / 现行锚）；`437cd5e9aa1a-rollback` @ `437cd5e9`（R-24）；`21dbf6c1d83f` @ `21dbf6c1`（停泊，非生产目标）。`outlook-pre` 是 10 题修前臂，不要当生产回滚。
4. **rag_worker prewarm 第三次撞限**：**已记且已决**。不抬 timeout；切后必查 ready，失败 kickstart 同快照一次。收据 `docs/verification/2026-08-16-8792-773b3d7e-inplace-cut.md`。

## 4. 边界 / 不做什么

- 本文件不做任何部署动作；所有链切/kickstart 避开进行中的对照窗。
- 不把 12:09 的切换追认成「R-24 部署窗重开」——那是 A/B 窗的配套操作，台账按第 3.1 条如实记即可。
- 不在 `docs/dsh-absorption-spec` 提交本文件。
- 5pp 门槛不放宽（冲突矩阵 row 10）。杀进程前必须 `ps -p` 验 argv，禁止只靠 `pgrep`/`pkill -f`。
