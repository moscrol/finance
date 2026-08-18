# 量纲口径契约 收口派单（Phase 1–4.5 验收 + 未完成清单）

- 日期：2026-08-18 20:30 CST
- 派单人：本轮独立验收方（未参与 Phase 1–4.5 实施，只复算读数）
- 接单人：下一个执行 agent
- 上游派单：`docs/handoffs/2026-08-18-caliber-contract-phase1-3-dispatch.md`
- 设计源：`docs/superpowers/specs/2026-08-18-measured-value-caliber-contract-design.md` §8 实施记录
- 通用规程：`docs/workflows/acceptance-workflow.md`

## 0. 一句话

**上游派单要的 Phase 1 已经独立复算通过（判据 A/B/C/D 我自己跑了一遍，读数在下面）；Phase 2 的判据 I 明确未过；Phase 3/4/4.5 有读数但支撑读数的 artifact 全部没入库；三本台账一处都没回写；六张 PR 一张都没合。本单收口这些，不新增设计。**

---

## 1. 现状盘点 [全部实测]

### 1.1 分支与 PR

`gitea/main = 3af5c81f`。六张 PR 全部 open，head 与分支 tip 一致，**无一合入**：

| PR | 分支 | tip | 叠在 | 内容 |
|---|---|---|---|---|
| #198 | `docs/kc-cde-final-acceptance` | `936289eb` | main（**独立栈**） | 派单 / spec / 分诊 / **改前基线** / 冻结 artifact |
| #199 | `fix/caliber-phase1-scorer` | `165226db` | main | Phase 1 判分器 |
| #200 | `fix/caliber-phase2-cases` | `6517b30b` | #199 | Phase 2 题集 |
| #201 | `feat/caliber-phase3-tool-result` | `82f99b26` | #200 | Phase 3 埋点 |
| #202 | `feat/caliber-phase4-wiring` | `3c2f98a3` | #201 | **Phase 4 产品侧** |
| #203 | `feat/caliber-bound-disclosure` | `ef0e0a3c` | #202 | **Phase 4.5 产品侧** |

**两条栈互不包含**：#198 是纯文档栈，#199–#203 是代码栈。`merge-tree --write-tree` 三向全 rc=0（main+#198、main+#203、#198+#203），**当前无冲突**。

### 1.2 我独立复算的读数

用 `fix/caliber-phase1-scorer` 树对**同一份冻结 artifact** 重算 board，逐题比对**入库的**改前基线（真值列 = markdown 表第 5 列）：

```bash
cd /Users/a77/fwp-wt-caliber-p1
export FORESIGHT_USERS_DIR=/Users/a77/.finance-runtime/live-probe-traceability/users
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY -m intelligence.eval.acceptance board \
  --run /Users/a77/fwp-wt-kc-integ/intelligence/eval/runs/20260818T051630Z.json
```

| 判据 | 我的读数 | 结论 |
|---|---|---|
| **A. B7 转绿** | `B7-volume-sentiment-evolution` ❌ 失败 → ✅ 通过 | ✅ |
| **B. C1 转绿** | `C1-future-date-no-data` ❌ 失败 → ✅ 通过 | ✅ |
| **C. 其余 26 题不变** | **变化题数 = 2**（只有 B7、C1）。改前 通过4/不可判12/失败12 → 复算 通过6/不可判12/失败10 | ✅ |
| **D. 08-15 基线同样只动两题** | B7 ❔不可判→✅、C1 ❌→✅，其余 26 题零变化 | ✅ |

**自证（先证明脚本读到了值，再看结论）**：08-18 基线解析 28 题 / 真值列非空 28；复算解析 28 题 / 非空 28。08-15 同。**解析数不等于 28 就先修脚本**——上游派单最贵的教训是「None 跟 None 比出来的零回归」。

