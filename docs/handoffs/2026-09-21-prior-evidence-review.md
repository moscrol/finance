# 2026-09-21 旧证据恢复、日期误删与 K3 复核决策快照

## 背景

本分支先解决了“明确只用已取得数据，却被错误当成 non_research 拒答”的路由问题，再接通受控原始证据恢复。V3/V4 真实入口证明：恢复输入和零工具可以成立，但模型仍会把成交额占比写成成交增量、把量价扩张当成资金来源区分条件，虚构材料也仍拒答。本快照记录本轮在此基础上完成的工程修复和独立复核，不把工程收据提升成业务质量结论。

## 发现顺序

1. 当前候选 `a4f51112` 全仓收据唯一失败是 `test_agent_episode_no_longer_projects_evidence_ordinals_itself`：`7d0afaff` 的 `_seed_prior_evidence` 在 runtime 内直接导入 `evidence_ordinal_table`。恢复逻辑本身需要 old/new 映射，但职责不应落在 episode loop。
2. 将映射封装为 `prior_evidence.remap_evidence_bindings(snapshot, evidence)`，内部复用协议层唯一编号表；runtime 只调用证据恢复服务。`E2 -> E1` 回归不变，AST 架构断言恢复。
3. V4 `on2` 公开答卷出现“有三处撤回”但只剩两处。定位是数值预检把句首 `9-11` 解析成区间；同句“降级”触发条件后，整句被程序删除。该错误属于传输/程序门，不归因于模型。
4. 日期修复选择句首形状白名单 + 当前绑定证据 `source_date` 月日双条件的局部遮罩。没有扩大日期正则，也没有把所有日期或 `user_premise` 当作数字证据。真实数值条件继续走原门，语义 judge 仍可拒绝。
5. 在独立 detached worktree 用 `kimi-k3` 运行 Spec/Quality 两轴 K3。两份报告均 PASS；Spec 33 项自建探针及 353 项相关测试，Quality 22 项自建探针、331 项相关测试和两次外部副本变异均通过/按预期击穿。
6. 最终候选 `2cfa9d0d` 全仓 pytest `12049P/87S/2X/0F`，Ruff 全仓通过。K3 报告、事件流和执行收据留在 `/Users/a77/.finance-runtime/reasoning-boundaries-20260921/k3-independent/`。

## 决策对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 让 runtime 继续直接调用协议序号函数 | 能工作，但违反已存在的职责断言，恢复逻辑会重新拥有公开投影职责 | 否决 |
| 复制一套 old/new 编号算法到 prior_evidence | 可能消除 import，但会制造第二个编号协议，后续漂移 | 否决；服务只包裹既有唯一表 |
| 扩大 `_DATE_TOKEN_RE` 把所有 `9-11` 视为日期 | 会误放 `9-11倍/元/手` 等数量和区间 | 否决 |
| 所有短日期都跳过数值门 | 未绑定/未知日期可获得无资格豁免，违反 fail-closed | 否决 |
| 只让句首、已绑定 source_date 月日匹配的日期送语义 judge | 修复确定性误删，保留语义裁决和数量门 | 采用 |
| 重跑后覆盖旧 V4 on2 | 会抹掉程序误删的版本证据，无法区分模型与门 | 否决；旧原件永远保留 |
| 将虚构材料全部改成 user_premise | 可能让答案过门，但绕过材料来源与推断正确性 | 否决，继续交给 E2 owner |
| 以 K3 PASS 代替独立语义盲审 | K3 本轮只审代码规格/质量，不审 V4 模型答案 | 否决 |

## 验证与收据

- 分层修复提交：`68949b92`。
- 日期修复提交：`2cfa9d0d`，来源隔离验证提交 `6f935bed`。
- 当前全仓：`~/.finance-runtime/test-receipts/20260920T195644Z-2cfa9d0d.json`，`12049 passed, 87 skipped, 2 xfailed, 0 failed`，dirty=false。
- 当前相关：`~/.finance-runtime/test-receipts/20260920T185948Z-2cfa9d0d.json`，477P；Ruff 全仓 `All checks passed`。
- 日期隔离树相关：338P；移除单位保护 5F，移除日期后缀 lookahead 8F，均在恢复后重跑。
- Spec K3：`k3-independent/spec-k3/REPORT.md`，SHA256 `63e2358d...`，PASS。
- Quality K3：`k3-independent/quality-k3/REPORT.md`，SHA256 `f2ae5448...`，PASS。
- K3 两个 detached tree HEAD 首尾为 `2cfa9d0d`、status 空；作者候选 tree 首尾同样未改。共享 refs 与 agent-memory 指纹在审核时发生并行环境漂移，execution 收据明确记为 false，不能省略此限制。

