# 工单：个股逻辑卡增量批次 + deepdive 管线跨机输入（P2 · 接力单）

- 状态：**接力单**——欠账主体已有在途执行，本单只做其覆盖不到的增量，**等在途队列收尾后再开工**。
- 在途执行（2026-08-28 23:39 实测 `/tmp/ima-stock-queue-0828c.status.json`）：launchd 串行队列在补 **8/13 之前缺卡的 95 家公司**的 IMA 12 章 stock_research 卡（75/95、0 失败），落到 worktree `kb-wt-ima-stock-0826`（分支 `ingest/ima-stock-logic-0826`），未提交未动 live vault；随后还排了 **8 个已有页面的题材 DeepDive**（CRO、电子化学品、商业航天、算力租赁、光刻胶、PCB、玻璃基板、液冷）。
- 目标仓：`/Users/a77/knowledge-base-private`（主）+ 用户本地目录
- 来源：2026-08-28 欠账盘点追问（用户点名 concept deepdive 与个股 deepdive）。
- 优先级：**P2**

## 0. 一句话

concept deepdive 的补充基座管线和个股逻辑卡管线的默认输入都指向 `/Users/a77/Desktop/c c/`——**用户已确认该目录在另一台电脑上**（2026-08-28），所以这两条管线在本机跑不了默认路径；且个股 deepdive 批量线停在 6 月底（454 张卡已入库审计后无新批次），此后两个月新触发题材的强势股没有逻辑卡。先跑不依赖该目录的覆盖审计出缺卡清单，需要 registry / 未入库卡时再让用户从那台电脑同步。

## 1. 证据

**多机分布（本机默认路径不可用）**：
- `<kb>/scripts/build_deep_dive_supplement_base.py`：`--registry` 默认 `/Users/a77/Desktop/c c/ima/canonical_theme_registry.json`。
- `<kb>/scripts/audit_stock_logic_card_coverage.py`：本地未入库卡目录默认 `~/Desktop/c c/个股`（可用 `STOCK_CARD_DIR` 环境变量覆盖）。
- 用户 2026-08-28 确认：`c c` 目录在**另一台电脑**上。本机（这台跑知识库仓的机器）没有副本，两个默认路径在本机为空指。

**个股 deepdive 批量线停摆**：
- `<kb>/wiki/raw/ima-stock/`：batch-runs 停在 2026-06-22，`ima-stock-ingested-454-audit-20260621.json` 是最后一次大审计，ingested 目录只有 06-21、06-22 和 `archive-backfill-al-0709`。
- 此后 7-8 月新触发题材（EDA、PCB、CPO、先进封装、光通信、医药、数字货币等，见 `<金融仓>/market_feature_store/exports/2026-08-2{6,7,8}-research-queue.md`）的强势股没有做过逻辑卡增量。

**concept deepdive 侧边界**：存量 590 candidates 的消化已有独立工单（`2026-08-28-ima-deepdive-slice-workorder.md`），新题材 DeepDive 由 kb-ingest 工单驱动；本单只负责 supplement-base 管线的断链修复，不重复做题材切片。

## 2. 范围

**做**（都在在途队列收尾之后）：① 对 **8/13 之后**（尤其 08-26~28）触发题材跑个股逻辑卡覆盖审计，与 95 家清单和 8 个题材去重后得出**残余缺卡清单**；② 残余量大再跑一个小批量增量；③ 确需 registry 或未入库卡时，请用户从另一台电脑同步指定文件（按需点名文件，不笼统要整个目录）。

**不做**：不与在途队列并行问 IMA（它的设计就是同一时间只问一次）；不碰 `kb-wt-ima-stock-0826` 树和它的分支；不猜内容重建 registry；不改两个脚本的默认路径（`c c` 在另一台电脑是多机布局现状，不是 bug——本机跑用 `STOCK_CARD_DIR` / `--registry` 显式传参）；不动 concept 切片工单的地盘。

## 3. 步骤

0. 确认在途队列已收尾（`/tmp/ima-stock-queue-0828c.status.json` 到 95/95 且题材 DeepDive 段结束，或其执行者交接说明），拿到它最终写卡的公司/题材清单作为去重基准。
1. 覆盖审计（本机可直接跑，`--local-card-dir` 传空目录即可）：
   ```bash
   cd /Users/a77/knowledge-base-private
   python3 scripts/audit_stock_logic_card_coverage.py --theme <题材> \
     --json-out wiki/raw/ima-stock/audits/coverage-<题材>-20260828.json
   ```
   题材取近三日 research-queue 的触发题材（EDA、PCB、CPO、光通信、医药等），逐个跑。
   完成判据：每个题材有 coverage json，缺卡清单（有强势表现但无逻辑卡的个股）汇总成一张表。
3. 选 1-2 个缺口最大的题材跑增量批次：对缺卡个股走 IMA 个股 deepdive（`ima-client` skill 提交 → 逻辑卡 md → `python3 scripts/apply_ima_stock_logic_to_obsidian.py` 入库），沿用 `wiki/raw/ima-stock/batch-runs/` 的既有批次产物格式。
   完成判据：批次产物 + ingested 记录 + 对应实体页逻辑卡段落三者对得上。
4. concept deepdive 补充基座（`build_deep_dive_supplement_base.py`）如需运行：先请用户从另一台电脑同步 `canonical_theme_registry.json`（及相关 JSONL 池），拿到后用 `--registry` 显式传路径；拿不到就留游标，不阻塞前三步。
5. 其余题材的缺卡清单留游标进交接。
6. 提交：知识库仓开分支 `theme-radar/stock-card-incremental-0828`，pathspec 提交。

## 4. 验收

1. 步骤 2/3 的产物不依赖 `c c` 目录即完成；若发生了跨机同步，交接里记录同步了哪些文件、放到了哪。
2. 近三日触发题材的覆盖审计 json 齐全，缺卡总数有数。
3. 至少 1 个题材的增量批次走完闭环。
4. 交接含：缺卡清单余量、下批建议题材。

## 5. 红线

- IMA 数字未经核验不落正文；逻辑卡结论标注证据硬度，二手判断不冒充 L3 硬事实。
- 8/16 口径同样适用于个股卡：没有材料不硬写。
- relations 大 JSON 用 `query_relations.py` 查。
- 禁 `git add -A`；不合 main 不推。
