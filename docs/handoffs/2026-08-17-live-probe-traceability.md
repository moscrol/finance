# Handoff：live 探针 trace 化——消掉「自述级收据」

日期：2026-08-17 晚
roadmap_ref：L1-8792
前序：claim-tiering 三发+长电发 live 均为 in-process 黑箱；#148 错账 → #149 更正（直接动因）
本单性质：探针基础设施改造。**不动 8792 生产实例与它的 launchd plist**

## 0. 一句话

现在的 live 探针（`~/.finance-runtime/claim-tiering-20260817/run_live.py`）进程内直调 `answer_query`，不落逐步 trace——收据只能回答「结果是什么」，回答不了「中间发生了什么」。把它升级成能产出可回看中间态的形态，让下一发 live 的任何断言都有一手证据。

## 1. 问题的实证

2026-08-17 长电靶那发：收据 telemetry 只有合成段流式读数（11.8s / 全程 141.7s，检索段 130s 无记录），「superseded 证据进上下文」靠答案正文反推写进台账 #148，次日 trace-first 复核证明为假（`max_evidence=8` 截断，边根本没进），#149 更正。**根因是探针形态：没有中间态，任何结论都只能是推断。**

已知事实（trace-profile.md §1 有账）：

- 逐步 trace（`trace.jsonl`，含 `step_id`、`llm_call_ledger`）只有 **workbench API run** 才写，位置 `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/`（`FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`），同目录还有 `run.json` / `report.json` / `answer.md`。
- in-process 调 `answer_query` 拿到的 `AskResult` 里，`synthesis_messages` / `prepared_synthesis_messages` 只在 `use_llm=True` 时装配；citations 不带 stale 标记；证据行在 LLM 上下文里瞬态存在。
- **lane 差异（关键）**：#146 的降桶标注/绑定闸在 marker lane（`WORKBENCH_GROUNDED_PRESENTER=0`）上，而生产 8792 默认 grounded on。**直接 POST 8792 压不到 marker lane**——这就是历史上探针都用 in-process + `GROUNDED=0` 的原因。

## 2. 方案空间（自选，写清理由；也可组合）

- **A. sidecar 实例 + API + trace.jsonl**：以 `WORKBENCH_GROUNDED_PRESENTER=0` 起一个旁路服务端口，探针改成 POST 提问、收 `run_id`、读 run 目录四件（trace/run/report/answer）。先例：8793/8795 sidecar、canonical 手册里 8794 隔离候选。加分项：`scripts/smoke_workbench_self_use.py` 已有 API 提问骨架可参考。
- **B. run_live.py 增强落盘**：`use_llm=True` 跑完把 `synthesis_messages`（全量 LLM 上下文）、`provider_traces`、citations、warnings 原样写进收据。改动最小、零服务，但拿不到逐步时序，证据等级是「落盘上下文级」而非「trace 级」。
- **C. A+B**：B 保底、A 做正式形态。

## 3. 验收（可判定）

1. 任选一题跑一发样例，产出的收据/产物能**不靠推断**回答三问：哪些证据行进了上下文？模型收到的完整 prompt 是什么？（A 方案另答）每步何时发生、调了什么工具？
2. 特别断言：收据能直接 grep 出「⚠️已被新证据取代」是否在场（这是《2026-08-17-dram-superseded-live-recheck.md》那单的依赖）。
3. 用法文档：本文件补一节或另立 doc，含起停命令、端口、产物路径。
4. 探针代码若进 repo（建议进 `scripts/` 或 `intelligence/eval/`）：走 PR + 本机四件套（`GITEA-USAGE.md` 三行；pytest 必须 **umask 022**，077 会假红 16 个权限位审计）。留在 `~/.finance-runtime/` 下的探针脚本不需要，但要在收据里写明脚本路径与内容 hash。

## 4. 纪律红线

- **不动 8792**（launchd `com.a77.finance-workbench`、快照 `finance-workspace-877e1f721e05`、`~/finance-workspace-runtime` 软链）；sidecar 用独立端口，起服务前 `lsof -iTCP:<port>` 确认空闲（8792/8793/8795/8799/8801 历史上都被用过）。
- sidecar 环境从 `/Users/a77/.local/bin/start-finance-workbench` 取 export（`set -a; . <(grep '^export ' …)`），**只取变量不执行 uvicorn**；密钥全在 Keychain，不落盘、不写进任何脚本。
- sidecar 是一次性验证工具：用完停掉，不装 LaunchAgent，不接夜跑。
- 基线从 `gitea/main` 开分支；`gh` 不可用，PR 走 Gitea API（token：`security find-generic-password -s gitea-local -a a77-token -w`）或网页。
- 避开 `/tmp/finance-8792-live.lock` 存在的时段起大负载（那是对照批的锁）。

