# 独立动态审查终稿 — review-b / mirasim-kimi(k3)

## Spec（边界与规则）

- **候选只读树**: `/Users/a77/.finance-runtime/reviews/pr884-closeout-20260923-04/finance-workspace-private`
- **revision**: `db2605d1b1a6a929d9bac468c84ef6aeaddce9ff`（已用 `git rev-parse HEAD` 核实一致，`git status --short` 为空）
- **运行时审查 baseline**: `da761024ed54c46b8e650d1b86076e1f9d261ed2`（#865前 main，本场的回归对照点）
- **本场负责合同**: C4、C5、C6、C7；C1/C2/C3/C8 一律 NOT_REVIEWED。
- **解释的合同口径**（来自 `docs/agent-product-door.md` 运行底座段，L115–L128 等）：
  - C4：writer 先锁后 load、全程持锁（含暂停的活驱动）、稳定 flock inode（不 unlink/不替换、O_NOFOLLOW）、锁随返回/异常/close 释放；跨进程竞争者经受保护入口（writer/restore/run）不得取得所有权，不得追加事件。该锁是合作式本机锁：不覆盖旧版进程、直接 append/put_state、跨机文件系统。
  - C5：同一运行器实例 run/manual_drive/resume 共用非阻塞控制锁（即使 task_id 不同也拒并发）；单步驱动 step/close 互斥，竞争抛 `EpisodeWriterBusy` 且不把活驱动标成结束；异常清理后顺序复用允许；独立实例并行互不阻塞。
  - C6：inbox/spool 排空、异常、交接、迟到输入、陈旧句柄、close/drain 顺序；仅 at-least-once。
  - C7：task/store/context/outcome/episode 绑定；磁盘精确 stored prefix；错误恢复不得跨 episode。

## Quality

- 环境对照：作者既有 5 个相关测试文件共 **89 passed**（基线绿），证明夹具/环境可用；该结果不作为本场动态通过证据。
- 本人独立探针（断言自编、复用仓内构造夹具 `build_rig`/fixtures，不复制作者结论）：
  - `work/probes/probe_c4_writer_lock.py` + 跨进程子进程 `work/probes/c4_child.py`：**3 passed**。
  - `work/probes/probe_c5_reentry.py`：4 例中 2 passed、2 failed——**两例失败均为我方探针缺陷**（①自旋等待竞态没等到模型在飞；②误以为模型 RuntimeError 会穿透 loop，实际按重试策略结算为 `model_error`，这是符合规格的行为，非产品缺陷）。已就地修补（事件门 + 改用 task_frame_hash 不匹配的穿透异常路径，拆出 `probe_c5_exception.py`），**但被控制器提前切入终稿，修补版从未执行**。
- **撤保护（变异）实验：未执行**。这是本场硬性要求，缺它即不能给 PASS。
- C6、C7：**零动态证据**（探针未写未跑，仅有代码阅读，依规不得以阅读替代动态证据）。

## 逐项合同状态

- **C1 NOT_REVIEWED** — 非本场范围。
- **C2 NOT_REVIEWED** — 非本场范围。
- **C3 NOT_REVIEWED** — 非本场范围。
- **C4 PASS（限本场范围、带限制）** — 动态证据覆盖：跨进程竞争者三入口均被 `EpisodeWriterBusy` 拒绝（C4-1/2/3）、竞争者零追加（C4-4）、锁正常释放后可取（C4-5 反向）、暂停活驱动仍持锁（C4-5/6）、锁 inode 跨会话稳定（C4-7）、符号链接锁路径被 O_NOFOLLOW 拒绝（C4-8）、restore 先锁后 load（持锁时竞争者连 plan 都拿不到）。限制：跨机文件系统、旧版进程直写、真实崩溃窗口不在本场可证范围；缺变异实验佐证。
- **C5 NOT_REVIEWED（覆盖不完整）** — 已证：同 runner 并发 run/第二 drive 拒绝且零副作用（C5-1/2/3，绿）；独立实例并行双双完成（C5-9，绿）。**未证**：step/close 互斥（探针修补后未运行）、异常清理与顺序复用（同上）、resume/回调重入（未探）。
- **C6 NOT_REVIEWED** — 未执行任何独立动态探针。
- **C7 NOT_REVIEWED** — 未执行任何独立动态探针。
- **C8 NOT_REVIEWED** — 非本场范围。

