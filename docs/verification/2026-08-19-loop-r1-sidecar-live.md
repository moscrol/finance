# Loop R1 sidecar 活性检查（2026-08-19）

> 代码：`gitea/main@88249857`（含 W1–W7 + #241 口径合一 + #242 文档）  
> sidecar：`:8796`，`RAG_WORKER_ENABLED=0`，`WORKBENCH_GROUNDED_PRESENTER=0`  
> **生产 `:8792` 本探针未切。** 实测 `runtime.source_revision=30f98d73`（#240，早于 #241）；账本 20:01 有 `action=startup port=8792`，不是本探针写的。  
> **结论：双引擎 #241 活性过。ask 的 `not_applicable`、episode 的 `repaired` 都没有进判官桶。W6 两行 8796 启动在场。不切 8792。**

第二发 sidecar 启动时工作树有未提交的本文件，`source_dirty=true`；指纹仍是 `88249857` 的 intelligence，脏的是这篇 verification。

## 两发对照

| | 引擎 B ask | 引擎 A episode |
|---|---|---|
| 入口 | `live_probe.py ask` | `POST /api/conversations` → `/messages` |
| 用户 | `loop-r1` | `loop-r1-ep` |
| 题目 | 贵州茅台的股票代码是什么 | 动力电池产业链近况跟踪一下 |
| run | `run_20260819_201858_388670`（105.5s） | `run_20260819_202414_193714`（46.2s） |
| `engine` | `ask` | `episode` |
| `verified_status` | `not_applicable` | `partial` |
| `judge_status` | `not_applicable` | `repaired` |
| `ju` / `cd` | 0 / 3 | 0 / 0 |
| W7 `extract_from_run_dir` | `judge_unavailable=False`，`primary_outcome=degraded` | `judge_unavailable=False`，`primary_outcome=partial` |
| 题型 | ask | `theme_track` / `continuous_episode` |

旧 W7 会把缺 `judge_status` 或 `not_applicable` 抽成 `None` 再记成 100% 判官不可用。两发都没发生。

## 判定

| 条 | 读数 | 结果 |
|---|---|---|
| 被测 rev | 两发 `gate_receipt.rev=882498573bb24ad493e07ea17bbd7b8c6d49d6a8` | 过 |
| W3 双引擎表 | ask 未伪造 `completed`/`passed`；episode 真 `partial` + `repaired` | **过** |
| #241 口径 | 两发 `judge_unavailable_count=0` | **过** |
| W6 启动行 | `state/deploy-ledger.jsonl`：`port=8796` pid `61177`（ask）+ `63107`（episode），rev `88249857` | **过** |
| Track D 接线 | episode `track_contract.missing_outputs=[]`，`ttl_status=current`，`valid_until=2026-09-18`，`baseline_declared=true` | 过（#240 已合，本发只确认还在） |
| sidecar 已停 | 收工时 `:8796` 不在听 | 过 |
| 生产 | 未 bootstrap 8792；8792 仍 `30f98d73` | 过 |

## 本发看见、不当本刀的东西

- ask 三条 AnswerSpec 未绑证据 → `content_degraded_count=3`。问的是代码，图谱段没绑盘面。
- episode 收据 issues 有一条 `numeric_unsupported`；`repair_attempts=1`、`backfill_turns=1`、`repair_cycles=0`。不是阈值题专打 W5 的那一发，也不是纯 `contract_rewrite_candidate`。
- `semantic_verifier_stale=true`：既有形状，不是 #241。

## 不在本发

- W5 阈值题（首轮 `numeric_unsupported` → 开 `market_data`/`financial_data` → completed）
- W7 `--live` N=5
- #240 纯表达缺口、零 required-output 的 contract-rewrite 单独 live（单测已锁）
- 链切 8792

## 产物

- ask：`~/.finance-runtime/live-probe-traceability/loop-r1-88249857/`
- episode：`~/.finance-runtime/live-probe-traceability/loop-r1-88249857-episode/`

## 命令

```bash
git worktree add --detach /Users/a77/fwp-wt-live-loop-r1 gitea/main
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY scripts/live_probe.py ask '贵州茅台的股票代码是什么' \
  --slug loop-r1-ask-code \
  --repo-root /Users/a77/fwp-wt-live-loop-r1 \
  --out-dir ~/.finance-runtime/live-probe-traceability/loop-r1-88249857 \
  --port 8796 --timeout 180 --user loop-r1
$PY scripts/live_probe.py start-sidecar --port 8796 \
  --repo-root /Users/a77/fwp-wt-live-loop-r1 \
  --out-dir ~/.finance-runtime/live-probe-traceability/loop-r1-88249857-episode \
  --user loop-r1-ep
# POST /api/conversations + /messages，题目「动力电池产业链近况跟踪一下」
$PY scripts/live_probe.py stop-sidecar \
  --out-dir ~/.finance-runtime/live-probe-traceability/loop-r1-88249857-episode
```