复算输出已入库（不留 `/tmp`）：
- `docs/verification/2026-08-18-caliber-phase1-recheck-board-0818.txt`
- `docs/verification/2026-08-18-caliber-phase1-recheck-board-0815.txt`

### 1.3 四件套（上游要求「只许升不许降」，此前无人报全量）

在 `feat/caliber-bound-disclosure@ef0e0a3c`（整栈 tip）上实测：

| 项 | 基线（main `3af5c81f`） | 整栈 tip | 判定 |
|---|---|---|---|
| ruff | 绿 | `All checks passed!` | ✅ |
| pytest（**全树**） | 5511 passed / 12 skipped | **5554 passed / 12 skipped / 0 failed** | ✅ 升 43 |
| webapp 65 test | 65 | **未跑，但整栈前端改动文件数 = 0** | ⚠ 结构性不受影响 |

pytest 收据：`~/.finance-runtime/test-receipts/20260818T122615Z-ef0e0a3c.json`（`target` = 整树，与 5511 基线同口径；`dirty=true`，脏的两项正是下面 T0 要入库的 run JSON）。

> ⚠ **口径坑，别踩**：`pytest intelligence` 只有 4975 passed，比 5511 少 536。**那不是回归，是 target 范围不同**——5511 基线的 `target` 是整个 worktree 根。比对前先读收据里的 `target` 字段。五个 Phase 的收据 `target` 全是 `intelligence` 或单个测试文件，**没有一份和 5511 同口径**，所以「四件套绿」此前是未验状态。

### 1.4 8792

`/api/health` 实测：`source_revision=3af5c81f959505a0bf751c958c7aa6b2a6344a6e`（= `gitea/main`）、`dirty=false`、`status=healthy`。**本批工作未影响生产链，各 Phase 收据「未切 8792」属实。**

---

## 2. 未完成清单（这就是「有没做完的部分」）

### ❶ 判据 I 未过 —— Phase 2 的核心指标没达标

上游判据：可判子集分母 `16 → ≥22`。实得 **6/15**（新 run 通过 6 / 失败 9 / 不可判 13）。

Phase 2 收据与 spec §8 都如实标注「未过」，没有粉饰。**但诊断指向判据本身**：剩余不可判的主因是 `semantic_required` 与缺 observation，**不是缺日期锚**——而日期锚正是 2.1 修的东西。判据 J（A3 拿到 `12.11`）已过，证明日期确实下达到产品了。

所以这是「修对了但判据设错了」还是「修得不够」，需要裁决。**见 §5 待拍板第 1 条。**

### ❷ Phase 4 / 4.5 在没有记录授权的情况下已经执行

上游派单原文：「**本单不授权动产品代码**」「Phase 4 的启动时机与优先级」列在「需要用户拍板」。

实际 #202 / #203 改了 8 个产品文件：`honesty_gates.py`（+380 行）、`route_table.py`、`answer_model.py`、`turn_controller.py`、`finance_query.py`、`lane_generation.py`、新增 `metric_spec.py`、`research_owner.py`。台账与 spec 里**没有任何一条授权记录**。

这不是说改错了——C3 空表披露、C5 口径不一致确实翻绿了，代码也全绿。**问题是下一个人读派单和读分支会得出相反结论**。合入前必须补一条授权记录（谁、何时、基于什么读数批的）。

绊线 `R-20260818-04` 的措辞是「下一份**自称修「B7 回归」**的 PR 不含产品侧改动」——#202/#203 不自称修 B7，**技术上未被证伪**，别误记成 refuted。

### ❸ 「尺子修好后的真实读数」这份读数**不存在**

上游出口写死的顺序是：Phase 1–3 全绿 → 重跑 28 题 → **那份才是产品真实水平** → 再按它排 Phase 4。

实际只有一份新 28 题 run `20260818T1749Z-caliber-p4`，跑在 **含 Phase 4 产品改动**的树上。后果：

