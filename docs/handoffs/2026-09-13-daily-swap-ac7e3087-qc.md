# daily-swap ac7e3087 收据更正质检与下一步

日期：2026-09-13；审查分支 `docs/qc-daily-swap-ac7e3087`。
被测提交 `ac7e30877d84c5b823fa25840451e39d4606d9f8`。
刷新后主干 `gitea/main=e40f22b837178322169f47e565282450b4381a3a`。

## 裁定

**核心收据更正成立，行为修补维持通过；文档仍有两项 P2 事实误差，改掉即可进入用户授权的整合候选阶段。不是新行为阻断，不要求重复第八轮全量。**

本轮未组装候选、未合并、未写生产库、未运行真实供应商修复。审查报告不授予任何上述权限；全量全绿及可直接合并仍不签发。

## 发现（按重要性）

### P2-1：父提交收据被扩大为“全量”，修补前对照身份也须分清

位置：`docs/handoffs/2026-09-13-daily-swap-round7-fixes.md:74-77`。

当前写 `2d16a7f7 全量同红（非本刀引入）`。实际收据
`~/.finance-runtime/test-receipts/20260913T104700Z-2d16a7f7.json` 的 target 是
`intelligence/tests/test_codex_headless_runtime.py::test_installed_codex_sandbox_denies_network_and_unix_socket`，counts 为 **0 passed / 1 failed**，是单测复跑，不是全量。

且 `2d16a7f7` 已包含七轮行为修补，它是文档提交 c20abf7d 的父提交，不是行为修补前对照。若用这份收据独立证明行为修补没引入失败，论证不充分。

但“该失败早于七轮修补”另有真实证据：
- `20260913T065924Z-7c89ca81.json`：dirty=false（行为路径干净，worktree_dirty_total=1），全量 9502 passed / 1 failed / 77 skipped，同一 failed_id；该 revision 早于七轮行为修补。
- `20260913T062132Z-44d23e6b.json`：全量 9499 passed / 1 failed，同一 failed_id。
- `20260913T105335Z-c20abf7d.json`：施工树干净，单独 1 passed。

建议改写为：“干净 c20abf7d 全量唯一红；2d16a7f7 单测复跑同红，c20abf7d 单测复跑绿；7c89ca81 的修补前全量亦有同名失败，故登记既有失败/环境敏感现象，非本刀新增失败。”

这支持历史存在性与结果波动，不等于已查明根因，更不等于合并门禁豁免。

### P2-2：供用户裁定合并范围的统计仍是旧快照

位置：`docs/handoffs/inflight/fix-daily-swap-lock-all-callers.md:35`；
`docs/handoffs/2026-09-13-daily-swap-round7-fixes.md:86`。

实算：

```text
git diff --shortstat 631786ab...dfb6ce87
15 files changed, 3723 insertions(+), 46 deletions(-)

git diff --shortstat e40f22b837178322169f47e565282450b4381a3a...ac7e3087
16 files changed, 3936 insertions(+), 51 deletions(-)
```

原“15 文件 / 3723 插入”能精确追溯至 dfb6ce87 的旧范围，不是当前分支。当前分母是**整个候选分支相对共同基座的增量**，不是 hithink 单模块，也不是 ac7e3087 本身（本提交只有三处文档）。

16 文件按本次清单分为：6 个生产 Python 文件、4 个测试文件、6 个文档/教训文件。确实包含整个 hithink 重建，不应让用户按旧规模授权。改用固定 base/tip + 生成命令，或把旧数字标成历史快照。

## 核验经过与收据

1. 当前主目录 detached HEAD 且大量他人在途改动；目标施工树 ac7e3087 干净。新建 `/tmp/daily-swap-qc-ac7e3087` 固定提交，只在此跑测试。
2. `git diff c20abf7d ac7e3087 --name-only` 恰为用户列的三份文档；`git diff --check` 通过。inflight 为 **3056 字节**，脚本阈值 3072，达标。
3. 两份全量 JSON 逐字段核对：
   - `20260913T095323Z-dfb6ce87.json`：9521 passed / 0 failed / 77 skipped，dirty=true，dirty_paths 恰为 db.py、sync_daily_full.py、staging_swap 测试；worktree_dirty_total=6。它不是干净提交收据。
   - `20260913T104506Z-c20abf7d.json`：9518 passed / 1 failed / 79 skipped，dirty=false、全树脏数0、exit_status=1，failed_id 为 codex sandbox 那条。
   - JSON 生成器只存 passed/failed/error/skipped；**1 xfailed 来源是原始 full.log**，不是 JSON 内字段。日志尾行是 1 failed / 9518 passed / 79 skipped / 1 xfailed，433.81s。
