# V4 索引卫生：排除工件页 + 同族折叠（2026-08-21）

> 规格：`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md` §V4（形状 V）
> 台账：`R-20260821-16`（pending；执行方不得 confirmed）
> 上游案例：`docs/verification/2026-08-21-inputside-delivery-window.md` §4
> 代码：`fix/v4-kb-index-hygiene`；只改本仓索引/检索侧，未动知识库仓页面

## 0. 一句话

本仓的索引构建入口丢掉验收/测试工件页；检索时同 slug 的 `-vN` 多版本只留最新。液冷 query 的 top-5 不再被 theme-radar 验收页挤满。

## 1. 工件页长什么样（先审计再定规则）

知识库 wiki 上现役验收页 **24** 个，**全部没有 YAML frontmatter**，只能靠路径识别：

| 形状 | 数量 | 样例 |
|---|---|---|
| `wiki/synthesis/<题材>-theme-radar-验收.md` 及 `-v2`…`-v8` | 23 | `液冷服务器-theme-radar-验收-v5.md` |
| `wiki/synthesis/` 下文件名含「验收」、非 theme-radar | 1 | `图片题材批处理流程验收_20260605.md` |

页首是 `# <题材> 题材雷达` + `生成日期`，没有 `type`/`kb_index` 字段。chunk 元数据里 `page_type=synthesis`、`tags=[]`，不足以当判别依据。

物理索引 `.rag_index/chunks.jsonl`（本机 2026-08-22 读数）：146595 chunks / 10478 页，其中 **24 页 / 977 chunks** 命中上述路径。

## 2. 判别规则（写进代码的那一份）

入口：`intelligence.services.kb_index_hygiene`。

**算工件页（排除）**——满足任一即排除：

1. 文件名含 `-theme-radar-验收`（可带 `-v<数字>`）且以 `.md` 结尾。
2. 路径组件含 `synthesis/`，且文件名含「验收」、以 `.md` 结尾。
3. frontmatter `kb_index` 为 false/exclude/skip，或 `type`/`kind` ∈ `{artifact, acceptance, test_artifact, fixture, eval_artifact}`。现役 24 页用不到第 3 条，留给以后带标记的产物。

**不算工件页（fail open，照常收录）**：

- `wiki/concepts/测试设备.md`、`wiki/entities/谱尼测试.md`（「测试」是产业词，不是测试产物）
- `wiki/synthesis/AI测试电源大功率化-serenity-alpha-20260605.md`（产品名含「测试」）
- 没有 frontmatter、路径也认不出的页

**同族折叠**：文件名 stem 匹配 `^(?P<slug>.+)-v(?P<ver>\d+)$` 的，与同目录未带版本号的 `slug.md` 视为一族，只留版本号最大的那条。认不出则 fail open：

- `报告-v2-draft.md`（`-v2` 不在 stem 末尾）与 `报告.md` **不折叠**
- `…_20260605.md` / `…_20260606.md` 日期戳 **不折叠**
- `wiki/synthesis/先进封装.md` 与 `wiki/concepts/先进封装.md` 不同目录 **不折叠**

## 3. 为什么过滤放在本仓，而不是去改知识库页

**RAG**（Retrieval-Augmented Generation，检索增强生成）的索引通常在内容仓构建。本单硬约束：只改 finance 仓；若必须挪 wiki 文件或改 frontmatter 才能达成，应停下报阻塞。

现役工件页路径已经可机械识别，所以：

| 方案 | 做什么 | 为何用/不用 |
|---|---|---|
| A. 本仓消费侧过滤（本单） | `indexable_paths` 定义「索引条目」；`kb_rag.retrieve` 过采样后丢掉工件并折叠 | 不跨仓；下次 KB `rag update` 仍会把验收页写进物理索引，但送达窗看不到它们 |
| B. 知识库仓 `rag_index.py` 建索引时排除 | 物理 `chunks.jsonl` 里就没有这些页 | 更干净，但要改另一仓，本单禁止 |
| C. 把验收页挪出 `wiki/synthesis/` | 从源头消失 | 改知识库页面，本单禁止 |

