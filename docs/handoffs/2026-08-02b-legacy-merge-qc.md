# Handoff — legacy/exposure 合并质检（2026-08-02b）

**承接**：`fix/legacy-script-migration` 上的合并提交（原 `f8feb997`）。
本段做独立复核 + 修正提交正文里的三处口径 + 补一条守门测试 + 本文件。
**生产代码零改动**，唯一的代码变更是新增测试用例。
未 push、未合并 main、未重启 8792/8799、未部署。

---

## 0. 一句话现状

合并本身**可以合**：解法正确、零静默回退、门禁真绿、全量测试逐位复现。
质检推翻了原正文的三处口径（as_of 风险等级、同批文件计数、smoke 窗口结论），
均已改在提交正文源头。发现的唯一真缺口——`_mainline_theme_names` 没有真实 DB 的
`as_of` 边界断言——**已补测试并用变异反验**，全量 4034 / 13 / 3。

---

## 1. 工作区与 Git

| 项 | 值 |
|---|---|
| 工作 worktree | `/Users/a77/.merge-tmp-exposure` |
| 分支 | `fix/legacy-script-migration` |
| HEAD | `431ebcdb`（= 原 `f8feb997` 仅改提交正文，**树完全一致**，`git diff` 为空） |
| 合并父 | `7d9c7364`（legacy） + `1e128053`（exposure），amend 后未变 |
| 旧 SHA | `f8feb997` 仍在 reflog，可 `git checkout f8feb997` 取回 |
| push / main | **未 push、未合并、未动 origin/main** |
| 运行时 | 8792 PID 54180（8/1 00:17 启动）、8799 PID 12401（7/31 01:04 启动），**均未重启** |
| 蓝绿指针 | `finance-workspace-runtime` → `.finance-runtime/finance-workspace-751ef706`，mtime 8/1 00:17，完好且不指向本 worktree |
| 生产库 | 3,660,328,960 B，mtime `2026-08-02 02:10:56`，质检前后一致 |
| 工作树 | clean |

---

## 2. 复核结论

全部独立实跑，不采信原文档。

| 项 | 验证方式 | 结果 |
|---|---|---|
| 含 `1e128053` + `main` | `merge-base --is-ancestor` | ✅ |
| **`as_of` 无「收下即忽略」** | AST 遍历，逐函数查参数是否在**函数体内**被 Load | ✅ **11/11 实际使用，0 例外** |
| 两处 sys.path 注释统一 | 全仓 grep | ✅ 15 文件统一英文，中文版 0 残留 |
| `run_review_sync` 取 `audit.brief()` | 读合并后函数体 | ✅ 且 legacy 的 F841 意图未丢 |
| 两处 F401 删除等价 | 读 `connect_readonly` / grep `INDEX_ALIASES` | ✅ |
| Ruff 全仓 0 | `ruff 0.11.13`（与 pre-commit 同 pin） | ✅ `All checks passed` |
| 未新增 noqa | 逐行比对 `(file, text)` 集合，非只看总数 | ✅ **两父都没有的 noqa = 0** |
| pre-commit | 对 `78187ec7..` 实跑 | ✅ 四 hook 全绿 |
| 全量测试 | `.venv-workbench` 实跑 139s | ✅ **4033 / 13 / 3 逐位复现** |
| 13 条属宿主基线 | 读断言详情 | ✅ 真实 `/Users/a77/agent-memory` 泄漏进 tmpdir 断言 |
| benchmark 偶发判断 | 本轮独立跑 | ✅ 绿，第三个数据点 |
| **零静默回退**（原文档未做） | legacy 96 + exposure 525 个改动文件，逐个查合并后是否退回 base | ✅ **0 个回退** |
| 已删分支可恢复 | `cat-file -e` + 祖先检查 | ✅ 两 SHA 均在历史内 |
| 遗留 #1 精确性 | AST 分类 11 个用连接的函数 | ✅ 恰好只有那 2 个是内联 |
| 分支 9 / worktree 3 / 主仓干净 | `git branch -vv` / `worktree list` | ✅ |

---

## 3. 三处修正（已改进提交正文）

### ① `as_of` 的风险等级被高估——不是静默

原正文：「这类失败不报错，只是结果变空」「不在冲突标记里能看出来，要读签名才发现」。

**运行时行为的描述是对的，但「发现不了」不成立。** 变异测试实测：

| 抽掉的边界 | 结果 |
|---|---|
| `_market_data_asof` 的 `as_of` 上界 | **3 条红**，含 `test_episode_tools` 打出 `requested_date=2026-07-24 / served_date=2026-07-27` 的 `future_of_cutoff` |
| `_mainline_theme_names` 的 `theme_date` 上界 | **1 条红**，复现「题材级主线未知」清空 |

