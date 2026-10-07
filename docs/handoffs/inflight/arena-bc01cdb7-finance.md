# inflight · arena/bc01cdb7-finance（连板日历高标配色 + 高标断板）

> 分支已推到 `origin/arena/bc01cdb7-finance`。三个提交：`8dfc4162`(feat 高标配色+断板) → `6901b33f`(fix 断板三处边界) → `1f6bc183`(webapp 对比度+图例联动)。PR 未开，等用户检查后再建。

## 这个分支做什么
用户先要熊猫骑摩托 HTML（未提交），后要求看既有连板日历 + 时间记忆长河 dashboard，再加：**>5 板（≥6 板）紫色高标**、**高标断板日标记（收盘不再涨停即断板、≥5 板）**，并抱怨首版断板 UI「有点乱」。

## 断板的最终口径（用户确认）
- **断板** = 单只 ≥ `high_board_min`（默认 5）板的个股，前一*市场*交易日**收盘**涨停、当日**收盘**不再涨停。炸板算断板（与仓内「炸板不分」一致）。
- **断于几板** = 断板前一交易日的连板数（`height_at_break`）。
- **fail-closed**：断板日或其前一日在连板表**无任何行**则不判（缺数据 ≠ 未封）。当日有行但 `boards=NULL` 视为「在板未计板」，**不算**断板（`present_by_day`）。
- UI：断板写**在当天那格**，用一个「断板」分组 + 同族实心圆角芯片（**淡灰 `#6f6a61`**），风格统一、不另占月度 strip。（v1 的「玫红虚线徽章 + 顶部月度 strip」已按用户「有点乱」撤掉。）

## 后端（`intelligence/services/board_calendar.py`）
- `_high_board_breaks(trading_dates, sealed_by_day, present_by_day, board_data_dates, high_board_min, leading_day)`：
  - 配对序列 = `sorted(trading_dates ∪ board_data_dates ∪ {leading_day})`（行情表缺某天时，断板高度仍读最近有数据的交易日，不是更早缺口日）；只报范围内的行情日。
  - 断板判定用 `code in present_by_day[day]`（当日有行即在板），`sealed_by_day` 只用来取高度（NULL 行不进去）。
  - `flattened = [e for day in trading_dates for e in per_day[day]]`（与分日高度降序一致，不再用插入序）。
- `_previous_market_trading_day`：范围首日的前一个市场交易日（跨月/首日断板可判）。
- `build_board_calendar` 返回每格 `high_board_breaks`（事件字段 `date/stock_ts_code/stock_name/height_at_break/theme`）+ 顶层 `high_board_breaks`/`high_board_min`；missing/unavailable/no_market_data 三条早退路径同 schema。
- API `intelligence/api/app.py`：`/api/workbench/board-calendar` 增可选 `high_board_min`(1-20)。
- docstring 交叉引用 `leader_succession.py`，并指向 UL-doc 区分两个「断板」。

## QC 审查（用户贴来「这份审查对不对」）→ 三个「真问题」全部复现为真并修
1. 配对序列原为 `[leading_day]+trading_dates`，会跳过「只有连板表、行情表缺」的日子 → 高度读错。**修**：union 序列。
2. `sealed_by_day` 构建 `if b_boards is None: continue` 丢行 → NULL 行被误判「不在板」= 误报断板（fail-open，与 docstring 的 fail-closed 矛盾）。**修**：`present_by_day`。（latent，非 live：入库目前只对 `status_type=='U'` 写 int 板数。）
3. 顶层 `flattened` 是插入序，只有 `per_day` 排了高度降序。**修**：从 `per_day` 重排。
- 3 条回归测试**先在未修复代码上验证为红**，修复后全绿。

## 前端（`intelligence/webapp/src`）
- `BoardCalendarDashboard.tsx`：>5 板用 `--x5` 紫相；断板为当天格内的「断板」分组（实心淡灰芯片）；摘要瓦片 + 图例的「≥N 板」均读 `payload.high_board_min ?? 5`（图例不再硬编码 5）。
- `styles.css`：`.board-calendar-stock--break` / `--group-title--break` = `#6f6a61`（9px 小字 3.57:1→**4.72:1**，过 WCAG AA，仍是同族淡灰）。
- 部署约定：改 `webapp/src` → `vite build`（outDir=`intelligence/api/static`，emptyOutDir）→ 重提交 `index.html` + 带哈希 assets。当前提交 = `index-enST7TjP.js` / `index-D_bQm86_.css`。
- `high_board_min` 目前**前端不可达**（`api.ts getBoardCalendar(month, minBoards?)` 不传它，只能吃默认 5）；图例已按 payload 联动，若日后暴露成可配即自动跟随。

