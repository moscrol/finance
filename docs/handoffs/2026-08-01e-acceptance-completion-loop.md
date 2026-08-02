# Session handoff — 验收 completion loop：28 题 live 基线已跑完（2026-08-01e）

**承接**：`2026-08-01d-harness-noise-and-case-defects.md`。

本段按用户最后的「handoff」指令停在一个完整、可续的 checkpoint：**已经发出的 C 组
run 收束完毕；不再启动 selector live probe、参照评审或新的实现。**

---

## 0. 一句话现状

**A/B/C 共 28 题已经全部各有一次当前基线：正常完成 10、降级完成 18；真值通过 0、
失败 15、不可判 13。C6 正确判为不可复现。Task 1–5 的代码均已本地提交；尚未跑
selector live probe、B/C Knevo 独立比较、最终文档包和全量回归。**

---

## 1. 工作区与 Git

| 项 | 值 |
|---|---|
| 工作 clone | `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17` |
| 分支 | `fix/exposure-ranking-truncation` |
| 当前代码 HEAD | `181c775d`（提交本 handoff/run checkpoint 后以 `git log -1` 为准） |
| push / main | **未 push、未合并、未改 origin/main、未动 8792** |
| 正典题库 SHA256 | `a25c68253a92be536b94d2403ffa010b6cd15a20b7eea581450159cb6444a1c6`（未变） |

本段新增提交：

| SHA | 内容 |
|---|---|
| `bf14a3f2` | 跨 run 逐题聚合、来源列、稳定 `run --output` |
| `5baa86f7` | 送达 / 信息量 / 可信度三轴看板 |
| `7e12b6af` | 哈希绑定 Knevo comparison queue/result + rubric |
| `a12cfdad` | synthesis 结构化 diagnostic、公开 trace、acceptance capture |
| `3e30f7b6` | 修规格审查发现的两项 P1：公开值 fail-closed + 真实 no-messages 路径 |
| `6f296c9b` | selector resolution 指标与冻结候选池 probe CLI |
| `181c775d` | acceptance runner 给 `/context`、`/trace` 正确下传 user |

`a12cfdad` 的独立规格审查曾抓到两项真 P1，均已修：

1. 只白名单键、不严格校验值，畸形 `detail` 可字符串化泄漏 prompt/path；现已按字段
   类型、范围和不安全内容整项 fail closed，并补变异测试。
2. orchestrator 原 guard 会绕过 `no_prepared_messages`；现已让 research/workflow 的
   无消息路径进入纯诊断函数（不会触发模型调用），生产路径测试已覆盖。

---

## 2. 验证到哪里

- Task 4 相关扩大回归：`247 passed`；Ruff 通过。
- Task 5：新测试 `7 passed`，selector/ranking 联合 `25 passed`；Ruff 通过。
- pre-live 聚焦套件：`94 passed`。
- runner user-binding 修复：`68 passed`；Ruff 通过。
- **最新全量 pytest / 全仓 Ruff 尚未跑**；不要沿用上一段的 3927 数字冒充本段结果。
- 正典题库 hash 在 live 前复核未变。

---

## 3. 8793 canary

| 项 | 值 |
|---|---|
| PID | `70568`（交接时仍监听 `127.0.0.1:8793`） |
| cwd | 工作 clone |
| `PYTHONPATH` | 工作 clone |
| backend | `continuous_glm / glm-5.2` |
| RAG | `KB_RAG_PYTHON` + 3 个 `RAG_*`，共 4 项；worker enabled |
| 启动脚本 | `/tmp/start-canary-8793.sh` |

注意两个 provenance 接缝：

1. server 是在 `6f296c9b` 后启动的，实际 Python 导入来自工作 clone；`181c775d` 只改
   runner，不改 server，所以 B/C 无需重启。