- 没有「纯尺子修好、产品未动」的 28 题读数，**分不开哪些提升来自量具、哪些来自产品**；
- `docs/verification/2026-08-18-kc-final-acceptance.md` 里「28 题冻结集 —— **不通过**」「三题零翻绿，另有一题回归」仍是旧尺子的产物。该文件被任一 caliber 分支改动次数 = **0**，**结论至今没重出**。

### ❹ 支撑全部 Phase 2/3/4/4.5 读数的 artifact 没入库

| 文件 | 大小 | 位置 | 状态 |
|---|---|---|---|
| `20260818T1749Z-caliber-p4.json` | 184 KB | `fwp-wt-caliber-p4/intelligence/eval/runs/` | **untracked** |
| `20260818T2002Z-caliber-p5-c4c5a5.json` | 16 KB | `fwp-wt-caliber-p5/intelligence/eval/runs/` | **untracked** |
| `20260818T2005Z-caliber-p5-c5.json` | 2.4 KB | `fwp-wt-caliber-p5/intelligence/eval/runs/` | **untracked** |

`intelligence/eval/runs/` **没有被 gitignore**（`git check-ignore` rc=1），可以直接入库。

另有 Phase 1/2 收据把复算输出指向 `/tmp/caliber-p1/`、`/tmp/caliber-p2/`（**现在还在，重启即失**）。

> 这正是上游派单在提交前自己抓出来的那个坑（把基线写成 `/tmp/kc/board-0818.txt`）**升了一级重演**：这次丢的不是基线，是唯一的原始证据。worktree 一删，Phase 2/3/4/4.5 的所有读数就再也复算不了。
> 只有 `docs/verification/2026-08-18-caliber-p4-board.txt` 已入库——**看板在、原始 run 不在**，能读结论不能重算。

### ❺ 三本台账一处都没回写

上游要求「台账每 Phase 一行」。实测三个文件被 caliber 代码栈改动次数均为 **0**：

| 台账 | 现状 |
|---|---|
| `docs/handoffs/inflight/main.md` | 最新仍是 **14:05** 那行（「派单已出」）。Phase 1–4.5 **零行** |
| `docs/prediction-ledger.md` | `R-20260818-01`..`04` 四条全 `pending`。其中 **R-01 的验证条件我已复核满足**（§1.2），可直接收 `confirmed` |
| `docs/verification/2026-08-18-kc-final-acceptance.md` | 「不通过」结论未重出（见 ❸） |

### ❻ 代码栈的 PR 不自足

冻结 artifact `20260818T051630Z.json`、`docs/verification/baselines/*.txt`、派单、分诊报告**只在 #198**。#199 的判据 A/C 在它自己的 PR 里**复现不了**——Phase 1 agent 当时是跨 worktree 读的文件（我复算时也只能传绝对路径）。

**合入顺序因此不是偏好问题**：#198 必须先合，否则后面任何人（含 CI）都拿不到基线。

---

## 3. 任务分派

### T0 —— 证据入库（阻断项，先做，不做别的）

1. 在各自分支 `git add` §2❹ 三份 run JSON 并提交（先确认不含密钥/绝对路径正文——Phase 3 的脱敏断言已覆盖 `tool_result`，但 run JSON 整体要再扫一遍）。
2. `/tmp/caliber-p1/`、`/tmp/caliber-p2/` 下的 board 输出与变异测试输出复制进 `docs/verification/`，改写两份收据里的 `/tmp` 指针。
3. 收据里每条路径**写行前先 `ls`**。

| 判据 | 通过读数 | 打回条件 |
|---|---|---|
| T0-a | `git ls-tree -r <branch> -- intelligence/eval/runs/` 能列出三份 JSON | 仍 untracked = 打回 |
| T0-b | 五份 Phase 收据里 `grep -c '/tmp/'` = **0** | 还有 `/tmp` 作为唯一来源 = 打回 |
| T0-c | 入库 JSON 里 `grep -c '/Users/'` = 0 | 出现绝对路径 = 打回（红线） |

