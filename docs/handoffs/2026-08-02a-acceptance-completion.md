# Handoff — 验收 completion loop 收尾完成（2026-08-02a）

**承接**：`2026-08-01e`（28 题 live 基线 checkpoint）。
**未重跑 A/B/C**，全部消费存量 artifact；本段新增的只有对比评审、selector probe
与文档。

---

## 0. 一句话现状

**2026-08-01e 的 6 项待办全部完成**（第 4 项换了 evaluator 来源、第 2 项换了
provider，两处偏差均已在文档正文声明）。B/C 信息量对比 11/18 已评，
`knevo_wins 9 : workbench_wins 2`；selector probe 判 `discriminative` 但 46% 选择
来自确定性回填；决策包只写不实施。**未 push、未合并 main。**

---

## 1. 工作区与 Git

| 项 | 值 |
|---|---|
| 工作 clone | `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17` |
| 分支 | `fix/exposure-ranking-truncation` |
| HEAD | `ca57a08a`（本段唯一新增 commit） |
| 上段 HEAD | `267d1997` |
| push / main | **未 push、未合并、未改 origin/main、未动 8792** |
| 正典题库 SHA256 | `a25c68253a92be536b94d2403ffa010b6cd15a20b7eea581450159cb6444a1c6`（未变） |
| 工作树 | clean |

---

## 2. 逐项完成情况

| # | 待办 | 状态 |
|---|---|---|
| 1 | 不重跑 A/B/C，只消费存量 artifact | ✅ 遵守 |
| 2 | selector live probe + 解读文档 | ✅ 完成（**换 provider**，见 §3） |
| 3 | 生成 B/C Knevo 队列（零模型调用） | ✅ B: eligible 7/missing 1；C: eligible 4/missing 3/ineligible 3 |
| 4 | 独立 evaluator 评 + `validate-comparison` | ✅ 完成（**换 evaluator 来源**，见 §3） |
| 5 | 三份文档 + completion handoff | ✅ 本文件 + 三份 |
| 6 | 决策包只写不实施 | ✅ `docs/decisions/2026-08-02-acceptance-open-decisions.md` |
| 7 | 清缓存全量 pytest / ruff / diff-check / hash / 风险扫描 | ✅ 见 §5 |
| 8 | 本地 commit，不 push 不合并 | ✅ `ca57a08a` |

---

## 3. ⚠️ 两处与计划的偏差（必读）

### 3.1 evaluator 不是 codex exec，是 cockpit 的 gpt-5.6-sol

计划写的是「独立 **Codex** evaluator」。实际用
`http://127.0.0.1:57244/v1` 的 `gpt-5.6-sol`（cockpit 本地代理）。

- **独立性成立**：产品跑 `continuous_glm / glm-5.2`，评审模型与产品无关；
  `evaluator.independent=true`，两份结果均通过 `validate-comparison`。
- **也没有让做分析的 agent 自评**——同样不满足 independent。
- **但不是原计划那条路**，没动 ChatGPT app sidecar。

> ⚠️ **evaluator ≠ reference。** 本段用 cockpit 做的是**评审**（对两份答案打分），
> 不是**参照答案**。参照快照必须是外部 agent 对同一问题的独立作答。
> **拿 evaluator 输出去填参照快照就是伪造**（决策包已写死这条）。

### 3.2 selector probe 文件名按实际日期，不套用计划里的 08-01

计划命令用 GLM，实际用 cockpit，因此产物命名为 `2026-08-02-exposure-selector-
resolution.{json,md}` 而非计划里的 `2026-08-01-*`。**换了模型的 probe 是另一份
artifact，不该冒充原计划那次。**

---

## 4. 结果摘要

### 4.1 B/C 信息量对比（11/18 已评）

| 结果 | 条数 |
|---|---:|
| `knevo_wins` | **9** |
| `workbench_wins` | **2**（B5 跨表交集、C10 多轮一致性） |
| `tie` / `not_evaluated` | 0 / 0 |
| 未评 missing / ineligible | 4 / 3（保持显式，**不得当 0 分**） |

**结构信号**：两场胜仗都是「需要本地精确数据、有唯一答案、可逐项排除」的题；
九场败仗都是「需要广度、因果链、标的分层、催化剂、跟踪信号」的题。多条评审同时
指出参照方有显著无出处细节风险，但按 rubric 可用决策信息仍更多。

> 这与 degrades 归因互相印证：18 条降级里 13 条 `reason_code=validated`（合成成功、
> 校验通过）——**问题在出口的组织与交付，不在检索或合成。**

⚠️ 这是**信息量**轴，不是真值轴。9:2 不等于「产品答错 9 道」。

### 4.2 selector probe：`discriminative`，但要打折

`unique_ordered_lists=4`、`union_size=23`（池 86）、`hallucinated=0`。

