# 2026-08-16 观点题 10 题修前/修后对照窗（outlook §4 收据执行交接）

roadmap_ref: 另案（P5 质量战线；`2026-08-16-outlook-question-empty-delivery.md` §4 预注册验收的执行窗）

> 权威版在 `eval/outlook-ten-question-window`（本文件）。Gitea PR **#82**。主 checkout `docs/dsh-absorption-spec` 上的同名文件是未跟踪交接，不要在那条分支提交。

一句话：观点题四层的预注册验收三件——原题 live 回归、10 题修前/修后对照、假数字 live 护栏——收尾质检明说「本收尾不假装做过」，至今无收据。本窗给臂配方、时序闸、题集冻结纪律、度量与收据格式。

## 0. 本分支已落（2026-08-16 14:05）

- Gitea PR **#82** `eval/outlook-ten-question-window` @ `9373f8b8`
- 冻结集 + sha256：`docs/verification/2026-08-16-outlook-ten-question-frozen-set.md` / 夹具 `ac464158a724c6312b373b59a4bae2ebc1f81925b5c6e284e85c22547bc7d608`
- 假数字护栏预注册为机制 (a)：`2026-08-14 中际旭创涨了 19.80%，你怎么看`（DuckDB `300308.SZ` 当日 `pct_chg=2.38`）
- 修前树已重建、**未起 8794**；`GATES.json` 两闸仍 false
- **不要开窗**：长尾窗未收口。`#84` `21dbf6c1` 已合 main（`timeout_asked` 埋点 + R-03/R-04 离线钉），**不是**判断正文修复，不能当第二道闸；8792 仍是 `773b3d7e`，长尾未齐之前不准切。

## 1. 前置条件（两道硬闸，都不满足就不要开窗）

1. **长尾 15 题窗收口**：判定 = `~/.finance-runtime/longtail-ab-20260816/runner.out.log` 末行 `all slots processed` 且 `runs/*.json` 覆盖 95 槽位；8793 sidecar 已停（收口交接 `2026-08-16-longtail-ab-window-closeout.md` §5）。**本机 `pgrep/pkill -f` 对这些进程失明，一律 `ps -p $(cat runner.pid)` 验 argv**。
2. **预算回归处置落地**：`2026-08-16-outlook-verification-budget-regression.md` 的修复已合 main，或分诊结论明确豁免（写明理由）。否则修后臂读数是「四层 ∧ 预算回归」的合成，10 题窗白烧——观点题在 `773b3d7e` 上现在交付不出判断正文，对照只会量出回归本身。

两窗不并行的原因：驱动是串行 live 批，同机并发会互相拉高延迟；本案失败形状恰好是 ~151s 预算敏感型，并发即污染。

## 2. 臂配方

| 臂 | 代码 | 端口 | 说明 |
|---|---|---|---|
| 修前 | `437cd5e9aa1ac2681ef3f990dee01866aec82b5c` | 8794 | 生产观察到空壳缺陷时的快照，评测态 sidecar |
| 修后 | 开窗时的 8792 生产 tip | 8792 | 记录实际 SHA 进收据（≥`773b3d7e`+预算回归处置） |

修前臂搭建（`437cd5e9` 的树已不在原快照目录——12:09 被就地切到 `773b3d7e`，见部署交接）：

1. `git -C /Users/a77/finance-workspace-private worktree add --detach /Users/a77/.finance-runtime/finance-workspace-outlook-pre 437cd5e9aa1ac2681ef3f990dee01866aec82b5c`（**已做**，HEAD=`437cd5e9aa1a…`）
2. 起服务用 `~/.local/bin/start-finance-workbench-outlook-pre`：sed 复写 `--port 8792` → `--port 8794`，以及 `RUNTIME_DIR` / `WORKBENCH_REPO_ROOT` / `PYTHONPATH` → 上述新树；**不**注入 `ASK_LONGTAIL_BASELINE`。数据根 `FINANCE_WS`、users 根不改。
3. 验收：`/api/health` `source_revision=437cd5e9…`、`source_dirty=false`；`/api/health/ready` 全绿（rag_worker prewarm 有过三次撞限史，失败就 kickstart 重试，见部署交接 §3.4）。`frontend_built=false` 的话按 CI `workbench-check` 的 frontend job 构建。本树检出时无 `dist/`。
4. 评测结束即停进程、不进 launchd；worktree 处置写进收据（删或留档均可）。杀进程前 `ps -p` 验 argv。

驱动与隔离：`~/.finance-runtime/outlook-ab-20260816/run_live.py` + 本 worktree `scripts/smoke_workbench_self_use.py`。独立用户 `outlook-ab-0816`、断点续跑、progress.jsonl 留痕。臂→端口 `pre=8794, post=8792`，两臂 revision 断言各自钉死。闸未翻时 runner 直接 refuse。

## 3. 题集冻结（先冻后跑，FREEZE 收据先落）

权威冻结：`docs/verification/2026-08-16-outlook-ten-question-frozen-set.md`。

- 10 题 = 长尾冻结集 outlook 档 L01-L05 原样复用（题面/as_of/来源 run 不改，L01 即原题）+ 新挖 O06–O10。
- 新挖谓词与冻结纪律照 `docs/verification/2026-08-16-longtail-baseline-frozen-set.md`：题面含「你认为 / 你觉得 / 怎么看 / 机会在哪 / 会怎么走」，来源是真实 run 的 report.json，最新分类已翻成 `market_forecast` 的不进集，as_of 避开休市日闸。
- 夹具 + sha256 已落（FREEZE_ONLY）。
- 重复次数：每臂每题 ≥2（原题 L01 = 3）。`nr_outlook=42`。

## 4. 度量与护栏（引用 outlook §4，不放宽）

- 主度量：非空判断正文交付率（不是「有字」——「未取得/证据边界」句不算判断正文）；evidence_bound_rate 修后不降；剥句率。
- 门槛：5pp（DSH/质量战线既有门），两处照旧不放宽。
- 判断句标记：与 `_JUDGE_SYSTEM_PROMPT` 词表逐字一致（「据此判断」「这说明」「这意味着」），共享常量 `ANALYTICAL_MARKERS`，别在收据里另立词表。
- 假数字 live 护栏：**已选 (a)**。F01 题面见冻结收据。跑完如实报告。
- 空壳 vs 诚实缺口判读：沿用长尾权威 handoff §3——无检索时正文明写「未取得」算合规交付，不算空壳。

## 5. 收据

开窗后：`docs/verification/2026-08-16-outlook-ten-question-ab.md`，格式照 bookgap S2 对照收据（worktree `fwp-wt-bookgap-s2`，分支 `bookgap/s2-judge-recheck`）。两臂 SHA、每槽 run_id、原题回归单列一节（§4 条款 1 逐条判定）、假数字护栏结果、5pp 判定、结论（含反例与不确定项）。这份收据落盘即视为 outlook 交接「各自出 docs/verification/ 收据算做完」的闭环。

## 6. 边界 / 不做什么

- 不与长尾窗并行；不动 8792 配置；修前臂不设任何新 ASK_* 开关。
- 不放宽 5pp；不改题集去凑结果——冻结后发现题坏（休市闸/分类漂移）按冻结收据的 dropped 纪律标注，不静默替换。
- 不在 `docs/dsh-absorption-spec` 提交本文件。
