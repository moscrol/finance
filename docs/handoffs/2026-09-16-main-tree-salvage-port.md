# 主检出树无主改动：封存与搬正记录 · 2026-09-16

> 背景：主检出树 `~/finance-workspace-private`（detached @ b4a35fa2，09-08）自 09-12 起累积了至少三个 session 的未提交工作，无分支、无交接、git 身份共用看不出归属。上一 session 于 17:49 把 tracked 改动封进 `salvage/main-tree-20260916`（b46c3bcf）；本轮补封未跟踪源码与文档（08de2b00，已推 gitea），并把其中两簇**生产已在用**的代码搬到基于最新主干的分支。主树本身一个文件都没动，原因见下。

## 树里有什么（逐簇）

| 簇 | 内容 | 主干状态 | 处置 |
|---|---|---|---|
| B · L2 闲鱼日包 / 百度分享源 | `scripts/moneyflow/` 5 个新脚本 + `run_l2_pipeline.sh` / `write_to_duckdb.py` 重写 + 夜跑脚本 L2 段 + l2-moneyflow SKILL / README / ops-pitfalls | 不在主干；**生产每晚 20:40 在跑**（`ops_pipeline_run_daily.source = baidu-share:xianyu-l2-7z`，09-10 起） | PR `feat/l2-share-source-port-0916` |
| A · 题材资金面板 | `sync_eastmoney_fund_flow` / `sync_theme_capital_from_baskets` + 两份测试；schema 四列 + `ops_fund_flow_5d_gap`；cli `sync-fund-flow`；river 三件按口径分组 | 不在主干；生产库已有四列与 09-11 / 09-15 数据（手动 `--direct` 写入） | PR `feat/theme-fund-panel-port-0916` |
| C · 文档 / 技能重构 | AGENTS.md、CLAUDE.md、UBIQUITOUS_LANGUAGE、load-memory hooks、dispatcher / handoff / duckdb-backfill 等 SKILL、skills.registry.json、删 3 个中文名技能 | 主干已有更新版（同区域改动，三方冲突 AGENTS 7 处等） | 不搬，留 salvage |
| D · BP v1.2 文档 | bp 母本 / deck / 申请表答案 + `build_bp_public.py` / `render_bp_pdf.py` + 对外版 + 财务 JSON | 已被 `docs/bp-v1.3-roadshow-align`（母本 v1.5，5 提交领先）取代 | 不搬 |
| E · daily-full-review SKILL 重写 + runlog / quality 状态 | — | SKILL 主干另有改法；runlog 是夜跑写进数据根的产物 | 不搬（ops-pitfalls 的 L2 段随 B 走） |
| F · 零散 | `tests/test_code_map.py`、`test_build_bp_public.py`、`.devin/config.json`、spec 文档（gap-roadmap §2.5、teaching-framework、extraction-first #53、broad-index） | 主干已有更新版 | 不搬 |
| 数据产物 | `market_feature_store/exports/` 09-07 / 09 / 14 / 15（30 份） | 主干跟踪该目录 | 已封进 salvage，未搬（夜跑数据提交另议） |

## 为什么主树成了「运营覆盖层」

装机启动器 `~/.local/bin/nightly_full_review.sh` 被手改成从 `$DATA_ROOT`（= 主检出树）执行 L2，因为代码不在冻结快照 `~/finance-workspace-runtime` 里。主干 `docs/verification/2026-09-12-l2-independence-production-writeback.md` 与 `docs/handoffs/inflight/fix-8792-qc-closeout-0913.md`「运营覆盖层」一节都记了这件事。今晚 20:40 日志：`l2_code=runtime` 只是打印，实际执行的 `scan_quant.py` 路径在主树。**回退主树 = 今晚 L2 断供**，所以不动。

## 搬运时的取舍

- 基线 `gitea/main`（db4a269a），逐文件 `git merge-file`（base = b4a35fa2）。主干这一周的修复全保留：`--repair-pct-chg`（QC E3）、三值日历判定与代码根探针（工单 #52）、DECIMAL 求和确定性、`knowledge_cutoff` 过滤、Polymarket 表。
- **L2 代码根回到 CODE_ROOT**（工单 #51 纪律），状态 / 库 / 输出走 DATA_ROOT。运营版的 DATA_ROOT 执行是权宜：分享入口 `state/l2-baidu-share.json`、日包缓存、百度 Cookie 都由 `l2_paths.py` 按 `FINANCE_DATA_ROOT` 与家目录解析，与代码根无关。原作者的测试断言相应改写并在 docstring 写明理由。
- 去掉 `l2-paused.flag` 短路（与生产一致；check 脚本仍认环境变量 `L2_PAUSED=1` 作应急开关）。
- `skills/l2-moneyflow/SKILL.md` 两边都是新文件（无共同基底），取生产侧文案。
- 日包解包口径测试从资金面板测试文件迁到 L2 单：两单互不依赖，`merge-tree` 对主干与彼此都干净。
- `check_unread_fields.py` ALLOWED 加 `sock`：`http.client` 协议属性，读取点在标准库里。

## 合入后的运维收尾（需要人拍板，合入本身不改变今晚行为）

1. 刷新 `~/finance-workspace-runtime` 到含两单的主干。
2. 重跑 launchd 安装脚本，让装机副本回到仓内版（L2 → CODE_ROOT）。
3. 观察一晚 `ops_pipeline_run_daily` 仍出 `baidu-share` 行、`feature_l2_*` 有当日数据。
4. 之后主树的运营覆盖层才可退役；`git checkout` 前再核一次装机副本与 plist。
5. `theme-flow-akshare-fallback`（09-10 未合）与 A 改同一文件 `sync_fupanhui_theme_flow_daily.py`，后合者 rebase。

## 复活整树

`git worktree add <路径> salvage/main-tree-20260916`。封存不含 `pelican-*.html`、`k3-p1-r1c.*`（草稿垃圾）、`docs/previews/2026-09-16-*.html`（另一 session 当日在途）。

## 收据

| 单 | PR | 代码提交 | 全量 pytest | 收据（`~/.finance-runtime/test-receipts/`） |
|---|---|---|---|---|
| B · L2 文件源 | [#773](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/773) | 7dc17832 + 8b4e1626（守卫先于前置件、代码根认 FINANCE_CODE_ROOT） | 11141 passed / 0 failed / 81 skipped / 2 xfailed，ruff 通过 | `20260916T132429Z-8b4e1626.json`（dirty=false） |
| A · 资金面板 | [#772](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/772) **已合入 c29a6401（2026-09-16 21:34，用户授权）** | 28c11b99 | 11163 passed / 0 failed / 81 skipped / 2 xfailed，ruff 通过；前端 lint / typecheck / vitest 107 / build 全过；e2e 34 passed / 2 skipped；registry check 一致 | `20260916T131231Z-28c11b99.json`（dirty=false） |

两单 `git merge-tree --write-tree gitea/main <branch>` 均干净，互相亦干净；#772 合入后 #773 对新主干 c29a6401 重探仍干净。B 第一轮全量曾 6 红（前置件检查早于日历守卫、`config` 裸模块名撞名），已在 8b4e1626 修掉并复现验证。前端 / e2e 叶两单都未跑（未改 webapp），合入前由合入者补跑或说明。

备份分支：`salvage/main-tree-20260916` @ 08de2b00（gitea 同步）。主树 `~/finance-workspace-private` 本轮一个文件都没动。
