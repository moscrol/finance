# V9a：kb_search 本仓换窗（2026-08-22）

> 规格：`docs/superpowers/specs/2026-08-22-kb-chunk-rerank-design.md` §3.1 A1 / §7.1
> 台账：`R-20260822-01`（pending；live 由验收方回填，本单不得 confirmed）
> 上游：`R-20260821-17` 第二腿（零信息窗换正文；本行是下游，不代结）
> 分支：`feat/v9a-kb-window-reexcerpt`
> **验收面**：给定命中页，送哪一段。不得从本文件推出邻页离开 top-k（V9b）或送达字符数量级（V3）。

## 0. 一句话

`retrieve()` 在 freshness 过滤之后、`sanitize_hits` 截 k 之前，按 `WikiHit.file_path` 读本地 wiki 页，按标题切节（抄 KB `_split_sections` 规则，不引入 KB 包），跳过结构小节黑名单，把零信息窗换成正文段。整页无正文的 pointer 丢弃，靠既有 `fetch_k` 过采样补位。认不出结构则 fail-open。

人话：检索还是把目录页递过来，送达时改翻到同一页的「一句话」；目录页自己没有正文就丢掉，让多抓的几条补上。

## 1. 判别规则

| 命中 | 机制 | 本单主张 | 不主张 |
|---|---|---|---|
| #1 长电逻辑跟踪 | 同页错段 | 窗头变成同页「一句话结论」（含封测），不再是 `cnfin.com` 清单 | 答案引用密度 |
| #2 长电实体 | 已是正文 | fail-open 保持 V5 已前置的一句话 | — |
| #3 baseline source note | 指针页 | drop，不用 `raw/cninfo-baseline/` 充正文 | 变出年报数字 |
| #4 颀中 / #5 华天 / #6 莱宝 | 邻页链接堆 | 换成**各该页自己的**正文 | 它们离开 top-k（V9b） |

独立头部判据（测试文件内字面检查，先剥 `命中块 path::N:`，不复用实现分类器）：清单头 = `cnfin.com` / `1. **` / 头 20 字含「原始资料」；wikilink 堆 = 头 200 字去掉 `[[…]]` 后剩余 <8 字。

## 2. 长电 6 命中 before / after

夹具：`intelligence/tests/fixtures/v3-kbsearch-jcet-hits.json`（V3 冻结窗）+ 页侧车 `intelligence/tests/fixtures/v9a-jcet-pages/`（从本机 wiki 原文复制，冻结后测试不再碰真索引 / 181MB `chunks.jsonl`）。

| # | 页 | before（V3 `llm_evidence` 去定位符后） | after | 处置 |
|---|---|---|---|---|
| 1 | `wiki/sources/长电科技_最新逻辑跟踪.md` | `1. **长电科技2025年度…` + `cnfin.com` 清单 | `长电科技作为国内封测龙头…`（一句话结论） | 重摘录 |
| 2 | `wiki/entities/长电科技.md` | `- **一句话**：长电科技作为国内封测龙头…` | 原样（已是正文） | fail-open 保持 |
| 3 | `wiki/sources/长电科技 2025年度报告 baseline 2026-04-08.md` | ``- `raw/cninfo-baseline/长电科技.json` `` + 分类元数据 | （无） | **drop** pointer |
| 4 | `wiki/entities/颀中科技.md` | `[[长电科技]] · [[通富微电]] · [[华天科技]]` | `- **一句话**：颀中科技…债转股/TGV…` | 重摘录（颀中自己的正文） |
| 5 | `wiki/entities/华天科技.md` | `[[长电科技]] · [[通富微电]] · [[比亚迪]]` | `全球第五大封测企业…` + 华天一句话 | 重摘录（华天自己的正文） |
| 6 | `wiki/entities/莱宝高科.md` | `[[京东方A]] · [[华勤技术]] · [[长电科技]]` | `- **一句话**：…MED项目…玻璃基…` | 重摘录（莱宝自己的正文） |

#4–6 仍在 top-k 是**排序病未愈**，不是本单失败——见 §6。

## 3. TDD 红绿

