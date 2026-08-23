# 设计：把 workbench 推到组件质量上限 + 8796 解耦收口

- 日期：2026-08-24
- 状态：Draft v1（审查结论落规格，尚未施工）
- 来源：云端子代理只读排查（模型 `claude-fable-5-thinking-xhigh`）
  - **续跑用的子代理 ID：`079a3f4b-6c91-40ce-969b-22381bcc58ce`**
  - 父会话：先列模型 slug、再经 Task `environment=cloud` 拉该子代理读 Mac trace
- 分诊（Mac 只读实况，08-23/08-24）：
  - `~/.finance-runtime/four-arm-knevo-20260823/`
  - `~/.finance-runtime/trace-diff-spt-tech-med-monday-20260823/`
  - `~/.finance-runtime/trace-diff-spt-ysjs-20260823/`（含 `agent-run-triage-report.md`）
  - `~/.finance-runtime/cutover-20260823-8792-8796.md`
  - 云端仓 `docs/verification/2026-08-21-tracediff-cxo-ceiling.md`（**不是终局**，主犯已换代）
- 相邻：
  - `2026-08-23-publication-and-contract-subtract-design.md`（#346 P0-A/B/C，已合 GitHub `main@8688545b`，已切 8792）
  - `2026-08-21-ceiling-shape-closeout-design.md`（W1 降级保留、W2 契约可满足性、W4 预算）
  - `2026-08-21-tracediff-cxo-ceiling.md`（8-21 判官投影主犯，已拆）
- 端口锚（08-24 01:06 health，会漂，开工先重读）：
  - 8792 = `8688545b` dirty=false（生产 workbench）
  - 8796 = `76ee1e89` dirty=false（解耦超集 + `reading_baseline`，**不是** 8792 的纯开关分身）
- 代码树纪律：禁止在 Mac 主检出 `/Users/a77/finance-workspace-private`（`feat/reading-rules-baseline-batch1`，163 行脏）上改。每单从 **`gitea/main`** 新开 `/Users` 下 worktree，独立分支、独立 PR。

---

## 0. 一句话

相交组件已经够用；当前封上限的是正交 harness 的**残余输出闸**和**契约缺口**。8796 是半解耦：离线开关板成型，live 仍是整包换树，还混着新功能。本 spec 把「先复验、再拆闸、再让 live 能做单变量消融」写成可接单步骤。

人话：后厨菜够，端盘偶尔把整桌掀了；解耦柜有抽屉标签，店里上菜还是换整间厨房。

### 0.1 对用户假设的冻结判定（后续审查不得悄悄改口）

| 命题 | 判定 | 成立条件 |
|---|---|---|
| 组件是相交层，不是 8792/8796 质量差的来源 | **成立** | 供数对照：有色题 8796 66 条 vs 8792 37 条；周一题 8792 已取到药明/恒瑞/沃森 |
| 正交 harness 限制了相对「Agent ReAct 直调组件」的上限 | **部分成立、时效性强** | 8-21 成立（判官整句删真话）；8-23 之后主犯换成判官可用性全损 + 契约缺口 + 预算极限路径 |
| ReAct 全面优于 workbench | **不成立** | 五臂「活工具包 5/5」标了自评偏斜 + 人在回路；ReAct 真增量收窄为「空结果换口径再查」 |
| 8796 完全是 8792 的解耦版 | **不成立（半解耦）** | revision 不同；生产不读开关板；混入 `reading_baseline` |

约束三筛（每条新闸必须填）：拦输入还是输出？模型变强会不会更惨？保下限还是封上限？

---

## 1. 为什么现在做这五单（原因）

### 1.1 主犯已经换代，继续修 8-21 形状是空转

8-21 CXO：判官按投影把 1259 字草稿裁成 437 字，15 个对库为真的数字被整句删。#289 / #298 已拆，B 臂 `run_20260821_164659` 零删句。

8-23 有色 8796：取数更好，判官 provider `RuntimeError` → fail-closed，118 字拒答（`ROOT_CAUSE_CONFIRMED`，`judge_status=unavailable`）。#346 P0-B 修了**谎报**文案，**没有**把「不可用 → 全损」改成有条件放稿。这是今天杀伤最大的输出闸。

8-23 周一科技/医药：信封没覆盖双主语和个股格，端盘曾把质检小票端上桌。#346 P0-A/C 已合已切 8792，但 8-24 A1 两臂仍见 `partial`——合同兑现还没在原题上锁死。

