# V10：换题泛化电池（2026-08-22）

> 规格：`docs/superpowers/specs/2026-08-22-r3-capability-alignment-batch-design.md` §B2
> 台账：`R-20260822-04`（pending；执行方不得 confirmed/refuted）
> 分支：`feat/v10-generalization-battery`
> **验收面**：评测基建。不改 `_repair` / `select_mode_for_remaining` / V5 / V9a 生产行为。电池真跑归验收方。

## 0. 一句话

0 档离线扫 wiki `##` 节标题，量黑名单覆盖与变体盲区；另交 held-out 探针电池脚本（mock 单测绿，禁默认 8792）。人话：先数目录页上到底有哪些「相关实体」变体，再留一组没练过的题给验收方去打。

## 1. 交付物

| 件 | 路径 |
|---|---|
| 审计脚本 | `scripts/audit_kb_section_coverage.py` |
| 电池脚本 | `scripts/run_probe_battery.py` |
| 题池 | `intelligence/eval/probe_pool/heldout-v1.json` |
| 台账行 | `docs/prediction-ledger.md` `R-20260822-04`（逐字抄 spec，outcome=pending） |

## 2. 离线审计真跑

命令（只读，worktree，不打 8792，不读 `chunks.jsonl`）：

```
.venv-workbench/bin/python scripts/audit_kb_section_coverage.py \
  --wiki-root /Users/a77/knowledge-base-private/wiki
```

| 读数 | 值 |
|---|---|
| wiki_root | `/Users/a77/knowledge-base-private/wiki` |
| pages_scanned | **10508**（unread=0） |
| heading_types | 1349 |
| `blacklist_heuristic_coverage` | **1.000**（6/6 黑名单名被启发式认成结构节） |
| `blacklist_corpus_coverage` | **1.000**（6/6 都在语料里出现） |
| 盲区（结构候选 ∧ 不在黑名单 ∧ 页数≥20） | **13** |

黑名单语料出现：相关概念 3618 / 相关实体 2801 / 使用口径 2064 / Raw / Manifest Trace 2019 / Source 分类 2019 / 原始资料链接 1449。

### 盲区清单（按页数）

| 节标题 | 页数 |
|---|---:|
| 来源 | 378 |
| 观察列表 | 310 |
| 当前实体暴露 | 265 |
| 所属上位概念 | 265 |
| 仅更新图谱 | 243 |
| 所属主干 | 212 |
| 相关公司/实体 | 210 |
| 关键标的 | 142 |
| 概念关系 | 115 |
| 观察列表（不进图谱，待确认） | 84 |
| 关键公司 | 28 |
| 产业链与相关概念 | 26 |
| 十、原始资料链接 | 26 |

审计腿的可证伪预测（「至少 1 个 ≥20 页变体」）在本机语料上**有读数**；按合同不把台账标 confirmed——结案权在验收方。盲区非空 → 黑名单扩展另立后续单。

## 3. 题池

`heldout-v1`：9 题 / 9 题材 / concept·stock·chain 各 3。不含「长电科技怎么看」「液冷服务器产业链怎么看」及钙钛矿。

| id | kind | theme | question |
|---|---|---|---|
| h1 | concept | 可控核聚变 | 可控核聚变现在怎么看 |
| h2 | stock | 北方华创 | 北方华创怎么看 |
| h3 | chain | 铜缆高速连接 | 铜缆高速连接产业链上下游怎么拆 |
| h4 | concept | 脑机接口 | 脑机接口这波发酵到哪了 |
| h5 | stock | 海光信息 | 海光信息最近基本面怎么看 |
| h6 | chain | 工业母机 | 工业母机产业链怎么看 |
| h7 | concept | 卫星互联网 | 卫星互联网这个方向怎么看 |
| h8 | stock | 新易盛 | 新易盛怎么看 |
| h9 | chain | 氢能源 | 氢能源产业链怎么拆 |

静态钉：`intelligence/tests/test_heldout_pool_isolation.py`（其它测试文件不得出现题池路径）。

## 4. 单测红绿

解释器 `.venv-workbench`，cwd 本 worktree。

| 文件 | 读数 |
|---|---|
| `test_audit_kb_section_coverage.py` | 8 passed |
| `test_run_probe_battery.py` | 6 passed |
| `test_heldout_pool_isolation.py` | 2 passed |
| 合计 | **16 passed** |

电池单测全 mock HTTP：`--base-url` required、无 8792 默认；`PYTEST_CURRENT_TEST` 下真 `http_json` 抛「拒绝真联网」。

全量收据在最终 HEAD 提交后跑，号见交付回复 / PR。本文件提交时不事后改写，以免破坏 `check_test_receipt.py` 对最终 HEAD 的可采信。