可迁移点：任何「派生索引 vs 权威源」系统都可以在**消费侧**做卫生规则，而不先改上游 dump——搜索引擎的 robots/noindex、日志管道的 PII 过滤，都是同一形状。

诚实边界：物理 `.rag_index` 仍含 24 个工件页（KB ingest 未改）。本仓「索引条目」= `indexable_paths` 的输出。验收判据「工件页在索引条目中为 0」按**这份入口**计。

## 4. 液冷 query 重放前后 top-5

query 取自 `run_20260820_032014_595378` 第一跳：`液冷服务器 产业链 拆解`，`k=5`。

命令：

```bash
cd /Users/a77/fwp-wt-v4-kb-index-hygiene
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
from intelligence.services import kb_rag
from intelligence.services.kb_index_hygiene import is_artifact_page
res=kb_rag.retrieve('液冷服务器 产业链 拆解','/Users/a77/knowledge-base-private/wiki',k=5,excerpt_chars=200,timeout=90)
print('ok', res.ok, 'n', len(res.hits))
for i,h in enumerate(res.hits[:5],1):
    print(f'{i}|{h.title}|{h.file_path}|artifact={is_artifact_page(h.file_path)}')
"
```

| # | before（`dd6ca952` 无卫生） | after（本单） |
|---|---|---|
| 1 | 液冷服务器产业新变化与新格局全面分析报告 | 液冷服务器产业新变化与新格局全面分析报告 |
| 2 | 液冷服务器-theme-radar-验收 **工件** | 英维克（002837） |
| 3 | 液冷服务器-theme-radar-验收-v5 **工件** | 申菱环境（301018） |
| 4 | 液冷服务器-theme-radar-验收-v6 **工件** | 工业富联（601138） |
| 5 | 液冷服务器-theme-radar-验收-v7 **工件** | 联创股份（300343） |

after：`artifact_in_top5=0`。过采样 `--k 21`（`fetch_k(5)`），截回调用方的 5 条。

CI 冻结夹具：`intelligence/tests/test_kb_index_hygiene.py` 里 `_LIQUID_COOLING_TOP5`，与上表 before 同形，不依赖本机 181MB 索引。

## 5. 索引审计命令与读数

```bash
cd /Users/a77/fwp-wt-v4-kb-index-hygiene
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
from intelligence.services.kb_index_hygiene import audit_served_index
print(audit_served_index('/Users/a77/knowledge-base-private/.rag_index/chunks.jsonl'))
"
```

本机读数（2026-08-22）：

| 口径 | 读数 |
|---|---|
| `physical_pages` | 10478 |
| `physical_artifact_pages` | 24（知识库仓物理索引仍有，本单不改） |
| `served_pages` | 10454 |
| **`served_artifact_pages`** | **0** |

`served_artifact_pages=0` 即 spec「工件页在索引条目中为 0」。

## 6. TDD 红绿

先红后绿。红钉位置：

```
ERROR collecting intelligence/tests/test_kb_index_hygiene.py
ModuleNotFoundError: No module named 'intelligence.services.kb_index_hygiene'
```

时刻：实现前，revision `dd6ca952`，命令：

```bash
.venv-workbench/bin/python -m pytest intelligence/tests/test_kb_index_hygiene.py -q --tb=line
```

绿：同文件 + `test_kb_rag.py` / `test_closed_loop_retrieval.py` **57 passed**。公开缝：

| 钉 | 测试 |
|---|---|
| 索引构建入口排除 theme-radar 验收 + 流程验收 | `test_index_build_entry_excludes_theme_radar_acceptance_pages` |
| frontmatter `kb_index: false` / `type: artifact` | `test_frontmatter_kb_index_false_is_artifact` |
| 「测试」产业词 fail open | `test_domain_pages_with_test_in_name_are_not_artifacts` |
| 同 slug 只留最新；跨目录不折 | `test_same_slug_keeps_latest_version_only` |
| 日期戳 / 夹心 `-v2` fail open | `test_unrecognized_siblings_fail_open` |
| 液冷冻结夹具 top-5 无工件 | `test_sanitize_drops_artifacts_and_fills_top5_with_knowledge` |
| `retrieve` 接线 + 过采样 | `test_retrieve_excludes_artifact_paths_and_overfetches` |