### 1.2 ReAct 不该被当成对手，该被拆成一条可搬规则

Cursor 臂看见空表就改查成交额前排，是人改查询策略。组件天花板是编码时冻住的 f-string，零模型，不是 A/B 对手。产品要追的是「空观察池 → 授权一次 fallback 查询」，不是追齐活工具包措辞。

### 1.3 8796 现在做不了合法消融

自家纪律：同字节同请求若 `answer_sha256` 不同则噪声地板非零；**差量 > 1 的配对禁止因果归因**（`R-20260823-SPTTECH-04` still_pending）。8792/8796 差的是整个 revision bundle + 新功能，不是单开关。继续拿两端口比质量，会得到假证据。

---

## 2. 范围

### 2.1 做

| 单 | 名称 | 类型 | 改代码？ | 切哪口 |
|---|---|---|---|---|
| D0 | P0-C 原题复验 + 8-21 文档补「主犯换代」章 | 审查 | 否（只写验证收据 / 文档补章） | 不切；读 8792 |
| D1 | 判官不可用：有条件放稿 + 事后重判 | 实现 | 是 | 先 8792，8796 另包 |
| D2 | 契约可满足性 + 修后降级保留（W2 / W1 残余） | 实现 | 是 | 先 8792 |
| D3 | 空结果 fallback 查询（ReAct 真增量产品化） | 实现 | 是 | 先 8792 |
| D4 | 8796 解耦收口：拆 PR、任务 D 等价、live 开关 | 基建 | 是（开关接线另单） | **先合 main，再同 rev 开 8796** |

### 2.2 不做

- 不加检索、不追活工具包成稿、不把组件天花板当 runtime。
- 不把裸 `RuntimeError` 整类加进判官放稿白名单（#346 P0-B 已否决；D1 只放「draft 完整 + bindings 完整 + 结构 completed」的 case）。
- 不在脏主树上改；不 `git add -A`。
- 不拿 n=1 有色拒答证「8796 判官更严」。
- 不解封 as-of、空表诚实报缺、口径分歧 fail-closed、合法算术错删句。

---

## 3. 续跑约定（给后续子代理）

后续审查和执行**必须**用同一子代理续跑，避免换人重读 8-21 当终局：

```
Task.resume = 079a3f4b-6c91-40ce-969b-22381bcc58ce
model 已固定为 claude-fable-5-thinking-xhigh（resume 时不要另传 model）
```

每轮开工：

1. Mac 隧道：`python3 /home/ubuntu/rx.py -- 'curl -sS -m 3 http://127.0.0.1:8792/api/health'`（及 8796）。token 只读 `CC_REMOTE_EXEC_TOKEN`，禁止打印明文。
2. 重读本 spec §0.1，不得把已拆的 8-21 投影删句写成现役主犯。
3. 大 JSON 只抽字段：`run_id`、`judge_status`、draft/published 长度、`source_revision`、tools、rejection。禁止 `cat` 整份 `continuous-episode.json`。

---

## 4. D0 — 复验与文档（零产品代码）

### 4.1 原因

#346 已合，但「合入 ≠ 原题锁死」。A1 8-24 仍 partial。8-21 ceiling 文档若不当成历史章，下一位会修已经拆掉的闸。

### 4.2 步骤

1. 在 **gitea/main 树**（或 8792 当前 `source_revision` 树）用 `scripts/workbench_probe.py` 打周一原题（题面抄 `2026-08-23-publication-and-contract-subtract-design.md` §5.1）。字段是 `user` 不是 `user_id`。
2. 锁判别变量 1–3（同一份 P0-C spec）：
   - `subject` 同时有「科技」和「医药」，不得空串；
   - `required_outputs` 含个股观察格（名单 + 代码 + 角色）；
   - 「分析下有色金属…」的 `subject` 不得以「下」开头。
3. 另记 A1「质检降级：部分必答格核验后不完整」是**哪一格**、是否 P0-C 漏网还是新形状。
4. 给 `docs/verification/2026-08-21-tracediff-cxo-ceiling.md` 追加「8-23 主犯换代」短章，指针指到本 spec 与三份 `~/.finance-runtime/trace-diff-*`；**不改** 8-21 原文结论，只标「其后已拆 / 现役主犯见本 spec」。
5. 收据落到 `~/.finance-runtime/test-receipts/` 或 `docs/verification/2026-08-24-p0c-monday-recheck.md`。