## 实际命令与证据

1. `git rev-parse HEAD && git status --short` → `db2605d…`，工作树干净。
2. 作者回归对照（经外置 wrapper 先设 `u.USERS_DIR` 到 work/users）：
   `python -B work/runpytest.py intelligence/tests/test_episode_writer.py test_episode_writer_reentry.py test_episode_inbox.py test_episode_steer.py test_episode_entry_identity.py --basetemp=work/tmp/bt1 -q` → **89 passed in 7.98s**。
3. `python -B work/runpytest.py probes/probe_c4_writer_lock.py --basetemp=work/tmp/bt2 -q`（cwd=probes）→ **3 passed in 7.41s**。子进程经 `subprocess` 调 `c4_child.py`（writer/restore/run 三模式），结果行 `RESULT <mode> BUSY/ACQUIRED` 由父进程断言。
4. `python -B work/runpytest.py probes/probe_c5_reentry.py --basetemp=work/tmp/bt3 -q` → **2 passed, 2 failed**。首红保留于 `work/tmp/bt3*` 与上文失败摘要；失败归因我方探针（时序假设与重试语义误判），非产品缺陷，未改写已产生的失败记录。

## 缺陷

- **产品缺陷：无已确认项。** C5 两例红为探针自身缺陷；模型异常被结算为 `model_error`/重试而非穿透，与设计文档「重试策略捕获在状态里」一致。

## 限制

- 撤保护变异实验缺失；C5 部分子合同、C6/C7 全部子合同无动态证据 → 依规 **BLOCKED**。
- 真实费用对账、跨机锁、完整崩溃续跑 driver、联网/真实模型均不在本场可证范围。
- C4 的 PASS 仅限「合作式本机 POSIX flock」语义，不承诺防直接 `append/put_state` 绕过。

```json
{"revision":"db2605d1b1a6a929d9bac468c84ef6aeaddce9ff","baseline":"da761024ed54c46b8e650d1b86076e1f9d261ed2","verdict":"BLOCKED","checks":[{"id":"C1","status":"NOT_REVIEWED","evidence":"非本场范围"},{"id":"C2","status":"NOT_REVIEWED","evidence":"非本场范围"},{"id":"C3","status":"NOT_REVIEWED","evidence":"非本场范围"},{"id":"C4","status":"PASS","evidence":"work/probes/probe_c4_writer_lock.py 3 passed（bt2）；跨进程子进程 c4_child.py 三入口均 BUSY、竞争者零追加、暂停驱动持锁、inode 稳定、O_NOFOLLOW 拒符号链接、restore 先锁后 load；作者基线 89 passed 仅作环境对照。限制：仅合作式本机锁，缺变异实验"},{"id":"C5","status":"NOT_REVIEWED","evidence":"probe_c5_reentry.py bt3：同 runner 并发拒绝(C5-1/2/3)与独立实例并行(C5-9)绿；step/close 互斥、异常清理/顺序复用、resume 重入无已执行证据（探针修补版未运行，两例首红为我方探针缺陷，保留于 bt3）"},{"id":"C6","status":"NOT_REVIEWED","evidence":"未执行独立动态探针"},{"id":"C7","status":"NOT_REVIEWED","evidence":"未执行独立动态探针"},{"id":"C8","status":"NOT_REVIEWED","evidence":"非本场范围"}],"issues":[],"limits":["撤保护变异实验未执行","C5 子合同覆盖不完整，C6/C7 零动态证据","真实费用、跨机锁、完整崩溃续跑、真实模型/网络不在本场范围","C4 PASS 仅限合作式本机 flock 语义，不防直接 append/put_state 绕过"],"complete":true}
```