### T1 —— 按顺序合入，每张合前自己探冲突

顺序**固定**：`#198` → `#199` → `#200` → `#201`。（`#202`/`#203` 见 T3。）

```bash
git fetch gitea
git merge-tree --write-tree gitea/main gitea/<branch>; echo "rc=$?"   # rc=0 才是干净
```

**不要信 Gitea 的 `mergeable`**——上游派单实测十张全报 `true`，实际两张有真冲突。

| 判据 | 通过读数 | 打回条件 |
|---|---|---|
| T1-a | 每张合入前 `merge-tree` rc=0，读数写进台账 | 只贴 `mergeable=true` = 打回 |
| T1-b | #198 合入后 `git ls-tree main -- docs/verification/baselines/` 列出 2 份 | 缺任一份 = 后续判据 C 无从执行 |
| T1-c | #199 合入后，在 **main** 上按 §1.2 命令复算，读数与我的完全一致（变化题数 = 2，且是 B7/C1） | 变化题数 ≠ 2 = 打回并回滚 |

### T2 —— 判据 I 的裁决落地（等 §5 第 1 条拍板后执行）

拍板前**不要**动 overlay 去凑分母。若裁定「判据设错」，就改判据表述并在 spec §8 记明改的理由与改前值；若裁定「修得不够」，Phase 2 打回重做。

| 判据 | 通过读数 | 打回条件 |
|---|---|---|
| T2-a | 判据 I 的新表述与旧表述**并列**写进 spec §8，含「为什么 16→22 这个数当初是怎么估的」 | 直接覆盖旧判据、不留痕 = 打回（那是在为满足指标改指标） |

### T3 —— Phase 4/4.5 的授权补记与合入决定（等 §5 第 2 条）

| 判据 | 通过读数 | 打回条件 |
|---|---|---|
| T3-a | spec §8 或台账出现一条授权记录：谁批的、何时、基于哪份读数 | 直接合 #202/#203 而无授权记录 = 打回 |
| T3-b | 若批准合入：合入后重跑 §1.3 四件套，pytest ≥ 5554 / 12 skipped，target 为**整树** | 用 `pytest intelligence` 的 4975 冒充 = 打回（口径不同） |

### T4 —— 补一份「纯尺子」28 题读数（这是 ❸ 的解法）

在 **`feat/caliber-phase3-tool-result@82f99b26`**（Phase 1+2+3，**零产品改动**）上跑一次 28 题旁路 sidecar：

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY scripts/live_probe.py start-sidecar --port 8796 --repo-root /Users/a77/fwp-wt-caliber-p3
# 等 /api/health 的 runtime.source_revision == 82f99b26 再跑
FORESIGHT_USERS_DIR=/Users/a77/.finance-runtime/live-probe-traceability/users \
  $PY -m intelligence.eval.acceptance run --base http://127.0.0.1:8796 --user live-probe