## 仍不成立的结论

- `K3 PASS` 只说明本次两个提交的规格/工程质量；不说明求证开关产生了稳定收益。
- V4 四臂仍是 `a4f51112` 版本；日期修复后的第一轮真实入口使用“9月11日”全日期，首答仍有“跌停21>涨停40”等错误，不能证明旧 on2 的短日期路径。旧 on2 失败原件必须保留；新 run 不替代独立语义盲审。
- V5 三类真实入口结果已封存：初始/续问分别澄清；最小自然题面进入本地查询但出现“9-18 逆势放量上涨”方向错误；最新句首 run `run_20260921_060912_869656` 第一字符为 `9`，保留目标短日期并绑定 E6(`2026-09-11`)/E5(`2026-09-14`)，目标首句到达真实 judge 后被降级为 issue，另一个带数字候选句仍被数值预检删除。结论是短日期路径证据成立，整篇语义验收不成立。manifest：`/Users/a77/.finance-runtime/reasoning-boundaries-20260921/v5-short-date/MANIFEST.json`，SHA256 `8142bec5b5213693bc2c97d3354345fb7ae488877621d2443b9fa63d02b8a387`。
- 四臂同源 judge、0工具和 completed/repaired 不能构成独立语义复核。Grok 因 read-only sandbox socket symlink 故障失败，Codex 因 code-mode host/usage limit 失败；现有 K3 无工具盲审只作 observation-only 负向证据：报告 `/Users/a77/.finance-runtime/reasoning-boundaries-20260921/semantic-k3-independent-3/REPORT.md`，结果 `passed=false`，拒绝候选 `[1,2,3,5]`，发现 E4 的 `+0.278%` 被错误保留/改号。旧 on2 离线重放仅证明短日期句到达 stub judge，收据 `/Users/a77/.finance-runtime/reasoning-boundaries-20260921/v4/on2/semantic-replay-2cfa.json`，不构成真实模型验收。
- 供需题仍拒答；E2 状态不能合并表述：P5 已随 PR #759 merge commit `db2963d4fbaa` 进入本候选祖先，但正式 P7 live 验收仍未完成；P6 实现 `6721470542a1` 仍在独立分支，owner 收据不传递为本候选行为证据。只读 `git merge-tree` 预检当前候选与 P6 以 exit 1 结束，唯一内容冲突为 `intelligence/services/episode_semantic_verifier.py`，涉及当前日期/语义门与 P6 `material_grounding`/删句撤 binding 合同；工作树未改。外部收据 `p6-integration-preflight.json` SHA256 为 `9f31283909f15a5add70afb93df83777688aeb684ac6e44e61863b8a62a6d581`。
- 未证明跨会话、多层复核、混合联网原轮、任意日期窗口筛选或崩溃 checkpoint 恢复。

## 下一步

1. 保留 V4/V5 原件、flag 未知状态、合同、工具数、公开答案和外部 manifest；不要用 V5 替换旧 on2，也不要把路径证据称为语义 PASS。
2. 由 P6 owner 先在合并树解决 `episode_semantic_verifier.py` 合同冲突，再给出合并树上的材料前提/逐句来源证据；由 P5 owner 补正式 P7 全新会话验收。不要全局改 `user_premise`。
3. 补未见题、新 fixture 反例的真实答卷；独立语义盲审负向结果与服务失败原件继续封存，不写 PASS。
4. 处理前端/E2E/registry 合流检查和跨仓 `kb/rag-query` 漂移，但不把无关漂移混进本候选提交。
5. 合 main、部署、重启8792、购买外审或删除生产原件均需另行授权，本轮不做。

## 原件位置

V4 真实 run、日期 probe、盲审失败原件、全仓日志：`/Users/a77/.finance-runtime/reasoning-boundaries-20260921/v4/`。
K3 独立 reports、events、stderr、execution receipts：`/Users/a77/.finance-runtime/reasoning-boundaries-20260921/k3-independent/`。
