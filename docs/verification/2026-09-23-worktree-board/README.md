# #84 看板加固与 ownership 处置输入

## 状态与范围

基线 `626d8a508c1c988ff094110b371987e6afdcdd15`，隔离分支 `fix/worktree-board-hardening-0923`。只前向 #812 看板修复；不合入旧三单组合，不处理 #813/#814，不重开 K3，不删除真实 worktree。

**工程候选，尚不可合入。** 定向测试通过；干净树四叶未齐。宿主同时运行多轮其他任务全量 pytest，磁盘从 11 GiB 降到 9.4 GiB，停止追加全量重负载。此前 #812 的 v4 组合工程绿与 K3 ENOSPC 中断均只代表旧对象，不能移签本分支。

## 判据去重

| 判据 | 唯一实现 | 调用方 |
|---|---|---|
| 路径存在且真是仓库根，不借父仓事实 | `worktree_safety.inspect_tree` | 看板 + 清理 `check` |
| Git 状态失败为未知；所有未提交文件阻塞；ignored 内容另列 | `worktree_safety.inspect_tree/status_paths/file_blockers` | 看板 + 清理 `check` |
| HEAD 祖先关系 | `worktree_safety.ancestor` | 看板合入快捷判断 + 清理 `ancestor` |
| 进程 PID / cwd / 打开文件 | `worktree_safety.sample_context/context_blockers` | 看板每轮一次 + 清理 `context/check` |
| plist、启动器、runtime 软链引用及 canonical 路径 | 同上；plist 用标准库解析 | 同上 |
| 补丁等价、ahead/behind、全扫描固定基准 SHA | `worktree_board.py` | 只属于合入看板，补丁等价不是删除许可 |
| 年龄、主树排除、detached 候选策略、实际删除 | `cleanup_gate_trees.sh` | 保留 #876 入口；本次未对真实仓运行它 |

定位命令：`rg -n 'merge-base|lsof|plistlib|status.*porcelain|inspect_tree|sample_context|SAFETY' scripts/worktree_{board,safety}.py scripts/cleanup_gate_trees.sh`。命令/解析只有共享模块一份；清理壳不再自行采样/解析状态和引用。

明确改变 #876 的一处宽豁免：不再忽略整个 `.code-review-graph` 的 Git 状态，包括删除、修改、未跟踪。否则真实未提交内容也会被豁免。现有 ignored 内容保护仍保留。mtime、删除策略未扩写；#64 的完整证据树/reflog/授权要求仍须另验，看板不签“可删”。

被否方案：只改“不是删除许可”文案而不接共享采样，仍有两套状态判据，也无法报告具体进程/plist；整枝搬 #812 会带入其他工单与旧收据。全扫描改为最多 4 路只读并发、保持注册顺序和固定基准；`--this` 不扫进程、不改变 session_facts.sh。

## 验证

- 看板 + 共享安全采样 + 清理隔离夹具：46 passed（实现迭代阶段）；全仓 ruff 通过。最终干净源码定向收据见本分支交接及树外运行目录。
- `check_regressions.py old`：固定 main 旧实现 **9 failed / pytest exit 1**，恰好九个反例；不是把旧结果抄来。
- `check_regressions.py mutation`：内存中把 `not row.dirty` 改为 `not row.code_dirty`，恰好 **1 failed**。源码未改写，撤保护确实被抓住。
- `--this` 正常输出冻结基线及生产 ledger 读数；未切生产。
- 实际整仓扫描先后在 120s / 900s 外层预算超时，未签成功。随后 `--json --timeout 1` 返回 `git worktree list failed; worktree inventory unknown`、`trees:null`，证明全局失败不冒充空清单。当前资源窗口不适合反复重扫；成功 JSON schema 用隔离仓回归验证。
- 原始日志：`~/.finance-runtime/reviews/worktree-board-hardening-20260923/{legacy-red.log,mutation.log,board.json,board.stderr}`。
- 四叶：Python 全量、frontend、E2E 待资源窗口；registry 单列跑、不得以定向46P冒充全量通过。旧日志保留，不覆盖重跑。