### 4.3 完成定义

- 三变量全绿 → D0 过，D2 只收 W2 形状级残余。
- 任一红 → 先补 P0-C，禁止跳去 D3 检索自适应。

---

## 5. D1 — 判官不可用：有条件放稿

### 5.1 原因

这是目前唯一还能把「取数最好的 run」打成全损的闸。保下限的本意是「无人复核不放行」；实效是基础设施抖动 × fail-closed，取数越好损失越大。#346 判别变量 #7 已承认「transient + release_safe 应走已有 `_transient_failure_candidate`」，但明文不把裸 `RuntimeError` 整类加白名单。缺口是：**结构已可机械对账时，仍走 gap 剥盘**。

### 5.2 目标行为

当且仅当同时成立：

- `judge_status == unavailable`
- draft 非空
- bindings 完整（或数字已全部落 StructuredObservation / 散文引用已进注册表）
- 结构 verifier `completed`

则：公开稿保留 draft（或结构-safe 子集），开口为「复核不可用 / 事后重判」，`pending_rejudge=true`。  
否则：仍走 gap，措辞按 #346 #6/#8，禁止「证据不足 / 未完成核验绑定」。

### 5.3 步骤

1. 从 `gitea/main` 开树 `fix/judge-unavailable-conditional-release`。
2. 读 `intelligence/services/episode_semantic_verifier.py` 的 gap 路径与 `_transient_failure_candidate`；对照 P0-B 测试（`test_publication*` / judge honesty）。
3. 实现「四条件放稿」。**不要**把 `exc_class=RuntimeError` 整类加入白名单。
4. 夹具：用有色题形状（66 证 + judge RuntimeError）重放——期望不再是 118 字拒答；谎报回归仍绿。
5. 收集 judge provider 原始错误码（triage 报告缺这份）；n≥3 同形才把「全损率」写入台账结案。
6. 全量 pytest + ruff；只切 8792。8796 等 D4 同 rev 后再复验，禁止用本单证 8796 更严。

### 5.4 台账（开行须逐字抄，不得自拟）

`R-20260824-01`：若 draft+bindings+结构 completed 且 judge unavailable，则公开稿非 gap 拒答，且正文不含「证据不足」「未完成核验绑定」。阈值：同形 n≥3 全过。

替代方案：judge 重试（加时延）、双 judge（成本翻倍）、本单有条件放稿（推荐：结构判官仍托「不编数」下限）。

---

## 6. D2 — 契约可满足 + 修后降级保留

### 6.1 原因

形状 B：mandatory 静态、供给动态，联立无解时模型在「违禁编造」和「缺格被删」间二选一。形状 C：句级错、块级删，post-repair 无二次窗。`R-20260821-05`、ceiling-shape W1/W2 已立项未收口。D0 若发现 P0-C 仍红，本单先让路给补合同。

### 6.2 步骤

1. 独立树 `fix/mandatory-satisfiability`（W2）与 `fix/marker-loss-degrade-keep`（W1），禁止一 PR 混两形状。
2. W2：mandatory capability 运行时不可达 → **降必填**并记账，不要注定 `missing_mandatory_capability`。参考 `2026-08-21-ceiling-shape-closeout-design.md` W2。
3. W1：合法句删后残块保留 + 质检段呈现；语义质量否决对必需块只有降级权。道歉横幅只归全灭闸。
4. 写作轮 20s 地板（#344）已合，本单不重做；只补「修复窗后再删 = 终态」的降级保留。
5. 验收押形状（全量 run 上 marker_loss 物理删块归零 / 不可达必填可观测），不押单题变好。

---

## 7. D3 — 空结果 fallback 查询

### 7.1 原因

这是 ReAct 相对填空天花板的**唯一实质增量**，且可在只读红线内做：不外呼新源，只换已授权工具的查询口径。

### 7.2 目标行为

某个 `required_output` 的观察池为空（预取空表 **且** 首轮工具 0 行）时，Episode 内授权 **恰好一次** fallback：

- 例如题材日线空 → 改查同窗成交额前排 / 涨停映射 / 成分股（具体策略表另附，须 fail-closed：无行仍诚实报缺）。
- 记 `fallback_query=true` + 原查询 + 新查询，便于消融。
- 第二次仍空 → 停，禁止第三轮「再想想」。

### 7.3 步骤

