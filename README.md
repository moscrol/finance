# 金融项目

A股量化复盘+研究工具集。数据来源：fupanhui.com API（浏览器内 XHR）、iFinD、AKShare、飞书 Bitable。

## 目录结构

```
├── db/
│   ├── schema.sql          # DuckDB 表定义
│   └── market.duckdb       # 本地分析数据库（列存单文件）
├── scripts/
│   ├── sync_to_local.py    # 飞书 → DuckDB 同步
│   ├── detect_turning_points.py  # MA5峰谷+放量信号检测
│   ├── backfill_sector_marginal.py  # 板块边际量历史回填（CDP代理抓取）
│   └── backtest_sector.py   # 板块边际量策略回测
├── skills/                 # 各分析模块的 SKILL.md（Claude Code skill 定义）
│   │                       #   注：ingest 类 skill（pdf/concept/entity-delta/baseline）已迁至知识库仓 skills/（2026-06-12）
├── shared/                 # → ~/.claude/shared（飞书工具库）
└── CLAUDE.md               # AI agent 项目指令
```

## 快速开始

```bash
# 初始化数据库
mkdir -p db && duckdb db/market.duckdb < db/schema.sql

# 飞书同步（需要 feishu_config.json 凭证）
python3 scripts/sync_to_local.py

# 信号检测
python3 scripts/detect_turning_points.py

# 板块边际量回填（需要 CDP proxy + fupanhui 登录态）
python3 scripts/backfill_sector_marginal.py 2026-05-19,2026-05-20 <CDP_TARGET_ID>
```

## 数据流

```
fupanhui.com API ──(CDP proxy)──→ backfill_sector_marginal.py ──→ DuckDB
                                  └──→ 飞书 Bitable (sector_daily)
                                  └──→ 飞书电子表格 (sector_marginal_sheet)
飞书 Bitable ──(API)──→ sync_to_local.py ──→ DuckDB
                                    │
                    detect_turning_points.py ←── DuckDB
                    backtest_sector.py ←── DuckDB
                                    │
                            信号日期 + 板块边际量 → 策略分析
```

## 环境要求

- Python 3.9+ (duckdb)
- Chrome（fupanhui 登录态）
- CDP Proxy（`node ~/.claude/skills/web-access/scripts/check-deps.mjs`）
- 飞书应用凭证（`~/.claude/shared/feishu_config.json`）
