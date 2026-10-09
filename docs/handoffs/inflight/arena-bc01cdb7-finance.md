# inflight · arena/bc01cdb7-finance（连板日历高标配色 + 高标断板）

**状态：PR #72 已开（mergeable，base main）；origin/main 已合入本分支（落后 0）；合并 head 的 CI 待复跑。** 展开细节见 `docs/handoffs/2026-10-07-连板日历高标断板.md`（指针，本文件只留结论）。

## 分支
8dfc4162 feat(配色+断板) → 6901b33f fix(断板3边界) → 1f6bc183 fix(webapp 对比度+图例) → 4238722b docs → 94744295 fix(webapp 空格+2钉子+docs) → 2976b968 merge origin/main。

## 已修（含 QC 复核 A–E，均在未修复代码先验证为红）
- 断板3边界：配对序列 union / present_by_day(NULL在板) / 展开顺序重排（3回归测试，29 passed）。
- 前端：断板对比度 #857d71→#6f6a61(4.72:1)；图例随 payload.high_board_min；图例多余空格删；补2条前端钉子（vitest 214 passed）。
- docs：UL-doc 区分两种「断板」+ docstring 交叉引用 + 断板边界补记。
- 交接拆分：本文件≤3000B，细节移日期快照（4238722b 那份 7456B 超门禁，本快照即补救）。

## 断板口径
单只≥high_board_min(默认5)板，前一市场交易日收盘涨停、当日收盘不再涨停=断板；断于几板=前一日连板数；当日/前一日无连板行 fail-closed 不判；boards=NULL 视为在板未计板；断板日缺行情表(连板表有)则该断板不报、格子标 market_data_missing。UI 写在当天格内(淡灰芯片)。

## 未做（下一步，用户核心研究诉求）
分析层：断板后市场反应 + 上下高标间隔规律。先定口径(单一流全市场最高≥5、锚点断板→诞生 or 断板→断板、小样本+基线防伪规律)，只真库验证。

## 坑
后端 `.cache/boardcal-venv`(duckdb+pytest)+`FWP_ALLOW_ANY_PYTHON=1`；前端 `corepack pnpm`，build 用 `pnpm exec vite build`；本仓 shallow clone，merge-base 需 `--deepen` 才可见。
