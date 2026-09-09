# 2026-09-09 · 判官修复 01（fix/judge-recovery-01）决策快照

写完不改。inflight：`docs/handoffs/inflight/fix-judge-recovery-01.md`；进度：`docs/superpowers/plans/2026-09-09-capability-upgrade/progress/01.md`。

## 背景

任务包 `docs/superpowers/plans/2026-09-09-capability-upgrade/`（codex 分支 `codex/docs-capability-upgrade-plan`，未在 main）把「独立完成研究」拆成 11 张单，01 是判官修复。派单依据是两条确定性复现（`evidence-judge.md`）：① 同一来源家族的新页补上缺口仍记零新证据、修复被拒；② 必需输出全 fulfilled、多绑一个引用真实证据的扩展块，整篇变 partial 且拒绝部分放行，语义判官零调用。范围合同只许改六个文件的准入/修复接缝及测试；派发时基线 `gitea/main=5eb24515`，主检出树满是别人的未提交改动，故另开 worktree `/Users/a77/fwp-wt-judge-recovery-01`。

用户的方向（INDEX）：先提高能力，在真实超限路径上局部限制；评价重心是任务完成度与研究增量，引用格式/拒答数不代替产品价值。

## 按发现顺序

1. **任务 0 复验**：两条反例在 5eb24515 逐字复现仍在。在途分支交叠（historical-discovery / judge-token-usage / sandbox-derived-calculation）不碰本单函数。
2. **真实存证普查**（391 份，`linxiaoqi5111`+`default`）：完成 87、判官后 partial 146、结构挡 61、判官不可用 42、零证据 48、判官拒 7。`unknown_output_binding` 出现 0 次；`repair_goal` 里「内容进展但 new_evidence=0」0 条——但被拒的修复轮根本不落事件，缺陷一的自然频率不可读。**这一步决定了后面所有「效果」结论只能是确定性口径**。
3. **第一刀**（extra binding）→ 第二刀（进展算法）→ 测试。第二刀撞红 `test_repair_invariant_regression::test_same_source_family_is_not_independent_progress`（ARL-0014 f5），读它的 provenance 后判定：finding 5 要防的是「光有新 hash」，家族门是实现时顺手加的强化，正是被复现的误挡；改期望，f5 原意由同文件另两条继续守。
4. **回放工具**：`scripts/judge_loss_point_replay.py` 从存证重建 contract/outcome 用当前代码跑结构核验 + 语义准入，语义层只读存证，闭集 L0–L5。冻结 15 题（`progress/01-frozen-runs.txt`）。基线臂用 `git archive 5eb24515` 干净拷贝跑同脚本：冻结 15 题、全语料 391 题，首个损失点零差异。诚实结论：两刀修的是确定性缺陷，真实对话里没自然发生过；「可答题整体挡回减半」离线口径 0/0。
5. **第三刀 V11**：读 V11 设计稿（2026-08-22）+ 判官内部（`_verify_inner` 早退、`_run_judge`、`_project_semantic_evidence` 只送绑定/被引证据）。实现时发现 V11 的「撤【质检存疑】标」已无公开落点（V8 后 `_annotate_semantic_rejects` 返回原文）——lifted 对用户不可见，价值只剩控制面可区分四结局。仍按合同做完，如实写。
6. **真实验收**：两臂 sidecar（抄 `v6_deadline_budget_ab.sidecar_zsh`）健康、env 与生产同名同长，五题两臂并发 → 全 HTTP 429 → 网关 57244 掉线。停臂、记账、写续跑命令。

## 决策对比表

| 决策 | 方案 | 评价 | 结果 |
|---|---|---|---|
| 契约外绑定 | A 一律 BLOCK（现状） | 复现二：核心答案连坐 | 否 |
| | B 一律 STRIP_OK | 池外哈希 = 编造引用，与必需槽 `UNKNOWN_EVIDENCE_HASH` BLOCK 不对称 | 否 |
| | **C 按引用可否核验分两档** | 扩展区隔离、编造仍 fail-closed；`_contract_slots_all_fulfilled` 忽略扩展 issue | **选** |
| 进展口径 | A 家族门（现状） | 同源新公告补锚被拒；换个家族名就放行 | 否 |
| | B 新 hash 即进展 | ARL-0014 f5：无 provenance / 转载旧闻开预算 | 否 |
| | **C 新 id 指向未覆盖输出 = 内容进展；家族另记** | 四臂矩阵可分辨；无 targets 账 fail-closed | **选** |
| V11 开关 | A 默认关（设计稿 §7.3） | 「永远不开的开关」被范围合同点名 | 否 |
| | **B 默认开 + env 回滚** | 三道闸限开火面；简单题不缴税 | **选** |
| V11 检索执行者 | A 直接 `kb_rag.retrieve` | 第二条检索链，丢 fixture/新鲜度/语义闸 | 否 |
| | **B 注册表 `kb_search` + `bounded_stage` 子窗** | 授予秒数到达执行者；未授权 → None | **选** |
| lifted 处置 | A 绑进证据台账 | V11 §10.1 防稀释；`_repair_snapshot` 不看 `semantic.verified` | 留增量 |
| | B 升级模型局部改写 | 破 V8「真话连坐」决定、第二修复窗 | 否 |
| | **C 只记账（`support_evidence` + `sentence_verdicts.lifted`）** | 用户不可见，遥测可区分 | **选** |
| 回放 A/B 对照臂 | A 与 8792 对照 | 生产是 `0060da5c`，差异含别人的改动 | 否 |
| | **B 同基线干净拷贝 / worktree** | 只剩本分支这一个变量 | **选** |

## 验证与收据

- 直接测试文件 241 passed；V11 22 条；adapter/verifier/invariant 191 passed；pre-commit 11 道过；`check_unread_fields` 无新增。
- 全量：第一次（两刀后）8308 passed / 1 failed（即改期望那条）；第二次（三刀后，机器同时跑 sidecar+探针）8327 passed / 3 failed（超时看门狗类，安静单跑 3 passed，108s）；第三次安静跑见 `/tmp/judge01/full-pytest-3.log`。
- 存证 A/B：`/tmp/judge01/{frozen,corpus}-{base,branch}.json`；探针存证 `~/.finance-runtime/judge01-users/`。
- **不成立的读数**：真实验收零草稿，任何「升级后更好/更差」都不能说；n=15 冻结样本只是分层抽样，不是统计。

## 后续要做 / 不要做

要做：网关回来后串行两臂五题；合并前以 `feat/judge-token-usage` 为准重跑；TOOLKIT 登记两个脚本；V11 §8 A/B 与台账行交验收方。

不要做：不要把 V11 改回默认关（合同点名）；不要为了让 lifted「可见」重新往公开稿加标（V8 决定）；不要把 `test_repair_invariant_regression` 的家族断言改回去（那是复现的缺陷）；不要拿 8792 当对照臂（revision 不同）；不要两臂并发发题。
