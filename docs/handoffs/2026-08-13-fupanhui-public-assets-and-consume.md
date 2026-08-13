# 2026-08-13 · 复盘会公开资产落库 + 消费层 + 席位（#300 / #305）

代码已合 `main` @ `8dbd588d`。本文件是完工快照；残余是 **DuckDB 写窗口回补**，不是未合代码。

## 做成了什么

1. **#300** `665eade1`：复盘会公开 API → DuckDB（keywords / 相似日 / 龙头高度 / 外盘 / 龙虎榜个股 / 监管 / 核心股 / 竞价 / 事件 / 研报目录），对齐窗口 `2025-01-02 ~ 2026-08-12` **390 交易日**（与 `fact_stock_daily` 对齐；`fact_market_daily` 多 8 个 2024-12 日不纳入）。`daily-full` 一步 `sync-fupanhui-public-assets`，子任务失败隔离。
2. **#305** `8dbd588d`：席位级 `fact_dragon_seat_daily` + 机构/游资日汇总 `fact_dragon_summary_daily`；**6 个 dataset 注册进 `finance_query._DATASETS`**；duckdb-backfill skill 加「入库后必接消费层」+「收尾对齐」三段。
3. L2 逐笔：**不能**从复盘会逆向。bundle 无逐笔；K 线资金流 401；自有 ClickHouse 密码只在服务端，客户端没有。续期找 base32/hisdata 后台拿 `CH_PASSWORD`，再验 `l2-moneyflow`。

盘点正文：`docs/data-sources/fupanhui-workspace-asset-inventory-2026-08-12.md`。

## 关键发现（接手别再踩）

**入库 ≠ agent 能查到。** agent 读 DuckDB 只走 `intelligence/services/finance_query.py` 的 `_DATASETS`。#300 合进去之后，dragon/core/leader/global 在库里但从未注册，问答工具够不着。这和「授予的额度必须传到最下游」同构：表在、遥测在、消费者不在。

已注册：`dragon_summary_daily` / `dragon_seat_daily` / `dragon_tiger_daily` / `core_stock_daily` / `leader_height_daily` / `global_index_daily`。稀疏表（auction/event/regulation/mapping）**故意不注册**，收敛工具面。

另外两处「行数对、值错」：

- 外盘主键必须用**请求的 A 股日**，不能信接口 `trade_date`（DESC 回补互相覆盖，390→258）。
- 龙头高度：请求日 as-of UPSERT；趋势图历史点 `ON CONFLICT DO NOTHING`。

## 已验证

- 质检两轮 FAIL 0：定向 8 日 + `random.seed(20260813)` 随机 8 日（`skills/duckdb-backfill/scripts/qa_fupanhui_public_assets.py`）。
- Mac worktree `8dbd588d`：`FinanceQuerySpec.from_arguments` → `FinanceQuery.run` 六 dataset 均有行，`served_date=2026-08-12`，evidence `L4_structured`。
- 席位单日 2026-08-12：summary 机构 +3.82 / 游资 +1.81 / 174 席；seats 416 行 / 46 股，与公开 `/data/dragon/detail` 抽查一致。

## 回补现状（主库，不是 git）

| 表 | 覆盖 | 缺口 |
|---|---|---|
| 公开资产主体 | 390/390 | 无 |
| `fact_dragon_summary_daily` | **389/390** | `2025-01-16` `/data/dragon/all` 超时 |
| `fact_dragon_seat_daily` | **9 日**（2026-07-31~08-12，5236 行） | 60 日窗口撞写锁停；390 日全量未做（~1.8 万次 detail） |

`fact_dragon_summary_daily` **还没进** `GAP_TABLES`（棘轮：先补齐再拦断档）。core/dragon_tiger/leader/global 已进 GAP；core/global_index/global_stock 进 ROW_ANOMALY（恒定 50/5/194）。

## 下一步（写窗口内跑，勿杀 8792）

写锁在 `uvicorn intelligence.api.app` 端口 **8792**。DuckDB 单写者。不要杀该进程；等写窗口或走 `daily-full` 既有窗口：

```bash
python3 -m market_feature_store.cli sync-fupanhui-public-assets \
    --start-date 2025-01-16 --end-date 2025-01-16 --only dragon_summary
python3 -m market_feature_store.cli sync-fupanhui-public-assets \
    --days 60 --only dragon_seats --sleep 0.15
```

之后：summary 390 齐 → `fact_dragon_summary_daily` 进 `GAP_TABLES`。Mac **主树** `git pull` 后 daily-full 才带新步（当时主树有他人未提交，未代 pull）。席位 390 日全量另立项。研报正文仍 401。知识库 36 篇 fundamentals 默认不写（`FUPANHUI_KB_NOTES=1` 才写）。

## 工具沉淀盘点

| 问 | 归位 |
|---|---|
| 质检跑了两轮以上？ | 已进 `skills/duckdb-backfill/scripts/qa_fupanhui_public_assets.py`（结构门 + 对源头抽查） |
| `/tmp` 一次性脚本？ | `consume_test.py` / `dragon_backfill.sh` 不入库 |
| 门禁洞？ | `quality.py` 已棘轮；summary 未齐故未进 GAP |
| 可迁移模式？ | 「表在 ≠ 消费者在」+「主键用请求日」+「只数行数不够」→ 已写进 duckdb-backfill SKILL「收尾对齐」。本环境无 `~/harness-reference`，未回写 KIT.md |
| 为何是手法不是脚本？ | 「这张表要不要注册 dataset」要语义判断（稀疏/低查询价值故意不注册），清单比自动扫描合适 |

干净 worktree：`/Users/a77/fwp-wt-fupanhui-assets`。禁止在 Mac 主树 `/Users/a77/finance-workspace-private` 改文件（常有他人未提交）。