## 7. 变异击杀

变异前 commit：`c3988701`（实现）→ `0f2cd121`（retrieve 钉改为路径子串，避免自指断言）。
在 `0f2cd121` 上把 `_path_is_artifact` 改成恒 `return False`（排除规则删掉），已提交树未用 `git checkout --` 当删除器。

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_kb_index_hygiene.py -q --tb=line
```

击杀 3 条（4 passed / 3 failed）：

| 钉 | 红因 |
|---|---|
| `test_index_build_entry_excludes_theme_radar_acceptance_pages` | `indexable_paths` 仍含 4 个验收路径，`Lists differ` |
| `test_sanitize_drops_artifacts_and_fills_top5_with_knowledge` | 夹具重放 `3 != 2`（工件页未被丢掉，折叠后仍留验收族） |
| `test_retrieve_excludes_artifact_paths_and_overfetches` | `True is not false`，titles 含 `液冷服务器-theme-radar-验收-v7` |

未击杀（与排除规则无关，属预期）：frontmatter 钉、产业词 fail-open、同族折叠、认不出 fail-open。

`git checkout -- intelligence/services/kb_index_hygiene.py` 后 7 passed 复绿。

第一次变异（`c3988701`、retrieve 断言还调用 `is_artifact_page`）只红 2 条：接线钉因同族折叠收成 `-v7` + 自指断言仍绿。故把断言改成路径子串后再杀一次。

## 8. 不做什么

- 不改知识库仓页面、不重建物理 `.rag_index`（跨仓 / 本单边界）。
- 不把「测试」当排除词（会误伤测试设备等产业页）。
- 不折叠日期戳近重复页（认不出 `-vN` 就 fail open）。
- 不标台账 `confirmed`。

## 9. 全量门禁

- `ruff check .` 绿
- pytest **5945 passed / 0 failed / 13 skipped**（基线 5938 + 本单 7 钉）
- 收据 `~/.finance-runtime/test-receipts/20260821T162329Z-55b519a3.json`（`dirty=false`，`revision=55b519a3`，`check_test_receipt.py` 可采信）

## 10. live 复算（2026-08-22 10:18，验收方）

台账 `R-20260821-16` 的 live 腿。生产身份：8792 health `loaded_tree_fingerprint`==`repo_tree_fingerprint`==`1816421c…`（V5 部署窗，快照标签 `6320b3bc` 滞后，按既有结论以指纹为准）。

先澄清一个口径：记分板上「确认生产索引是否已按新排除规则重建」是伪问题——本单选的是 §3 方案 A（消费侧过滤），物理 `.rag_index` **按设计不重建**。live 复算的真判据是：①部署树代码含 V4 接线；②用部署树代码审计生产索引条目；③液冷 query 经部署树重放。

| 判据 | 读数 | 结果 |
|---|---|---|
| 部署树 V4 接线 | `kb_index_hygiene.py` / `kb_rag.py` 与 gitea/main `diff -q` 逐字节一致 | ✅ |
| 索引审计（部署树代码 × 生产 `chunks.jsonl`） | physical_pages=10478 / physical_artifact_pages=24 / served_pages=10454 / **served_artifact_pages=0** | ✅ |
| 液冷重放（部署树 `kb_rag.retrieve`，同 §4 命令） | top-5=产业报告/英维克/申菱环境/工业富联/联创股份，artifact 0/5，与 §4 after 表逐行一致 | ✅ |

复算命令与 §4/§5 相同，仅 `cd` 换成部署树 `~/.finance-runtime/finance-workspace-6320b3bcbf82`。台账行翻 `confirmed`。物理索引里的 24 个工件页仍在（`physical_artifact_paths` 全清单见审计输出），若知识库仓日后在构建侧排除（§3 方案 B），本节读数是 before 基线。
