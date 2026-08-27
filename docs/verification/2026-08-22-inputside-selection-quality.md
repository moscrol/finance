# V5：kb_search 选段结构噪声过滤（2026-08-22）

> 规格：`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md` §V5
> 台账：`R-20260821-17`（pending；live 由验收方回填，本单不得 confirmed）
> 上游：`docs/verification/2026-08-21-inputside-delivery-window.md`（形状 IV）
> 分支：`feat/v5-selection-noise-filter`
> **验收面**：选段质量（结构噪声占比、正文是否前置）。不得从本文件推出送达字符量或答案质量——那是 V3 / live（R-12 预测③：送达变大 ≠ 选段变好）。

## 0. 一句话

`kb_search_hit_text` 在 `llm_evidence or display_excerpt or excerpt` 之后、送达截断之前，剥掉可机械识别的结构包装（`# 标题 tags: … section: … >`、YAML frontmatter、`命中块/相邻块 path::N:`），再丢掉来源清单项、wikilink 堆、纯路径行、表格分隔符。认不出就放行；整段皆噪声则保留去包装文本，不加长度上限。

## 1. 新旧选段对比读数

夹具：

- 长电：`intelligence/tests/fixtures/v3-kbsearch-jcet-hits.json`（V3 冻结，不重跑 live RAG）
- 钙钛矿：`intelligence/tests/fixtures/v5-kbsearch-perovskite-hits.json`（从 `probe-r2-live-0822` / `run_20260822_041251_127897` 的 `evidence[].detail` 冻结；验收复算走夹具，不读 run 目录）

独立头部判据（测试文件内字面检查，不复用实现分类器）：标签汤 = 头 120 字同时含 `tags:` 与 `section:`；定位符 = 以 `命中块`/`相邻块` 开头；路径行 = 以 ``- `raw/`` 开头。

### 1.1 钙钛矿（形状 IV 活体：噪声头吃掉 observation[:80]）

| # | 命中页 | 旧头（V3 detail） | 新头（V5） | 噪声比 raw→out | 正文前置 |
|---|---|---|---|---|---|
| 1 | 曼恩斯特（301325） | `# 曼恩斯特… tags: 锂电设备… section: … >` | `Baseline 产业链暴露 \| [[钙钛矿]] \| …GW级涂布…` | 0.242→0 | 是 |
| 2 | 大胜达_603687_最新逻辑跟踪 | `# 大胜达… tags: … section: … >` | `四、证据与来源链 \| 纤纳光电7683万…` | 0.174→0 | 是 |
| 3 | 金银河（300619） | `# 金银河… tags: … section: … >` | `速览 \| 维度 \| 内容 \| …` | 0.310→0 | 是 |
| 4 | 杭州柯林个股逻辑卡 | `# 688611_杭州柯林… tags: …` | `业务验证矩阵 \| 产能 \| **钙钛矿**：百兆瓦…` | 0.244→0 | 是 |
| 5 | 杭萧钢构（600477） | `# 杭萧钢构… tags: …` | `Baseline 待核实问题 - …` | 0.354→0 | 是 |
| 6 | 捷佳伟创_最新逻辑跟踪 | `# 捷佳伟创… tags: …` | `业务验证矩阵 \| **产品** \| TOPCon/HJT/钙钛矿设备…` | 0.241→0 | 是 |

汇总：

| 指标 | 旧 | 新 |
|---|---|---|
| 标签汤头 | **6/6** | **0/6** |
| 噪声比（6 条均值） | **0.261** | **0.0** |
| observation 第一条 `title：detail[:80]` | `曼恩斯特…：# 曼恩斯特… tags: …` | `曼恩斯特…：Baseline 产业链暴露 \| [[钙钛矿]] \| …涂布…` |

observation 总长仍约 580 字（6×`[:80]` 预算未改）。主张的是**头 80 字从标签汤换成正文**，不是摘要变长。

### 1.2 长电（形状 IV 原案）

| # | 命中页 | 旧头（V3 `llm_evidence`） | 新头 | 噪声比 | 说明 |
|---|---|---|---|---|---|
| 1 | 长电科技_最新逻辑跟踪 | `命中块 wiki/sources/…::24:` + 来源清单 | `1. **长电科技2025年度…`（清单） | 0.994→0.993 | 窗口内无正文，fail-open 保留清单 |
| 2 | 长电科技（600584） | `命中块 wiki/entities/…::38:` | `- **一句话**：…封测龙头…` | 0.105→0.0 | 正文前置 |
| 3 | 2025年度报告 baseline | `命中块 …::2:` + ``- `raw/cninfo-baseline/…` `` | `- **分类**：annual_report_baseline / L2` | 0.478→0.0 | 路径行去掉，剩元数据 |
| 4 | 颀中科技 | `命中块` + wikilink 堆 | wikilink 堆 | 0.992→0.983 | 邻块也是链接堆，fail-open |
| 5 | 华天科技 | 同上 | wikilink 堆 | 0.995→0.994 | 同上 |
| 6 | 莱宝高科 | 同上 | wikilink 堆 | 0.991→0.979 | 同上 |