2. health 的 `source_revision=0430d544` 来自启动脚本里
   `WORKBENCH_REPO_ROOT=/Users/a77/finance-workspace-private`，不是实际 import root。
   收据必须同时写「health 声明值」与「已核验 cwd/PYTHONPATH/工作 clone HEAD」，不能
   把前者冒充产品代码真值。

**安全提醒**：不要直接输出 `ps eww $PID`，会把进程环境里的凭据带到终端。只用定向
过滤命令验证 `PYTHONPATH` / RAG 变量名或计数，不打印完整环境。任务结束后可
`kill 70568`；不要动 8792。

---

## 4. 三份 live artifact（都只调用一次）

| 文件 | SHA256 | 结果摘要 |
|---|---|---|
| `intelligence/eval/runs/20260801-a2-diagnostic.json` | `12d00d38846584872600345775ec3568dc4744a8887a993116b458b9eedbd34f` | A2 42.3s，降级，7 条证据 |
| `intelligence/eval/runs/20260801-b-midfreq.json` | `a999fe8a86ea435e57b0a6c3bf5bc83f4a3a816fa03180f00a87e46bdf77103f` | B 8/8 完成 |
| `intelligence/eval/runs/20260801-c-longtail.json` | `b35b46b73f1f699b07ee5e575de65e05e438bd5738dcc62c0506df7b2bfe0d15` | C 10/10 完成；C6 不可判 |

### 4.1 A2 的真正诊断

A2 **没有重跑**。首次 runner 写盘时，产品 run 已经有公开 diagnostic/context，但
`_fill_run_detail` 漏传 `user=default`，误写成 `evidence_bound=0`、diagnostic `{}`。

- 原始漏字段 artifact SHA256：
  `5db655ba5198dcb8739dd890e0374a6d9378526f251e308c706b38ecf7aff059`
- 修复 `181c775d` 后，从**同一个**公开 run
  `run_20260802_010641_844570` 离线补齐，未再次调用模型；最终 hash 如上表。

补齐后的结构化真相：

```json
{
  "state": "not_prepared",
  "reason_code": "no_prepared_messages",
  "prepared_message_count": 0,
  "candidate_claim_count": 7,
  "bound_claim_count": 6,
  "evidence_bound": 7
}
```

所以 A2 不是「没证据」也不是「provider 挂了」：证据和大部分 claim binding 都在，
**断在该 route 没准备 synthesis messages**。最终仍是 232 字降级桩，真值失败。

### 4.2 B/C 分账

| 组 | 正常 / 降级 | 真值通过 / 失败 / 不可判 | 送达通过 / 部分 |
|---|---:|---:|---:|
| A | 7 / 3 | 0 / 6 / 4 | 7 / 3 |
| B | 1 / 7 | 0 / 2 / 6 | 1 / 7 |
| C | 2 / 8 | 0 / 7 / 3 | 2 / 8 |
| **合计** | **10 / 18** | **0 / 15 / 13** | **10 / 18** |

看板总口径：

- 28/28 已跑，阻塞 0、未产出 0。
- 可判子集通过率 `0/15`，**不是**“28 题产品通过率”。
- 信息量 comparison 仍是 `0/28 已评`；不要把未评当 0 分。
- 可信度：通过 0、失败 15、不可判 13。
- C6 正确命中 #13 detector：相对时间「最近」+ 冻结到 2026-07-23 的
  `expect_answer_set`，因此不可判，不得算产品红。

结构信号：B/C 大量题有 3–33 条绑定证据却仍降级，说明当前主矛盾是检索后契约/出口
交付，不是单纯“没有检索到”。但本 baseline 后**禁止现场调判官或重跑**。

---

## 5. selector resolution：代码完成，live 尚未跑

模块：`intelligence/eval/selector_resolution.py`。

它冻结一次 `固态电池` 候选池，对四个预声明意图分别选公司，再用纯函数计算：