**但 46% 的选择来自确定性回填**：

| 意图 | LLM 实选 | 回填 | LLM 占比 |
|---|---:|---:|---:|
| beneficiary | 12 | 0 | 100% |
| **expansion** | **1** | **11** | **8%** |
| margin_elasticity | 5 | 7 | 42% |
| revenue_realization | 8 | 4 | 67% |

最可信的一对是 `beneficiary × margin_elasticity`（RBO 0.213 最低、Top-3 全换），
名单也符合产业直觉（受益选材料/设备端，利润弹性选电池厂）。
**已在决策包提出：单意图回填 >50% 应标 `unjudgeable`，否则回填会伪造分辨率。**

---

## 5. 验证

清缓存（`__pycache__` + `.pytest_cache`）后全量：

```
3991 passed, 15 failed, 3 skipped in 192.47s
```

**这是该分支 HEAD 的首次全量**——2026-08-01e 明确写过「不要沿用上一段的 3927
数字冒充本段结果」，故不与 3927 对比。

15 条按**失败身份**归类（不只比数量）：

| 类别 | 条数 | 说明 |
|---|---:|---|
| 既有环境基线 | 11 | `test_subconscious` 8 + `test_userspace` 3（FORESIGHT/AGENT_MEMORY 本地路径） |
| main 自带回归 | 1 | `test_nightly_script_attempts_l2_before_sync_failure_exit`——main 改了夜跑脚本没同步改测试；**该分支尚无 main 的修复** |
| 本段造成、已消除 | 1 | `test_dry_run_records_exact_source_provenance`：未提交文件使工作树 dirty 而红，`ca57a08a` 提交后**实测转绿**。当前实际红数应为 **14** |
| **既有、此前未被记录** | **2** | `test_acceptance_board` × 2（`cmd_board` 返回 2 而非 0）。实测把本段文件全部挪走后仍红；测试文件最后改动在 07-29。**08-01e 因为没跑全量，这两条从未出现在任何 handoff 里** |

其余检查：

| 项 | 结果 |
|---|---|
| 全仓 ruff | 164 条；**本段零 .py 改动**，全部既有（涉及 70 个文件） |
| `git diff --check` | ✅ 干净 |
| 正典 hash | ✅ `a25c6825…a1c6` 未变 |
| 风险文件扫描 | ✅ 无命中 |
| 新增文件密钥扫描 | ✅ 无命中 |
| `validate-comparison`（落库后重跑） | ✅ B 7 cases / C 4 cases 均通过 |

---

## 6. 产物清单

| 文件 | 内容 |
|---|---|
| `docs/verification/2026-08-02-b-c-acceptance-baseline.md` | B/C 基线 + 信息量对比解读 |
| `docs/verification/2026-08-02-exposure-selector-resolution.md` | selector probe 解读 |
| `docs/verification/2026-08-02-exposure-selector-resolution.json` | probe 原始产物（`artifact_sha256=2b01aee9…`，`code_revision=267d1997`） |
| `docs/verification/2026-08-02-acceptance-{b,c}-knevo-queue.json` | 冻结对比包 |
| `docs/verification/2026-08-02-acceptance-{b,c}-knevo-result.json` | 评审结果（自哈希，绑定 queue） |
| `docs/decisions/2026-08-02-acceptance-open-decisions.md` | 决策包（只写不实施） |

---

## 7. 仍未完成 / 下一步

1. **两条 `test_acceptance_board` 红没修**——本段只做了归因（既有、非本段引入），
   没动代码。它们是这次全量跑出来的**新信息**，值得单独一批。
2. **参照快照仍缺 6 份**（22/28），导致 4 题 `missing`。补齐须走
   `freeze --via` 记录真实来源，禁止伪造。
3. **A8/C6 破封**待用户决策（需连带更换参照快照，见决策包）。
4. **该分支落后 `main` 17 个 commit 且有冲突**——`main` 已在 2026-08-02 合入
   一批（板块快照分代迁移、kb-rag 修复等）。越拖冲突越大。
5. **路由修复未做**：C5 那条「查价题被送进 `theme_analysis` 契约」的根因分析在
   `fix/kb-rag-worker-attribution` 分支的
   `docs/verification/2026-08-02-degradation-taxonomy-95-events.md`，
   涉及的 `task_frame.py` / `task_fulfillment.py` 都在**本分支**上，本段没动。

---

## 8. 刻意不要做的

- 不重跑 A/B/C 来「调到好看」；本批仍是基线收据。
- 不改 `acceptance_cases.json`；A8/C6 破封是用户决策。
- 不把未评（missing/ineligible）当 0 分。
- **不拿 evaluator 输出冒充参照快照。**
- 不把「信息量 9:2」读成「真值答错 9 道」——两条轴独立。
- 不 push、不合并 main、不碰 8792。