## 5. 交付（2026-08-17）

**选型：A 为主、B 作 sidecar 保底。** 不用纯 B：验收第 1 条要逐步时序；公开 `/api/runs/{id}/trace` 会抽空 `input_summary`、把 step 名投影成话术，不能当一手证据。不用会话口 `POST /api/conversations/.../messages`：那是 continuous/grounded 车道，压不到 #146 的 marker lane。

正式形态：

1. 旁路 sidecar，独立端口（默认扫 8796–8820，避开 8792/8793/8795/8799/8801）。
2. 只 `grep '^export '` 生产启动器，**不执行**它的 uvicorn。覆盖 `WORKBENCH_GROUNDED_PRESENTER=0`、`WORKBENCH_PERSIST_LLM_CONTEXT=1`、`RAG_WORKER_ENABLED=0`（不跟 8792 抢 RAG 子进程）。
3. `POST /api/runs` → `_run_ask` → `answer_query`（与旧 in-process 探针同车道）。
4. 读 **磁盘** run 目录：`trace.jsonl` / `run.json` / `report.json` / `answer.md` / `llm_context.json`。`llm_context.json` 是 internal 产物，生产 8792 默认不写。

### 起停与一发

仓库：`/Users/a77/fwp-wt-live-probe`（或合入后的任意 `gitea/main` 检出）。venv：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

```sh
# 确认 8792 对照锁不在、目标端口空闲
test ! -e /tmp/finance-8792-live.lock
lsof -nP -iTCP:8796 -sTCP:LISTEN || true

cd /Users/a77/fwp-wt-live-probe   # 或合入后的工作树
PYTHONPATH=$PWD /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/live_probe.py ask "DRAM怎么看" \
  --slug live-sample \
  --repo-root "$PWD" \
  --port 8796
```

默认问完停 sidecar（`ps -p <pid>` 验 argv 含 `--port 8796`，不用 `pkill -f`）。要留着给 DRAM 复验单接着打：`--keep-sidecar`，停用 `scripts/live_probe.py stop-sidecar --out-dir ~/.finance-runtime/live-probe-traceability`。

只起/只停：

```sh
python scripts/live_probe.py start-sidecar --repo-root "$PWD" --port 8796
python scripts/live_probe.py stop-sidecar
python scripts/live_probe.py inspect ~/.finance-runtime/live-probe-traceability/live-sample
```

### 产物

| 路径 | 内容 |
|---|---|
| `~/.finance-runtime/live-probe-traceability/users/live-probe/runs/<run_id>/` | sidecar 写入的 run 目录 |
| `~/.finance-runtime/live-probe-traceability/<slug>/` | 拷贝的四件 + `llm_context.json` |
| `~/.finance-runtime/live-probe-traceability/<slug>.json` | 收据：`evidence_grade` / `stale_marker_present` / 逐步 `steps` |
| `~/.finance-runtime/live-probe-traceability/sidecar.err.log` | sidecar 日志 |

三问怎么答（不靠答案正文反推）：

1. **哪些证据行进了上下文？** `grep '⚠️已被新证据取代' <slug>/llm_context.json`（`evidence_grade=llm_context` 才算一手）。只在 `answer.md` 出现不够——那是上次 #148 的错法。
2. **模型收到的完整 prompt？** 同文件 `prepared_synthesis_messages`。
3. **每步何时、调了什么？** 磁盘 `trace.jsonl` 的 `started_at`/`finished_at`/`name`；检索源在 completed `ask_retrieve_compose` 的 `retrieval.sources` / `citation_counts`。不要读公开 `/trace` API。

`FORESIGHT_USERS_DIR` 隔离在 `~/.finance-runtime/live-probe-traceability/users`，不写生产 `~/.local/share/finance-workbench/users`。

### 样例（本单验收第 1 条）

- 题：`DRAM怎么看` · `run_20260817_231105_279692` · 159.8s · sidecar :8796 问完已停 · 8792 pid **91312** 未动（`source_revision=877e1f72`）
- 一手 prompt：`live-sample/llm_context.json` 56538 字（system 492 + user 25949），`grounded_presenter=0`
- `grep '⚠️已被新证据取代' live-sample/*` → **不在场**（`evidence_grade=absent`）。这是 grep 结论，不是从答案反推。本发进上下文的是长鑫 R1/R2/R3（20260612/0726/0727），不是 DRAM 靶那两条 superseded 边（20260518/0724）——DRAM 复验单请用它指定的题面。
- 时序：s01 retrieve+compose 23:11:05–23:13:04（graph+wiki，29 条引用）；s03 followups 至 23:13:44
- 收据：`~/.finance-runtime/live-probe-traceability/live-sample.json`
