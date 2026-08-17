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
