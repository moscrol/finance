# 2026-09-22 研究尾单联合候选：门禁已齐后的合流推进工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
上游：#59。姊妹：#66（财务链独立路径，与本单**互斥**，见决策 1）、#68（历史 completion 分支，决定本单历史 head 用哪个）、#75（独立终审）、#76（四道自然题）。本单含三处用户决策。

## 背景与动机

- 09-21 #831 把研究尾单的集成基线合进 main（`e82717d9a`），三条前向分支因此直接摞在 main 上：历史 `fix/history-forward-boundary-0921`（#845，head `442476f7d`）、runtime `fix/runtime-forward-0921`（#834，`cb16cd463`）、财务 `fix/financial-forward-0921`（#835，`d82cb16b5`）。`merge-tree` 自探：main × 三者各 0 冲突；历史 × runtime 0 冲突；历史 × 财务 6 文件 7 处；runtime × 财务 4 文件 5 处。
- 联合基线 **`de8b06732`**（`baseline/research-tail-union-0922` = main `a2c8d1f9` + 历史候选 `42784d27e`〔含 #814 门禁移植〕+ runtime `cb16cd463`，财务不在内）：前端 6 项、registry 5 项绿；Python 叶首次被负载 SIGTERM（2420.8s / 2400s 帽，无 junit，不是红）；重排后用派生 `run_leaf_extended.py`（只把 python 叶上限 2400→5400 秒，收据 `extends_sha256` 指回冻结 runner）于 **22:07 完成：`exit_code=0`、`complete=true`、`source_unchanged=true`**（`retry2-de8b06732/gates/python/run.json`）。
- 财务合流候选 **`65fde6171`**（`fix/research-tail-financial-union-0922`，本地未推）：在基线上 `git merge --squash d82cb16b5`，实解 8 文件 13 处冲突，核心碰撞点 `continuous_turn_adapter.py`：`track_contract` 取财务线的 `track_receipt`，同时把 `history_intent=context.history_intent` 下移到 `_track_public_delivery` 的 `contract_receipt(...)`；保留 `_recover_verified_delivery` 但保住 `_storage_failed_result` 围栏；`honesty_gates.py` 两套正则合并新增 `history` 分组、`_cutoff_instruction_text` 改走 `top_level_message_text`（比财务旧版更严、fail closed）。registry exit 0、frontend exit 0（324s）、**python 叶 22:25 完成 `exit_code=0`、`complete=true`**（`candidate-gates/gates/python/run.json`）。定向 849P；4 条接缝变异改坏即红。新增 `intelligence/tests/test_research_tail_union_seams.py`、`tests/test_mutation_runner_selection.py`。
- 历史 head 的分叉：联合树用的历史候选 `42784d27e` 是 #845 head + #814 门禁移植；同日另一条 `fix/history-completion-0922`（`807a75d88`，#68）在 #845 之上又加 6 个提交（`compare_cases` 规则型启动、算子清单补齐、引错算子剔除不作废、四题四形状离线走通）。两者不是同一个历史。
- 独立终审与四道自然题（历史四题 + 财务 R6 四题里的自然形态）**未动**，要付费通道 / 另行授权。
- **已定的形态决策**：不信 Gitea `mergeable`，用 `merge-tree` 自探；冲突逐处按双方意图解，不用 `-X ours/theirs`；被负载中断的收据不当部分绿也不当红；候选分支冻在门禁 revision 上不再追加提交（再提交收据就不描述分支头了）。

## 决策（先贴用户）

1. **财务线路径**：走本单候选 `65fde6171`（一次带三线合入）还是走 #66（#835 → #855 依序）。同一改动只走一条路。
2. **`contract_receipt` 同一调用点同时承载财务契约与 `history_intent`**：技术上两边都保住了，产品上该不该这样并，需用户签字。
3. **历史 head**：联合树继续用 `42784d27e`，还是重建为 #68 的 `807a75d88`（重建 = 重跑三叶约 40 分钟 + 重解财务冲突）。

## 目标