更关键：这三条守门测试 `base` 和 `legacy` 都没有，**全部来自 exposure 分支、随合并
自动带入**（`git grep -l <test名> 78187ec7 / 7d9c7364 / 1e128053` = 0 / 0 / 1）。
所以取错 legacy 体，全量一跑就红。判断和选择都对，只是风险等级不该记成「静默」。

### ② 同批文件计数

「与另外 15 个同批文件一致」→ 全仓共 **15 个**文件带这条英文注释，**含这两个冲突
文件本身**，所以是「另外 13 个」。

### ③ smoke 结论是错的，报告那个「2 笔」能复现

原遗留：「默认参数、`--overlap`、`--top 5 --hold 3 --min-marginal 8` 三组都是 1 笔
交易，6 个交易日；报告里那个 2 笔仍复现不出」。

**默认参数跑出来是全历史 2024-12-25→2026-07-31 共 68 笔，不是 1 笔。**
那组「1 笔 / 6 交易日」实际用的是 `--from 2026-07-24`：

| 窗口 | 交易日 | 笔数 |
|---|---|---|
| `--from 2026-07-24` | 6 | 1 ← 上轮实测的那组 |
| `--from 2026-07-22` | 8 | 1 |
| **`--from 2026-07-15`** | **13** | **2** ← 报告的数 |
| `--from 2026-07-14` | 14 | 2 |
| 默认（全历史） | — | 68 |

不是「复现不出」，是**窗口没对齐**。该遗留改记为「报告未标注回测窗口」。

---

## 4. 唯一真缺口：`_mainline_theme_names` 无守门测试 —— **已补**

`_mainline_theme_names` 在 4 个测试文件里**曾全部是 monkeypatch 的**
（`test_market_review_knowledge_anchor.py:39/207/212`、`test_review_followups.py:164`），
从没有过真实 DB 的 `as_of` 边界断言。§3① 那条「测试会红」**覆盖不到它**。

它的 `as_of` 是间接传播的：`as_of` → `_market_data_asof()` → `market_date` →
`where trade_date <= cast(? as date)`。链上任一环断掉，行为是主线上下文被清空。

已补 `test_ask_compose.py::DailyMarketOverviewTests::
test_mainline_theme_names_bounds_theme_date_by_as_of`，与 `test_ask_compose.py:467`
同形状：临时库数据到 07-27，传 `as_of=2026-07-24`，断言
`(theme_date, names) == ("2026-07-24", ["人工智能", "半导体"])`。

**按 §5① 反验过才算数**：只抽掉 `_mainline_theme_names` 那一处上界（不动同文件另外
两处相同查询）跑 5 个相关测试文件，**唯一红的就是这条新用例**，报
`AssertionError: '2026-07-27' != '2026-07-24'`——既证明缺口是真的（此前这处变异
无人发现），也证明新用例确实堵住了它。还原后全量 **4034 / 13 / 3**（+1 即本用例，
宿主基线 13 条不变）。

---

## 5. 可复用的两条方法

1. **说「静默」之前先做变异测试。** 把那行边界抽掉、跑相关测试文件、看红不红，
   再 `git checkout -- <file>` 还原（跑之前确认工作树干净）。红了说明有守门，
   风险降一档；绿了才是真静默。附带产出是知道**哪个函数没人守**。
2. **零静默回退检查。** 合并后逐个比对「某侧改过、但合并结果 == base」的文件集合，
   能抓住冲突标记看不出来的整块丢失。本次两侧各 96 / 525 个文件，结果 0。

**跑测试用 `.venv-workbench/bin/python`**，不要用 `python3`（是 homebrew 3.14，
缺 fastapi / yaml / duckdb，全量跑会在 collection 阶段就 `Interrupted`，看着像代码坏了）。
干净基线 = `4033 passed / 13 failed / 3 skipped`，约 140s。

---

## 6. 遗留与下一步

| # | 项 | 状态 |
|---|---|---|
| 1 | `_mainline_theme_names` 缺 `as_of` 边界测试（§4） | **已补并反验，见 §4** |
| 2 | `_mainline_theme_names` / `_market_cause_window_block_for_llm` 仍用内联 `connect_readonly` | 未做，风格不统一，不阻塞 |
| 3 | `.merge-tmp-exposure` 目录名名不副实——它已是本分支主开发 worktree，不是临时合并区 | 未做，不阻塞 |

下一步：质检发现的问题已全部处理完，可考虑 push / 合 main。**合并 main 需用户确认。**