- Jaccard（集合重合）；
- Top-3 位置变化；
- RBO（Rank-Biased Overlap，头部排名权重更高，`p=0.9`）；
- unique ordered lists / union size；
- hallucinated / backfilled / fallback；
- selected-vs-pool evidence coverage median（**只读，不进排序/prompt**）。

结果只允许 `discriminative / indistinguishable / unjudgeable`；provider fallback 或
hallucination 必须不可判。

下一 agent **只跑一次**：

```bash
W=/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
cd "$W"

export KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki
export FORESIGHT_BUILTIN_LLM_API_KEY="$(security find-generic-password -a a77 -s finance-workbench-glm -w)"
export FORESIGHT_BUILTIN_LLM_MODEL=glm-5.2
export FORESIGHT_BUILTIN_LLM_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4

$PY -m intelligence.eval.selector_resolution probe \
  --concept 固态电池 \
  --output docs/verification/2026-08-01-exposure-selector-resolution.json
```

建议先提交本 checkpoint，使 probe 开始时工作树 clean；probe 在写 output 前冻结
`code_revision`，否则会诚实标成 `-dirty`。

---

## 6. 仍未完成（按顺序续）

1. **不要重跑 A/B/C。** 只消费上面三份存量 artifact。
2. 跑一次 selector live probe，写
   `docs/verification/2026-08-01-exposure-selector-resolution.md` 解读。
3. 生成 B/C Knevo 队列（零模型调用）：

   ```bash
   $PY -m intelligence.eval.acceptance comparison-pack \
     --run intelligence/eval/runs/20260801-b-midfreq.json --agent knevo \
     --output /tmp/acceptance-b-knevo-queue.json
   $PY -m intelligence.eval.acceptance comparison-pack \
     --run intelligence/eval/runs/20260801-c-longtail.json --agent knevo \
     --output /tmp/acceptance-c-knevo-queue.json
   ```

4. 用**独立 Codex evaluator**评 eligible pair，生成 hash-bound result 并跑
   `validate-comparison`。禁止让产品 GLM 自评；missing/ineligible 保持显式。
5. 写：
   - `docs/verification/2026-08-01-b-c-acceptance-baseline.md`
   - `docs/verification/2026-08-01-exposure-selector-resolution.md`
   - `docs/decisions/2026-08-01-acceptance-open-decisions.md`
   - 最终 completion handoff（新建后续编号，不覆盖本 checkpoint）
6. 决策包只写不实施：
   - K：推荐保留 L2 独立 DAG；
   - A8/C6：推荐单独 benchmark version migration 后破封；
   - Codex 快照：重登 ChatGPT app sidecar 后冻结 28 份，禁止伪造；
   - J：基线后单独做确定性正文补写。
7. 清缓存后跑全量 pytest、全仓 Ruff、`git diff --check`、正典 hash、风险文件扫描；
   按**失败身份**对比旧基线，不能只比数量。
8. 本地 commit；**不 push、不合并 main**。完成后再更新项目 memory。

---

## 7. 刻意不要做的

- 不重跑 28 题来“调到好看”；本批是基线收据。
- 不改 `acceptance_cases.json`；A8/C6 破封是用户决策。
- 不把 `validated` synthesis 等同于整题通过；B/C 已证明二者不同。
- 不把绑定证据数当信息量或可信度分数。
- 不生成不存在的 Codex reference snapshot。
- 不在 K 未决前 push，不碰 8792/origin/main。
- 不打印完整进程环境或任何 Keychain 值。

---

## 8. 最小接手检查

```bash
cd /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
git status --short
git branch --show-current
git log -10 --oneline
shasum -a 256 intelligence/eval/cases/acceptance_cases.json
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  -m intelligence.eval.acceptance board
```

预期：分支 `fix/exposure-ranking-truncation`；正典 hash 为 `a25c…a1c6`；看板
28/28 已跑、0 pass / 15 fail / 13 unjudgeable、C6 unjudgeable。