汇总：

| 指标 | 旧 | 新 |
|---|---|---|
| 定位符头 | **6/6** | **0/6** |
| 噪声比（6 条均值） | **0.759** | **0.658** |
| 实体页正文是否在头 40 字 | 否（被 `命中块 path::` 挡住） | 是（`一句话`） |

均值降幅小于钙钛矿，是因为 4 条冻结窗口里没有可替换正文——过滤层不能发明邻页之外的段落。

## 2. TDD 红绿

文件：`intelligence/tests/test_kb_selection_noise_filter.py`。解释器 `.venv-workbench`，cwd 本 worktree。

红（实现前，基线 `4fb6873c`，只有测试+夹具）：

```
FFFF...F  5 failed, 3 passed
test_synthetic_page_selects_body_not_source_list
test_perovskite_fixture_fronts_body_not_tag_soup
test_perovskite_observation_head_is_not_tag_soup
test_jcet_replay_noise_heads_drop_and_body_fronted
test_identity_passthrough_is_not_the_default
```

收据：`~/.finance-runtime/test-receipts/20260821T203458Z-4fb6873c.json`（当时树脏，只作红灯形状，不作全量基线）。

绿（实现后 `e84e6ab9`）：同文件 8 passed；连同 `test_kb_search_coarse_pipe.py` + `test_agent_research.py` 共 46 passed。

## 3. 变异击杀

基线提交 `e84e6ab9`（实现已在树上）。把 `filter_structural_noise` 改成恒等放行（函数开头 `return original`），然后：

```
FFFF...F  5 failed, 3 passed
```

与实现前同一组 5 钉。fail-open / 不加长度上限两条在恒等下仍绿（它们锁的是「别误杀 / 别截断」，不是「必须过滤」）。

`git checkout -- intelligence/services/kb_selection_noise.py` 后 8 passed。

收据：变异红 `~/.finance-runtime/test-receipts/20260821T203844Z-e84e6ab9.json`（dirty，未提交的恒等改动）；还原绿 `~/.finance-runtime/test-receipts/20260821T203847Z-e84e6ab9.json`（dirty=false）。

## 4. 复算命令

```bash
cd /Users/a77/fwp-wt-v5-selection

# TDD
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_kb_selection_noise_filter.py

# 夹具头对比（不跑 live RAG）
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
import json
from pathlib import Path
from intelligence.services.kb_selection_noise import (
    filter_structural_noise, structural_noise_ratio,
)
for label, path in (
    ('perovskite', 'intelligence/tests/fixtures/v5-kbsearch-perovskite-hits.json'),
    ('jcet', 'intelligence/tests/fixtures/v3-kbsearch-jcet-hits.json'),
):
    hits = json.loads(Path(path).read_text())['hits']
    print('==', label, '==')
    for hit in hits:
        raw = hit['llm_evidence']
        out = filter_structural_noise(raw)
        print(hit['title'], 'ratio', round(structural_noise_ratio(raw), 3),
              '->', round(structural_noise_ratio(out), 3))
        print('  raw', raw[:60].replace(chr(10), ' '))
        print('  out', out[:60].replace(chr(10), ' '))
"
```

## 5. 诚实边界

1. **不主张送达量**。过滤只删噪声，钙钛矿 observation 仍约 580 字；V3 的 6 条 / `detail_chars=0` 未改。
2. **不主张答案质量**。本单无 live 探针，不得从选段头改善外推引用密度或公开稿。
3. **spec「4 条零信息 excerpt 变正文段」未全兑现**。长电冻结 `llm_evidence` 里，来源清单（#1）与三条 wikilink 堆（#4–#6）窗口内没有正文可换；按预注册 fail-open 保留。能兑现的是：定位符头 6/6→0、路径行不再当头、#2 正文前置、#3 不再是纯路径。
4. **不做语义重排 / rerank**。邻块若也是链接堆，不会去库里另挑 chunk。
5. **不加第二套长度阶梯**。`KB_SEARCH_DETAIL_CHARS` 仍为 0。
6. **噪声比函数与过滤器同源**，只作验证读数；测试期望用独立字面头部检查，避免同语反复。
7. live 由验收方回填，本行保持 `pending`。

## 6. 不做什么

- 不改 V3 送达规格（max_hits / detail_chars / 粗管道字段优先级）。
- 不改 `tool_result_budget` 的 240/900，不改 observation `[:80]` 预算。
- 不写 kb telemetry 新字段（V7）。
- 不打生产 8792/8803，不部署。
