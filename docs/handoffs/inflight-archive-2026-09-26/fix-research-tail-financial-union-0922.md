# 研究尾单联合树 + 财务线合流（在途）

## 这个分支做什么
把此前因真冲突进不来的财务线 `d82cb16b5` 化解到联合基线 `de8b06732`（= main `a2c8d1f9` + 历史候选 `42784d27e`（含 #814 门禁移植）+ runtime `cb16cd463`）之上，只在隔离工作树里成树。不合 main、不推送、不部署、不启动付费终审。

## 决策与被否方案
- 用 `git merge --squash d82cb16b5` 在新工作树逐处解冲突（实为 **8 文件 13 处**，非交接里说的 6+4）；否了 `-X ours/theirs` 与「按行数取大」，冲突处按双方意图判，不是挑版本。
- `continuous_turn_adapter.py`（核心碰撞点）：`track_contract` 取财务线的 `track_receipt`，同时把 `history_intent=context.history_intent` 下移到 `_track_public_delivery` 的 `contract_receipt(...)`；两方语义都保。否了二选一——丢财务侧则公开回执失去财务契约，丢历史侧则 `history_intent` 断在公开边界。
- 同文件保留财务线新增的 `_recover_verified_delivery`，但保住 `_storage_failed_result` 保存失败围栏；否了让语义修复路径吞掉落盘失败。
- `api/app.py` SSE：取财务线的精确发布检查，并补发两次读取之间新产生的事件；否了「先发终局 run 再收尾」，那会丢提交事件。
- `honesty_gates.py`：删掉对 `explicit_information_cutoff` 的依赖，两套正则合并（新增 `history` 分组），`_cutoff_instruction_text` 改走 `top_level_message_text` 顶层来源分区，保留财务线的日期角色/否定规则；否了并存两个解析器（同一问题两处真相）。
- `scripts/review_probes/run_extraction_mutations.py`：把 `--suite` 与 `--tests/--definitions` 两套选择器合并、去掉 `global`、抽出 `_parse_args`；否了保留两个入口。
- 交叉接缝测试期望 `completed` 实得 `partial` 时，查明是历史线**独立存在**的发布上限（无已执行历史结果 → `max_status=partial`），改的是测试断言，不是产品。

## 当前状态
- 工作树 `/Users/a77/fwp-wt-research-tail-financial-union-0922`，分支 `fix/research-tail-financial-union-0922`，工作区干净。
- 两个提交：`0b688c368`（财务线合流，218 文件）、`f517cd27f`（删掉被财务构建取代的 `index-DH207EFA.js`，静态目录与 `d82cb16b5` 完全一致）。
- **未推送、未合 main、未部署**；#845 head 仍 `442476f7d`，未动。
- 联合基线 `de8b06732` 本身**一行未改**，其 Python 叶重跑仍在资源准入等待中（见下）。

## 已验证
- 定向全量：`intelligence/tests` + `tests` 相关面 **849 passed**，日志 `…/research-tail-union-resume-20260922/focused-02/pytest.log.txt`；再次局部 32 passed。
- 全仓 `ruff check` exit 0；`gen_runtime_catalog.py --check` 三张目录与源码一致；pre-commit 全部门禁（层级 0 ERROR、路径字面量 23/37 持平、字段契约 38 文件/92 字段未增、dataset 注册、工具可达性、目录保鲜）通过。
- 负向控制有牙：对已提交 revision `f517cd27f` 跑 4 条变异（`…/union-seam-mutations/results.json`），逐条**改坏即红、还原即绿**，字节指纹还原一致，基线与还原各 24 项全绿，临时工作树已自清理。
- 新增交叉接缝测试 `intelligence/tests/test_research_tail_union_seams.py`、CLI 选择器测试 `tests/test_mutation_runner_selection.py`、变异定义 `scripts/review_probes/research_tail_union_mutations.json`。

## 未验证 / 已知边界
- 本候选 `f517cd27f` **没有跑过完整 Python/前端/registry 全叶门禁**；849P 是定向面，不能当全量绿，更不能当合并依据。
- 联合基线 `de8b06732` 的 Python 叶仍只有一张 `stop_reason=disk-space-floor` 的中断收据（12077P，exit 4）；中断收据不可当部分绿。
- 前端产物取自财务线既有构建，本轮未重新 build、未跑前端叶；`index.html` 与 assets 的一致性只做了树级比对。
- 财务线带入大量 `docs/handoffs`、`docs/verification` 历史文件（squash 的一部分），未逐份复核其内容时效性。
- 机器磁盘曾低至 1.8 GiB、load 峰值 45/10 核；未检查资源前不要启动任何全量门禁。

## 下一步
1. 等 `admit_union_python_v2.py`（证据目录内，一次性、不自动重试）放行后回读 `retry-de8b06732/gates/python/run.json`；若 `stop_reason=timeout` 说明是资源不是失败，重排即可。
2. 联合基线绿灯后，再对 `f517cd27f` 固定跑三叶全量门禁，才谈合并授权。
3. 财务冲突的化解口径需产品/历史两线确认（尤其 `contract_receipt` 同调用点的双语义），确认前不要把这棵树当共识。
4. 全程保持：不合 main、不推送、不部署、不启付费终审。

## 踩过的坑
- `git commit <pathspec>` 按工作区匹配路径，**已删除的文件永远匹配不上**，第一次提交因此漏掉一个删除（后补 `f517cd27f`）；用 `git status` 复核暂存区才发现。
- pytest 临时目录里有测试故意设成只读的 fixture，`rm -rf` 会整片 Permission denied，须先 `chmod -R u+rwX` 再删。
- 上一版资源准入要求「机器上零 pytest」，这台机器常驻 5–12 个他人 pytest，该条件不可达，等于永不放行；v2 改成磁盘 ≥12 GiB、load1 ≤14、外部 pytest ≤3 且静默 60 秒，并排除自己的子进程。
- 同叶基线耗时：安静时 981s，重载下跑到 1968s 仍未完，而 runner 单命令上限 2400s——重载下启动买到的多半是超时收据。