## 12 棵处置表

原始读数 `ownership.json`，复算入口 `collect_ownership.py`。W = `/Users/a77/fwp-wt-ownership-`；R = `/Users/a77/.finance-runtime/reviews/`。表内路径 `Wxxx` 是前缀拼接，不是相对目录。

实测为 **6 baseline + 1 ops + 5 detached**；所有 HEAD 与注册表一致，且 **12/12 都不是采样基准 main 的祖先**（exit 1）。脏项是受跟踪文件删除 ` D`，不是预期的未跟踪文件。以下 B2/B3/B4 分别是 `baseline/ownership-gates-v2-0921`、`baseline/ownership-gates-v3-0921`、`baseline/ownership-gates-v4-0921` 的精确 HEAD 锚点。

| 树路径 | 分支 / HEAD 锚点 | HEAD | 证据目录 | dirty 文件 | 可否拆 |
|---|---|---|---|---|---|
| Warena-gates-0921 | baseline/ownership-arena-gates-0921 | 471f85a22613 | Rarena-main-ready-20260921 | `.code-review-graph/.gitignore`、`.code-review-graph/wiki-steering.json`（D） | 否：dirty、非祖先、证据保全 |
| Warena-gates-v2-0921 | baseline/ownership-arena-gates-v2-0921 | b8292d235a88 | Rarena-main-ready-v2-20260921 | 同上两文件（D） | 否：dirty、非祖先、证据保全 |
| Wcloseout-0921 | ops/worktree-ownership-closeout-0921；无 baseline 精确锚点 | 53f789969c44 | Rownership-closeout-20260921；树内 docs/verification/2026-09-21-* | 同上两文件（D） | 否：dirty、非祖先、#812 原件 |
| Wgates-0921 | baseline/ownership-gates-0921 | 321712b68732 | Rownership-followup-20260921 | 同上两文件（D） | 否：dirty、非祖先、证据保全 |
| Wgates-v2-0921 | B2 | e1b63b1a5b7c | Rownership-followup-recheck-20260921 | 同上两文件（D） | 否：dirty、非祖先、证据保全 |
| Wgates-v3-0921 | B3 | 47530e20fe5c | Rownership-resume-20260921 | 同上两文件（D） | 否：dirty、非祖先、证据保全 |
| Wgates-v4-0921 | B4 | 6eb12c1b8a41 | Rownership-integration-v4-20260921 | 同上两文件（D） | 否：dirty、非祖先、证据保全 |
| Wquality-v3-0921 | detached；B3 精确锚点 | 47530e20fe5c | Rownership-k3-v3-20260921/quality-k3 | 同上两文件（D） | 否：dirty、非祖先、审查现场 |
| Wquality-v4-0921 | detached；B4 精确锚点 | 6eb12c1b8a41 | Rownership-k3-v4-20260921/quality-k3 | 同上两文件（D） | 否：dirty、非祖先、K3 中断原件 |
| Wresume-review-0921 | detached；B2 精确锚点 | e1b63b1a5b7c | Rownership-resume-20260921 | 同上两文件（D） | 否：dirty、非祖先、审查现场 |
| Wspec-v3-0921 | detached；B3 精确锚点 | 47530e20fe5c | Rownership-k3-v3-20260921/spec-k3 | 同上两文件（D） | 否：dirty、非祖先、审查现场 |
| Wspec-v4-0921 | detached；B4 精确锚点 | 6eb12c1b8a41 | Rownership-k3-v4-20260921/spec-k3 | 同上两文件（D） | 否：dirty、非祖先、ENOSPC 原件 |

所有证据目录存在；Arena 对应关系来自各目录 `evidence/README.md` 的完整 SHA，v3/v4 来自原 README/run.json。此处不重验或升级历史审查结论。未采全 #64 的 mtime、reflog、ignored 内容与逐树授权条件；已经命中禁止条件就保留，不能把缺少其他检查读为通过。实际删除名单由 #64 重算并请用户确认。