文件：`intelligence/tests/test_kb_window_reexcerpt.py`。解释器 `.venv-workbench`，cwd 本 worktree。

红（实现前，基线 `31dd63eb`，恒等桩）：

```
FFFF.FFFFFF.  10 failed, 2 passed
test_jcet1_reexcerpt_fronts_body_not_source_list
test_jcet456_no_longer_wikilink_piles
test_jcet3_pointer_is_dropped
test_synthetic_page_picks_body_across_sections
test_reexcerpt_path_does_not_call_dense_or_rerank_worker
test_remaining_under_15s_stays_bm25
test_pointer_drop_lets_oversample_fill_k
test_telemetry_new_fields_and_historical_missing_is_unjudgeable
test_identity_reexcerpt_is_not_the_default
test_empty_blacklist_is_not_the_default
```

fail-open / 6 页读预算两条在恒等下仍绿（它们锁的是「别误杀 / 读得完」，不是「必须换窗」）。

绿（实现后）：同文件 12 passed；连同 V5/V3/V4 钉 `test_kb_selection_noise_filter.py` + `test_kb_search_coarse_pipe.py` + `test_kb_index_hygiene.py` 零回退。

## 4. 变异击杀

基线提交 `654c3f08`（实现已在树上）后做，击杀 **2/2**：

1. `reexcerpt_hits` 函数开头恒等 `return items` → `test_jcet1_*` + `test_identity_*` 两钉红。收据 `~/.finance-runtime/test-receipts/20260822T025046Z-654c3f08.json`（dirty）。
2. `STRUCTURAL_SECTIONS = frozenset()` → `test_jcet1_*` + `test_empty_blacklist_*` 两钉红（#1 仍是清单）。收据 `~/.finance-runtime/test-receipts/20260822T025057Z-654c3f08.json`（dirty）。

`git checkout -- intelligence/services/kb_window_reexcerpt.py` 后 12 passed。

## 5. 预算读数

本机（worktree，不跑 live RAG / 不打 8792）：

| 动作 | 墙钟 |
|---|---|
| 读 6 个冻结本地 md | **0.44ms** |
| 6 命中重摘录（切节+换窗+drop pointer） | **1.06ms** |
| 预注册 p95 增量 | <100ms（本机两档均远低于） |

夹具断言：重摘录路径 `subprocess.run` 仍只调用一次 worker；`timeout=4`（remaining<15s）时 `effective_mode=bm25`，真值表未改。不调用 dense/rerank worker。

## 6. 诚实边界

1. **不主张排序。** #4–6 换成颀中/华天/莱宝自己的正文，槽位还在——那是 V9b。禁止写「4 条都变正文所以检索好了」。
2. **不主张送达量 / 答案质量。** `detail_chars` 可能变大，但那是 V3 的量纲；本单主判据是窗内容。
3. **#3 不发明年报数字。** baseline source note 不是年报，drop 后过采样补位。
4. **#2 不重写。** 窗已经是正文，fail-open 保持，避免误伤 `test_kb_rag` 里「命中供需章节」这类好窗。
5. **B5③ 移交 V9b。** 「过采样后丢掉结构段代表块再截 k」会把 #4–6 直接踢出 top-k，模糊 V9a/V9b 判别边界，本单不做。
6. **历史 run 缺 `reexcerpted` / `pointer_dropped` 报不可判，不报 0**（沿 V7 `detail_chars` 形状）。
7. live 由验收方用 `probe-v9a-<mmdd>` 回填，本行保持 `pending`。`R-20260821-17` 不代结。

## 7. 不做什么

- 不改 `KB_SEARCH_DETAIL_CHARS` / max_hits / 字符阶梯。
- 不改 `select_mode_for_remaining` 真值表与 15.0 阈值。
- 不动任何 timeout / `ASK_TOOL_BATCH_TIMEOUT` / 生产档位（`R-20260816-07`）。
- 不改 V5 `filter_structural_noise` 的 fail-open。
- 不扫 `chunks.jsonl` 进请求路径，不把 181MB 索引接进测试。
- 不打 8792，不跑 live 探针，不把任何台账行标 confirmed。
- 不开 V9c 跨仓重切。
