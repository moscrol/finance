# 2026-09-25 收口指针：第三轮受托代拍的「关 / 归档」线

授权：用户 2026-09-25 01:4x「按照最优推进」，依据 `~/.finance-runtime/reviews/pi-session-inventory-20260924/cleanup/DECISION-SHEET.md` 的建议列受托代拍；
记录见同目录 `round3-authorization.md`。这些线没有 PR，所以指针写在这里而不是 PR 评论里。**分支一条没删**，只拆检出；恢复任何一条：
`git fetch gitea && git worktree add --detach <路径> gitea/<分支>`。裁决表里写「你定」的线（runtime P1 系、E2 impl、Knevo、#77 判定表、302132 旧线）不在本文。

## 已被 main 覆盖（关）

| 编号 | 分支 | 覆盖依据 [实测] |
|---|---|---|
| C11 | `fix/citation-numeric-gate-0917`（09-17，引用序号不进数值条件） | `strip_evidence_ordinals` 已在 `gitea/main` 的 `intelligence/services/episode_protocol.py`（2 处）与 `episode_semantic_verifier.py`（3 处），随 #832 → #863 谱系进入；本枝多出的 `intelligence/tests/test_episode_numeric_citations.py`（137 行）若要补覆盖，从分支取 |
| G5 | `fix/gate-receipt-selection-0921`（09-21，选中本次 pytest 收据、保留失败退出码） | #860 已落同一机制：`scripts/run_main_gate.sh` 110–117 行 `PYTEST_LOG` + `PIPESTATUS` 取精确收据、不假定绿 |
| A7 | PR #900 `fix/recovery-release-forward-0923` | 已关，指针评论 6921 → #915（三个修复按补丁进入 eb4ec08f） |

## 归档（方向未变，但这条实现路径不再推进；代码保留在分支）

| 编号 | 分支 | 归档理由（来自各自交接） |
|---|---|---|
| C4 | `feat/research-data-readiness`（09-18） | 工程通过，「自然回答质量仍 not_passed」；病根分析被 #71 `fix/delivery-guard-structural-binding` 取代（守卫绑在模型自选列名） |
| C5 | `q/research-data-readiness`（09-19） | 冻结 QC 候选 6fb37a6e，18 项 exit 0；业务码已是 #71 分支的基座 |
| C6–C10 | `fix/8792-boundary-integration`、`fix/8792-financial-contracts-r5`、`baseline/8792-financial-r6`、`fix/8792-financial-r6-repair`、`fix/8792-readiness-boundaries`（09-17～09-19） | R3 四首题 0/4、R6 四 run 0/4 not_passed，「不晋级」；R4–R6 离线修复未改善 live。8792 现网已切到 3b7e473575b0，这批候选没有部署过 |
| F1–F3 | `baseline/capability-benchmark-00`、`feat/i1-availability-attribution`、`eval/k3nj-compat-payload`（09-09～09-11） | 基准测评线：终件 clean 13 / recovered 10 / unavailable 5，review-pack HOLD「不要开评」；k3nj 的结论（关掉判官回答也不错）已被 #830 K3 无判官采纳 |
| H7 | `data-source/broad-index-delta`（09-09） | 交接自述「只建了树，一行代码没改」；任务仍在 `docs/superpowers/specs/2026-09-09-broad-index-coverage-delta.md`，接手直接从 main 开新树 |
| H1 | `codex/feat-workbench-research-journey`（08-25） | 一个月无人动；树里 19 个未提交文件先封存到 `salvage/fwp-wt-workbench-research-journey-20260925` 再拆 |

## 核过但**没有**被 main 覆盖，留在裁决表里继续推进

- G7 `feat/continuous-research-09-live`：`LLM_COMPAT_PAYLOAD`（按模型前缀改写 / 摘除出站字段）在 main 里找不到同名或等价逻辑；8090 服务跑的就是这一版。建议前向 + PR。
- G2 `fix/fupanhui-session-hygiene`：main 的 `fupanhui_source.py` 只有 CDP proxy 说明，没有 429 熔断 / 批量串行；对 main 3 处冲突（CLAUDE.md、两份夜跑 plist）。建议前向 + PR，前向时以 main 的 plist 为准。