1. 决策 1 选本单时：推送 `fix/research-tail-financial-union-0922`（不改 SHA）、开 PR（base main），描述含两棵树四叶收据路径、13 处冲突的解法表、变异读数；交 #75 独立终审（Spec + Quality）。
2. 决策 3 选重建时：以 `807a75d88` 替换历史层，重做 squash 与冲突化解，重跑三叶，新候选新 SHA，本单收据全部作废重取。
3. #814（`fix/test-gate-receipt-identity-0921`，每轮新建 `gate-*/pytest.json` 并传 `FWP_TEST_RECEIPT_PATH` 的做法）：确认其内容已随 `42784d27e` 进入候选；进了就 `close 814 --pointer-file` 指向候选 PR，没进就列出差异。
4. 用户确认后合入（`merge --record`）；然后 `close` #833 / #834 / #838 / #841 / #845（若被候选覆盖）各留接替指针；未覆盖的写明差异留 open。
5. 四道自然题的条件卡交 #76：题面来源、固定 SHA、frozen 数据根、预算。

## 非目标（写死认领）

- ❌ 不静默替用户决定财务口径（决策 2）。
- ❌ 不在候选分支上追加任何提交（含文档）；新状态写证据目录 README，不写分支。
- ❌ 不跑真实模型；独立终审由 #75 用 K3 通道做。
- ❌ 不修联合树里既有的负载敏感红；分诊表同 #59。
- ❌ 不把财务线带入的大量 `docs/handoffs`、`docs/verification` 历史文件逐份复核时效性；PR 描述声明未复核。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/.finance-runtime/reviews/research-tail-union-resume-20260922/README.md` | 两棵树身份、门禁现状表、「timeout 收据怎么读」、每一版准入为什么被否 |
| 同目录 `retry2-de8b06732/gates/python/run.json`、`candidate-gates/gates/{python,frontend,registry}/run.json` | 完成状态、`source_unchanged`、`extends_sha256` |
| 同目录 `focused-02/pytest.log.txt`、`union-seam-mutations/results.json` | 849P 定向面、4 条变异 |
| 分支 `fix/research-tail-financial-union-0922`：`docs/handoffs/inflight/fix-research-tail-financial-union-0922.md` | 13 处冲突逐处的意图判断（核心碰撞点段） |
| `~/.finance-runtime/reviews/research-tail-formal-gate-20260922/` | 历史候选 `42784d27e` 正式门禁 12861P/0F 与两条负向控制 |
| `intelligence/services/continuous_turn_adapter.py`（候选版 vs main vs `d82cb16b5`） | 双父枝差分：对财务父枝只多历史/runtime 的东西，对基线只多财务的东西 |
| `scripts/run_leaf_extended.py`（证据目录内） | 派生 runner 与冻结版的唯一差异 |
| #68 工单与 `fix/history-completion-0922` 交接 | 决策 3 的另一候选 |

## 步骤

1. 开工三连；`git -C ~/fwp-wt-research-tail-financial-union-0922 status --short` 必须为空；核对两棵检出 HEAD 仍是 `de8b06732` / `65fde6171`。
2. 三问贴用户。
3. 决策 1 选本单 → 推送、开 PR；决策 3 选重建 → 新建 `fix/research-tail-union-v2-0922` 从 `de8b06732` 重做（历史层换 `807a75d88`），三叶收据新取。
4. 双父枝差分复核一次（`git diff d82cb16b5 <候选> -- intelligence/services/continuous_turn_adapter.py` 只应含历史/runtime 侧改动）。
5. 交 #75；结论 PASS 或 PASS_WITH_LIMITS 且用户确认后合入；随后 close 一族 PR 留指针。
6. 合入后 main tip python 叶复跑一次（接 #59 口径）。
7. INDEX #67 行；inflight ≤3K（写在证据 README，不写冻结分支）。

## 验收

- [ ] 候选 PR 描述引用的两棵树四叶 `run.json` 全部 `complete=true`、`exit_code=0`、`source_unchanged=true`。
- [ ] 阳性对照：`union-seam-mutations` 任取一条重跑，改坏即红、还原即绿，字节指纹一致。
- [ ] 三问均有用户原话记录。
- [ ] 合入后 #833 / #834 / #838 / #841 / #845 / #814 每张要么 merged 要么 closed 带接替指针要么 open 带差异说明。
- [ ] 合入后 main 上 `history_intent` 在 `_track_public_delivery` 的 `contract_receipt(...)` 可 grep 到，且 `_storage_failed_result` 仍在。

## 红线

- 只用 pathspec 提交；合入 main 等用户确认；不强推；不 `-X ours/theirs`。
- 冻结候选不追加提交；证据树 `~/.finance-runtime/reviews/**` 不改内容。
- 全量前 `uptime` / 磁盘准入；被中断的收据不移签。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`。
- 不跑真实模型；不动 8792；不写明文密钥。
