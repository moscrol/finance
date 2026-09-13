# daily-swap 87be884b 文档更正复核

日期：2026-09-13；审查分支 `docs/qc-daily-swap-87be884b`。
被审提交：`87be884b78520046f46905eaf84baeff6041892a`。
本轮 fetch 后 `gitea/main=e40f22b837178322169f47e565282450b4381a3a`。

## 裁定

**九轮两项文档 P2 均可关闭，未发现本次更正引入新的阻断项。建议用户授权完整分支整合候选阶段；不是批准合并或生产换库。**

上一轮裁定见 `docs/qc-daily-swap-ac7e3087` 分支的
`docs/handoffs/2026-09-13-daily-swap-ac7e3087-qc.md`。
本轮只复核事实更正与执行边界，不重审没有变动的行为代码，不把旧测试结果冒充新收据。

## 复核经过

1. 主检出树 detached HEAD 且大量其他会话改动，未触碰。目标施工树
   `.claude/worktrees/daily-swap-race-condition-d0f557` 为干净 `87be884b`。
   本报告在独立 `/private/tmp/daily-swap-qc-87be884b` 编写，不修改施工分支。
2. `git diff --name-status ac7e3087 87be884b` 仅三份文档；进一步核对
   `2d16a7f7..87be884b` 同样只有这三份文档，无行为/测试代码改动。
3. 逐份读取原始收据，而非引用上一轮结论作为原件。收据根目录
   `~/.finance-runtime/test-receipts/`：

   | 原件 | 核得事实 | 可支持的结论 |
   | --- | --- | --- |
   | `20260913T104700Z-2d16a7f7.json` | target 是 sandbox 单测；0 passed / 1 failed；dirty=false，全树脏数0 | 父提交单测失败，不是全量；该提交本身已经包含七轮代码修补 |
   | `20260913T065924Z-7c89ca81.json` | target 是整树；9502 passed / 1 failed / 77 skipped；dirty=false、dirty_paths=[]、worktree_dirty_total=1 | 修补前全量存在同名失败；不能称整棵工作树零改动 |
   | `20260913T104506Z-c20abf7d.json` | 整树9518 passed / 1 failed / 79 skipped；dirty=false，全树脏数0，exit=1 | 干净 c20abf7d 全量有一红 |
   | `20260913T105335Z-c20abf7d.json` | 同一 sandbox 单测1 passed；dirty=false，全树脏数0 | 单独复跑绿；不是全量绿 |

   三份失败原件的 failed_id 均为
   `intelligence/tests/test_codex_headless_runtime.py::test_installed_codex_sandbox_denies_network_and_unix_socket`。
   `git merge-base --is-ancestor 7c89ca81 2d16a7f7` exit=0，历史顺序成立。
   原日志 `~/.finance-runtime/reviews/daily-swap-c20abf7d/full.log:215`
   为 `1 failed, 9518 passed, 79 skipped, 1 xfailed`；xfailed 来自日志，不是 JSON 字段。
4. 现三份文档均撤掉了预先豁免，明确根因未清、旧失败只用于历史归因。
   这闭合九轮 P2-1。历史同名失败不证明此次失败机制相同，也不能独立排除回归；
   本次更正没有再作这种扩大断言。
5. fetch 后实算 `git diff --shortstat e40f22b8...ac7e3087`：
   **16 files / 3936 insertions / 51 deletions**，与文档固定快照一致，九轮 P2-2 关闭。
   最新 `e40f22b8...87be884b` 则是 **16 files / 3941 insertions / 51 deletions**。
   两个 tip 差异全为文档；这不是新阻断或要求再改一轮历史数字。
   三点 diff 是分支相对共同基座的增量，不是已经组装好的候选相对主干的最终差异。
   正式执行时固定 main SHA 与最新施工分支 SHA，再生成实际候选范围。
6. `git diff --check ac7e3087 87be884b` 通过。施工 inflight 为 **3065 字节**，
   `scripts/session_facts.sh` 的告警阈值是3072，达标但仅余7字节。

## 执行方案评价

| 选择 | 评价 | 裁定 |
| --- | --- | --- |
| 再重复同一代码修补的全量审查 | 本提交无行为/测试改动；不能补上最新主干整合风险 | 不要求；新全量应花在获授权的整合候选上 |
| 只摘七轮最新行为提交 | 缺前序发布/锁/错误分类契约；不是独立功能包 | 不建议；若要缩范围须另审依赖拆分 |
| 最新 main + 完整施工分支，冻结干净候选后验证 | 保留已审堆叠链，并对主干组合与整个 hithink 重建负责 | 建议用户授权，不代用户授权 |
| 历史失败按 baseline exception 自动放行 | 混淆归因与门禁裁定 | 拒绝；红/无结论仍阻断 |

### 建议授权文本

> 从届时最新 gitea/main 建独立整合候选，整合完整施工分支（当前 tip 87be884b；若推进先核对新增范围）。固定双方 SHA、提交并确认干净后，分别重跑 Python、前端、E2E、注册表适用门禁，并用冻结输入与隔离库完成 hithink 对账。遇红保留原始证据、定位处理，不自动豁免，也不跳过其余门禁。暂不合并 main、不切运行时、不写或替换生产库；合并与生产换库分别再申请授权。

执行细则沿用九轮报告：
- 适用性按届时 workflow paths 核；非适用也留判定依据。收据记录命令、候选 revision、dirty、解释器与依赖，不跨候选挪用。
- 任一失败修复形成新候选后，旧证据保留，重新验证最终候选；不得循环刷到偶然绿、删测试或盲目 xfail。
- 隔离目标、输出及备份路径必须确认不解析到 canonical 生产路径；不另开实时外呼/历史回填范围。
- hithink 不只数行：主表/两类派生一致、当日字段/允许漂移、非目标日期不变、板块拼接、302132置缺、ops_sync_run、备份指纹与恢复步骤可核验。
- 代码合并许可和生产换库许可分开；生产执行时另核基线与备份，候选验证不能提前代表未来生产状态。

## 验证边界与沉淀

本轮没有运行 pytest/Ruff/前端/E2E/注册表，没有组装整合候选，没有重放真实 hithink 数据，未查清 sandbox 波动根因。没有写生产库、切运行时或合回 main。
旧 c20abf7d 全量仍是9518P/1F，旧 ac7e3087 定向75P与探针19P只属于各自原始被测快照。
一般 clone IO 裸抛仍按原裁定另单；既有库身份检查到 replace 的末端窗口、同 inode 裸写仍为已声明边界。

没有新增通用工具或新方法论：本轮是一次性文档闭环核验，复用 Git 与结构化收据；语义上区分“历史存在”与“根因归属”，无需再建第二份门禁/经验清单。