## 5. 变异击杀

实现已在工作树、单测绿之后做，**2/2**，打完立即还原。

1. `is_structural_heading` 函数体首行 `return False` → `test_heuristic_covers_every_blacklist_name`（覆盖率 0≠1）+ `test_frozen_corpus_ranking_and_blind_spots`（变体不再被标结构）两钉红。收据 `~/.finance-runtime/test-receipts/20260822T044427Z-6f761366.json`（dirty）。
2. `is_body_header` 函数体首行 `return True` → `test_body_header_false_on_structural_title` + `test_body_header_rate_zero_when_all_structural`（报告 1.0≠0）两钉红。收据 `~/.finance-runtime/test-receipts/20260822T044436Z-6f761366.json`（dirty）。

`git` 还原后 16 passed。

## 6. 诚实边界

- **电池未真跑**。脚本交 mock 单测；首轮 live 归验收方（`probe-battery-<mmdd>`），本单不碰 8792。
- **未改生产代码**。`STRUCTURAL_SECTIONS` 只读；不扩黑名单（盲区另立后续单）。
- **审计默认不扫 `raw/`**。`raw/` 是 ingest 原文，不是 kb_search 换窗读的实体/概念/来源页；扫进去会淹没节名排行。`.rag_index` / `chunks.jsonl` 按合同禁扫。
- **只计 `##` 二级节**。`#` 页名、`###` 日期条目不计。与黑名单同级。
- **启发式是规则不是语义模型**。「产业链与相关概念」因含子串「相关概念」被标结构，可能偏宽；「十、原始资料链接」是带序号的同义变体。扩黑名单前要人审。
- **覆盖率 1.0 只说明黑名单 6 个名字被启发式认出来**，不说明黑名单已穷尽变体——盲区 13 条才是预测要找的东西。
- 题池避开了合同点名的三组题，以及长电/液冷/钙钛矿家族；不保证从未出现在其它单测的问句里当过例子。
- 台账 outcome 保持 `pending`。

## 7. 验收怎么跑电池（验收方）

```
.venv-workbench/bin/python scripts/run_probe_battery.py \
  --base-url http://127.0.0.1:<sidecar> \
  --user probe-battery-<mmdd> \
  --json-out /tmp/heldout-v1.json \
  --md-out /tmp/heldout-v1.md
```

不要把 `--base-url` 指到生产 8792，除非验收合同另写。

## 8. live 首轮（2026-08-22 13:49，验收方）

台账 `R-20260822-04` 两腿的验收方读数。生产身份：#338/#339/#340 合入后部署，
8792 health 指纹 `fb7a0d5d…`（639 模块）。

**口径声明**：本轮 `--base-url` 指生产 8792——R3 spec §B2 行文「电池首轮归验收方」
即本节所指的验收合同；基线目的就是采集生产在 held-out 题上的行为，与 R2 以来
`probe-v8/v9a/v9b-0822` 全部打生产同法。探针用户 `probe-battery-0822` 隔离，
不污染主账号。

### 8.1 审计腿（可证伪预测）——验收方独立复算

验收方在部署树自跑 `audit_kb_section_coverage.py --wiki-root <知识库>/wiki`：
盲区 **13 条**（≥20 页），Top 与执行方 §2 逐条一致（来源 378 / 观察列表 310 /
当前实体暴露 265 / 所属上位概念 265 / 仅更新图谱 243 / 所属主干 212 /
相关公司/实体 210）。预测「至少 1 个 ≥20 页盲区」实测 13 个 → 审计腿成立。

### 8.2 电池腿（首轮基线，不判 pass/fail）

`probe-battery-0822`，9/9 completed（中途一次进程被环境收割重跑，孤儿 run 3 个
不入报告；报告只收本轮 9 会话）。报告 `/tmp/battery-0822.{json,md}`，摘要：

| 读数 | 值 | 注 |
|---|---|---|
| `body_header_rate` | **1.0**（8/8 可判题） | 换题后 KB 证据头零结构节——V9a 泛化的直接证据 |
| `reexcerpted_rate` | 0.267 | 重摘录在 held-out 题上真实开火（h2 北方华创 0.5 最高） |
| `pointer_dropped` 分布 | 全 0（5 个有 KB 遥测的 run） | held-out 题未触发指针页，与长电题（drop=1）形状不同，属正常 |
| KB 参与度 | 5/9 题 episode 计划调了 kb_search | h3/h4/h5/h7 走了其他工具路线；episode 层工具选择随机，与 V9b live 探针观察一致 |
| h7 卫星互联网 | 无任何可判 KB 证据 | body_header=None 如实记 None 不记 0（合同要求） |

首轮为基线采集，无 pass/fail；黑名单扩展单落地后用同题池做前后对照。