4. 阅读 `sync_daily_full.py:516-568,722-797`、`db.py:196-248,437-491` 及对应常规回归。首次观察分类先于探针；已见旧库消失拒绝开工；首次建库用 link，link 错误无 replace 回退。未扩大既有库身份检查→replace 的非协同写者边界承诺。
5. 在干净 ac7e3087 独立复跑：
   - 三文件 **75 passed，14.01s**；`20260913T111550Z-ac7e3087.json`，dirty=false，worktree_dirty_total=0。
   - 原七轮9条 + 八轮边界矩阵10条：**19 passed，4.02s**；`20260913T111633Z-ac7e3087.json`。
   - 全仓 Ruff：通过。
   - 使用主树 `.venv-workbench/bin/python`，`env -i PATH/HOME/KNOWLEDGE_WIKI`、umask 022；pytest 显式 `-p no:randomly`。探针拷入本审查树 ignored `tmp/qc-probes/`，避免别的 worktree conftest 抢 import；这是原探针重放，不是19条新生产回归。
6. `git merge-tree --write-tree gitea/main ac7e3087` exit=1，唯一报告的冲突为 `.claude/lessons_learned.md`。只生成 Git 对象、没有移动分支或实际合并；文本预检不能代替候选门禁。

本轮证据目录 `~/.finance-runtime/reviews/daily-swap-ac7e3087/`：targeted.log、ruff.log、probes.log、probes.sha256、merge-tree.txt。原八轮输入与日志在 `~/.finance-runtime/reviews/daily-swap-c20abf7d/`，复用 prepared 下两份探针，哈希单独保存。

## 下一步：推荐完整整合，而不是只摘最新一刀

| 路径 | 评价 | 建议 |
|---|---|---|
| 只摘 2d16a7f7 | 它依赖前序 link 发布、错误分类、三锁与备份契约；摘一刀不是独立功能包 | 不选；若用户只要锁修复，应另做明确依赖拆分 |
| 完整分支进入最新 main 的候选 | 保留已审的堆叠链，范围明确；会带入整个 hithink 修复，须补整体数据验收 | 推荐，等用户明确授权 |
| 把 baseline exception 当永久跳过规则直接合并 | 归因不是放行；现行 AGENTS.md 要求所有适用叶子全绿 | 不选 |

建议接手顺序：

1. 小文档提交修正上面两点，并将“整合候选 codex 抖动按 baseline exception”收紧成“历史失败保留归因记录；新候选失败仍阻断，不能预先豁免”。无需重做同一刀全量。
2. 用户授权后，从届时刷新并固定的 gitea/main 建独立候选分支，整合完整修补链。当前只看到 lessons 文本冲突；保留双方教训，不用 ours/theirs 整文件覆盖。尚不合回 main。
3. 候选先提交、确认干净，再串行跑适用门禁并记录完整命令、revision、dirty、解释器、依赖及失败 ID：Python Ruff+全量、前端 lint/typecheck/test/build、E2E、registry-check；一片红不跳过其余叶子。data-quality 是否适用按届时 workflow paths 判定，当前分支增量未触发其路径。
4. codex sandbox 若再红，在相同环境的候选与主干对照记录 failed_id 和底层失败原因，另修测试隔离/环境问题。历史记录只用于归因；不得删测试、盲目 xfail、循环重跑直到偶然绿，或把 exit=1 签成全绿。若要变更门禁政策，须另行明确裁定，不能从“baseline exception”四个字推导。
5. 同一候选上，用隔离库和冻结 hithink 输入完成真实修复入口的端到端对账：当日字段与白名单漂移、非目标日期不变、板块拼接、主表与两类派生一致、302132 保持明确置缺、ops_sync_run 与备份指纹/恢复步骤可核验。不得只以行数验收，不扩大历史回填日期。旧 hithink 端到端记录不能代替新候选验证。
6. 全绿及整体数据对账齐后，提交用户裁定“合并代码”；生产换库仍需独立授权，执行时重新确认生产基线、备份与恢复条件。

## 未验证与沉淀边界

- 本轮没有重跑全量：ac7e3087 仅文档变更，且检查时另一个工作树全量运行中；全量证据保留为 c20abf7d，不外推成 ac7e3087/候选全绿。
- 未新跑 codex 单测，未查清其波动根因；没有重放 hithink 真实数据链。
- 一般 clone IO 裸抛仍按旧债另单；非协同整文件替换末端窗口、同 inode 裸写仍是声明边界。
- 没新建通用排查工具：本轮复用现有 JSON 收据、Git 差异/预检与现成探针。发现的是报告对 target/对照身份/范围的语义扩大，不是本轮证实了机械门禁失效；方法不另建第二份通用清单。