## 已验证
- 后端：`intelligence/tests/test_board_calendar.py` **29 passed**（断板基础 6 + 三处边界回归 3 + 既有 20）；`ruff` 干净。跑法：`FWP_ALLOW_ANY_PYTHON=1 ./.cache/boardcal-venv/bin/python -m pytest …`（venv=duckdb+pytest，非 `.venv-workbench`）。
- 前端：`vitest` **212 passed（22 文件，含 BoardCalendarDashboard 8）**、`tsc` 干净、`eslint` 干净；`vite build` 3s，产物含 `#6f6a61`、图例 `high_board_min??5` ×2、`#857d71` 已移除。
- 对比度：`#857d71/#f2f0ec`=3.57:1 FAIL → `#6f6a61/#f2f0ec`=4.72:1 PASS（脚本核验）。
- 已知 flaky：`components.test.tsx` 有 2 个聊天轮询测试在本沙箱偶发超时，A/B 证明与本次改动无关（干净树同超时），非回归。

## 未验证 / 已知边界
- 无生产市场库/日报；合成演示数字、股票、工作日均为演示，不签真内容/生产部署。
- `high_board_min` 的可达性（要不要前端可配）留待用户拍板。

## 分析层（用户核心研究诉求，**下一步，未做**）
用户要研究：(a) 高标断板后**市场**发生什么；(b) 上下两任高标之间的**时间间隔**是否有规律。
需先定口径：(1) 间隔要在**单一流**（全市场最高≥5）上有意义，而非所有≥5个股；(2) 间隔锚点 = 断板日→下一任诞生日（对齐 `leader_succession` 的 `gap_days`）或断板→断板；(3) 小样本 + 无基线 = 伪规律（复用仓内四态统计门/基线法）；(4) 只能真库验证，合成演示出不了「结论」。待用户拍口径后接六轨/复盘数据实现。

## 分支状态 / 流程
- `origin/arena/bc01cdb7-finance` = `1f6bc183`。PR 未开（用户「我到时候再检查下」）。
- 分支落后 main 6 个提交（PR #68/#69 的 task_frame/turn_controller/episode_*，与本分支**无文件重叠** → rebase 应干净）。CI（workbench-check/registry-check）只跑在 `pull_request` 或 push `main`，本分支还没跑过。
- 仓库已 PUBLIC；`AGENTS.md:59` 的 branch-protection 说明已过时（当前 token 对 protection settings 403，改不了 required checks）。
- **本地分支指针曾被重置**：某回合后本地 `arena/bc01cdb7-finance` 被 reset 回 base `ea217633`（特性变未提交工作区改动）；`origin` 完好。恢复法：`git reset 8dfc4162`（工作区匹配）后再继续提交。教训：别信本地 `git log`，看 `origin/` ref。
- QC 会话绑在另一分支（arena/bf2d616d），清掉了自己的 worktree/venv/diff；本会话据其文字描述复现+修复。

## 未提交（有意留在工作区）
`panda-ride.html`、`intelligence/webapp/preview/`（合成演示 + fixtures + playwright）、`.cache/`（venv/字体/截图/日志，本地 exclude）。

## 踩过的坑
- Chromium 从 npm 本地装 + 解出 al2023 库 + GitHub 取 Noto CJK 字体保证截图中文字；依赖/字体/截图放 `.cache` 不提交。
- `vite build` 用 `corepack pnpm exec vite build`（`pnpm build` 里嵌套的 `pnpm typecheck` 会 pnpm-not-found）；esbuild 二进制在 `.pnpm` store（pnpm 10 跳过 postinstall 但仍可用）。
- Python 测试要 `.cache/boardcal-venv`(duckdb+pytest) + `FWP_ALLOW_ANY_PYTHON=1`，非 `.venv-workbench`。