```

| 判据 | 通过读数 | 打回条件 |
|---|---|---|
| T4-a | sidecar `source_revision` == `82f99b26`，preflight 自然通过 | 用 `--force` 绕过 = 打回。`FORESIGHT_USERS_DIR` 客户端与 sidecar 必须一致，**要修好再跑不是强跑** |
| T4-b | 跑完 run JSON + board txt **双双入库** | 只入库 board = 打回（见 ❹） |
| T4-c | 该读数与 `20260818T1749Z-caliber-p4`（含 Phase 4）逐题对照表入台账，**分离出「量具贡献」与「产品贡献」** | 只报总分不做对照 = 本任务的意义就没了 |
| T4-d | 8792 全程不切；跑完停 8796 | 动了 8792 = 打回 |

### T5 —— 三本台账回写

1. `docs/handoffs/inflight/main.md`：Phase 1 / 2 / 3 / 4 / 4.5 各一行，写明改了什么、判据逐条读数、收据路径（**写行前 `ls`**）。
2. `docs/prediction-ledger.md`：
   - `R-20260818-01` → **`confirmed`**，引用 §1.2 我的独立复算（两份 artifact、变化题数 = 2、自证 28/28 非空）。
   - `R-20260818-02` → 按 T2 裁决收口。J 已过、I 未过，**不要整条打包成 confirmed**。
   - `R-20260818-03` → 按 Phase 3 的 M/N/O 读数收口（M/N 有读数；O 部分解锁：A5 判出 retrieve，C4/C5 无 episode `tool_result` 仍 unknown）。
   - `R-20260818-04` → 判 `held`，并写明理由：#202/#203 是产品侧改动，但不自称修 B7，**不构成 refuted**。
3. `docs/verification/2026-08-18-kc-final-acceptance.md`：等 T4 出数后重出「28 题冻结集」那节的结论，**旧结论保留并标注被哪份读数取代**，不要删。

| 判据 | 通过读数 | 打回条件 |
|---|---|---|
| T5-a | 四条预测的 `outcome` 均离开 `pending`，每条带收据路径 | 仍 `pending` = 打回 |
| T5-b | 旧「不通过」结论在文中可见且标注取代关系 | 直接删改 = 打回（台账不能只留有利读数） |

---

## 4. 合入顺序图

```
#198（基线/artifact，必须最先）
   └→ #199 Phase 1  ──合入后在 main 上复算判据 A–D
        └→ #200 Phase 2  ──等 T2 裁决
             └→ #201 Phase 3  ──合入前先做 T4（纯尺子 28 题）
                  └→ #202 Phase 4    ┐
                       └→ #203 4.5   ┘ 等 §5 第 2 条授权
```

---

## 5. 需要用户拍板（两件，都卡着后续）

1. **判据 I（可判分母 ≥22）实得 6/15，怎么裁？**
   - (a) 认判据设错——诊断显示剩余不可判是 `semantic_required` / 缺 observation，**日期锚已确实下达**（判据 J 过：A3 答出 `12.11`）。改判据、Phase 2 通过。
   - (b) 认修得不够——Phase 2 打回，继续做到分母 ≥22。
   - **我的建议：(a)**，但要求把改判据的理由和改前值一并写进 spec §8（T2-a）。理由：J 是 2.1 的直接因果检验且已过；I 是间接代理指标，当初 `≥22` 这个数没有推导过程。

2. **Phase 4 / 4.5 已经写完了，追认还是回退？**
   - 事实：派单明写不授权动产品代码；#202/#203 改了 8 个产品文件；无授权记录；但代码全绿、C3/C5 翻绿、8792 未受影响。
   - **我的建议：追认并合入，但顺序不变**——先合 #198→#201、先跑 T4 拿到纯尺子读数，再合 #202/#203。这样「产品到底提升了多少」还有得算；反过来先合产品，那份对照就永远做不出来了。

---

## 6. 移交时的已知事实（省得重查）

- `gitea/main` = `3af5c81f`；8792 也钉在这个 revision，`dirty=false`。
- 本仓多 worktree 共享一个 `.git`，`git status` 不足以判断能不能动手，**开工先 `git worktree list`**。
- 测试壳：`umask 022` + `env -i PATH="$PATH" HOME KNOWLEDGE_WIKI`。**PATH 要透传真实值**，我第一次写死成 `/usr/bin:/bin:...` 就把 `test_installed_codex_sandbox_denies_network_and_unix_socket` 跑红了——那是环境没复刻真实环境，不是代码回归。
- 解释器只用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- 比对 pytest 数字前先读收据的 `target` 字段（§1.3 那个 4975 vs 5511 的坑）。
- Gitea API 需登录态（`http://127.0.0.1:3300`，匿名调 `/api/v1` 返 `Only signed in user is allowed to call APIs`）。PR 与分支的对应关系可以用 `git ls-remote gitea 'refs/pull/<n>/head'` 自己解，不必开 API。
