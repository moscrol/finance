# 金融项目

A股量化复盘+研究工具集。数据来源：fupanhui.com API（浏览器内 XHR）、iFinD、AKShare、飞书 Bitable。

## 目录结构

```
├── db/
│   └── market_feature_store.duckdb  # canonical 本地事实库（运行时生成，不入库）
├── market_feature_store/
│   ├── schema.sql           # canonical DuckDB 表/视图定义
│   └── cli.py               # daily-full 等现役入口
├── scripts/
│   ├── sync_to_local.py    # 已退役兼容入口（不再写库）
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
# 每日复盘与 canonical 数据同步（按指定交易日运行）
python3 -m market_feature_store.cli daily-full --trade-date YYYY-MM-DD

# 信号检测
python3 scripts/detect_turning_points.py

# 板块数据回填旧入口已停用；按指定交易日统一使用 daily-full
# python3 scripts/backfill_sector_marginal.py ...  # 不要执行
```

## Chat-first Skill Workbench（本地/私有）

Workbench 是可恢复的多轮研究对话界面：每轮重新检索当前证据，并支持自动或
手动调用 Daily Review / Daily Agent。当前版本没有生产级身份认证，**只能绑定
本机回环地址或部署在受控私网，不能作为公开互联网服务**。

```bash
# Python 3.10+；推荐独立虚拟环境
python3 -m venv .venv-workbench
source .venv-workbench/bin/activate
python -m pip install -r intelligence/api/requirements.txt PyYAML "duckdb==1.4.3"

# Node.js 22 + pnpm 10.12.1；构建结果写入 FastAPI 静态目录
cd intelligence/webapp
corepack enable
corepack prepare pnpm@10.12.1 --activate
pnpm install --frozen-lockfile
pnpm build
cd ../..

# 仅监听本机
python -m uvicorn intelligence.api.app:app --host 127.0.0.1 --port 8788
```

浏览器打开 `http://127.0.0.1:8788`。LLM 未配置时会诚实降级为结构化模板，
不会阻止本地启动。环境变量、数据目录、健康检查和公开部署安全门详见
[本地私有站点运行说明](docs/workbench/local-site.md)。

## 数据流

```
fupanhui.com API ──(CDP proxy)──→ daily-full ──→ db/market_feature_store.duckdb
                                                      │
                              detect_turning_points.py / backtest_sector.py
                                                      │
                                      信号日期 + 板块边际量 → 策略分析

旧的 sync_to_local.py 只保留退役提示，不再建立第二条飞书写入路径。
```

## 环境要求

- Python 3.9+ (duckdb)
- Chrome（fupanhui 登录态）
- CDP Proxy（`node ~/.claude/skills/web-access/scripts/check-deps.mjs`）
- 飞书应用凭证（`~/.claude/shared/feishu_config.json`）
- 本地软链 `shared`（首次克隆后创建，不入库）：`ln -s ~/.claude/shared shared`