1. 树 `feat/empty-pool-fallback-query`。引导写在 episode 工具/计划层，不写进判官。
2. 正控：预取空 + 首轮空 → 恰好一次换口径，trace 有标记。
3. 负控：首轮已有行 → 零 fallback。
4. 与 D1 解耦：fallback 是供给，放稿是出口，禁止一个 PR。

---

## 8. D4 — 8796 半解耦收口

### 8.1 原因

开关板已经有了：

- 登记表 `intelligence/eval/fixtures/capability_switchboard.json`
- 解析 `intelligence/services/capability_switchboard.py`（未知 id → `UnknownSwitchError`）
- 拧动只在 `scripts/run_capability_switchboard.py`（**生产路径永远不读**）
- 8796 启动器只换 `PYTHONPATH` / `WORKBENCH_REPO_ROOT` / `FORESIGHT_USERS_DIR`

焊死 / 缺口：`structural-verifier` welded；4 谓词有正典无缝；`evidence-layers` contested；解耦增量未合 main；任务 D 等价性尚无跑完收据。

### 8.2 步骤（顺序强制）

1. **拆分支**：`reading_baseline` 新功能一个 PR；「开关板 + 谓词缝 + 离线 runner」一个 PR。禁止再以 8796 超集树当「解耦版」。
2. **任务 D 等价性**（catchup 文档原口径）：冻结题、只比结构字段、差集应为空。收据归档后才讨论 #343 能否合。
3. 两 PR 都进 **同一 `gitea/main` revision** 后，8792 与 8796 **同 SHA** 启动，users_dir 仍可分开。
4. 若要 live 消融：再生产路径读开关板（默认全开 = 今日行为）。每次只关一颗。差量 > 1 禁止归因。
5. 离线 `--all-arms` 继续作为门禁：正控（`offered_schemas` 差集恰好一颗）/ 负控 / 底盘三判据。跑不动的那颗 = 还没解耦干净。

### 8.3 完成定义

- 文档与 health 都承认：8796 = 同 rev 的 sidecar，不是功能超集。
- 至少 1 次「同 SHA、只关 1 个 capability」的 live 或离线收据。
- `structural-verifier` 保持 welded，或另开论证单（本 spec 不授权关掉底盘）。

---

## 9. 总执行顺序

```
D0 复验 ──红──► 补 P0-C ──► 再 D0
         └──绿──► D1 放稿口（现役最大杀伤）
                    │
                    ├─► D2 W2/W1（形状收口，可与 D1 平行但分 PR）
                    └─► D3 fallback（D0 绿之后，勿与 D1 混）
D4 全程可做文档/拆 PR，但 live 消融必须等「同 SHA」
```

建议接单粒度：一次一个 D；续跑同一子代理 ID。

---

## 10. 全局纪律（抄 ceiling-shape，补本单）

1. `/Users` 下从 `gitea/main` 开 worktree；解释器 `.venv-workbench/bin/python`。
2. 交付前 ruff + 全量 pytest；动 webapp 才 pnpm 四连。Gitea 不跑 Actions，本机绿才可合。
3. 变异测试前先 commit。
4. live 探针字段 `user`；烧题查重跑在 gitea/main 树。
5. 部署：worktree 快照 + symlink + `launchctl kickstart`，不用 rsync。
6. 台账行从本 spec 各单「台账」小节逐字抄。
7. pathspec 提交，禁用 `git add -A`。

---

## 11. 验收总表

| 单 | 离线必须 | live 必须（用户点头后） |
|---|---|---|
| D0 | 周一题判别变量 1–3 记录齐全；ceiling 文档有换代章 | 8792 原题三变量全绿 |
| D1 | 有色形状夹具：有稿、无谎报；P0-B 旧测试仍绿 | 同形 n≥3 不再全损拒答 |
| D2 | W1/W2 形状测试 + 变异红对 | 全量 run 上物理删块 / 不可达必填可观测 |
| D3 | 正控一次 / 负控零次 fallback | 空池题 trace 带 `fallback_query` |
| D4 | 任务 D 差集空收据；离线 `--all-arms` 绿 | 同 SHA 两端口；单开关消融差量可解释 |

---

## 12. 给续跑代理的第一句话

> 你是 `079a3f4b-6c91-40ce-969b-22381bcc58ce`。先重读 `docs/superpowers/specs/2026-08-24-harness-ceiling-and-8796-decouple-followup.md`。从 D0 开做。不要改 8-21 主犯结论，不要在脏主树上施工。
