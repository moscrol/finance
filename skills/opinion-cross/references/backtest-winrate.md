# T+N 盘后回测 + 机构胜率

## b 阶段：T+N 盘后回测 + 机构胜率（已实现）

把 opinion-events.jsonl 的「看多」事件按 `source_id` 聚成**机构胜率榜**，回答「哪个卖方机构胜率更高」。
行情只用免费公开接口（新浪 suggest 名称→代码 + 腾讯前复权日线 + 指数基准），**不依赖** eastmoney/iFinD/duckdb/飞书凭证。

- `price_lib.py`：`name2code`（新浪 suggest，精确名匹配）/ `qfq_daily`（腾讯前复权）/ `index_daily`（指数基准）/ `fwd_metrics`（T+3/5/7/10 收益 + 区间最高收益 + 峰值天数 + 峰值后回撤 + 相对基准超额）。范围感知磁盘缓存落仓外 `WINRATE_CACHE`（默认 `~/kb_work/winrate_cache`，不进 git）。
- `build_outcomes.py`：筛「看多」且非 `[晨汇转述]` → 解析代码 → 抓前复权价 → 算指标 → 写 `outcomes.jsonl`。进场 = 报告日**次日开盘**；窗口不完整的事件标 `*_complete=false`。
- `winrate_rank.py`：join `sources.json` 聚合机构胜率。**主口径 = T+N 相对沪深300 超额收益 > 0**（默认 T+5），同时给绝对收益口径；只排**有效看多 ≥ N 次**（默认 5）的机构，1~2 次样本视为噪音不排。
- `refresh_winrate.py`：**一键刷新** = `build_outcomes` → `winrate_rank`（默认 T+5+T+10）。报告写仓外 `--report-dir`（默认 `~/kb_work/winrate/winrate_T{N}_{date}.md`，不提交）。
- `render_winrate_html.py`：**胜率榜可视化**。复用 `winrate_rank.aggregate_winrate` 一次算 T+3/5/7/10 四窗内联进自包含暗色 HTML（对齐复盘/策略页风格），前端切换窗口、点表头排序、画「超额胜率柱状图」+「均超额 vs 均回撤 风险收益散点」。默认输出 `复盘/winrate/winrate-<date>.html`（生成物，零依赖、双击即开、不提交）。

```bash
# 一键刷新（补完数据后跑这一条即可；日期自动取到今天）
python3 skills/opinion-cross/scripts/refresh_winrate.py --vault "<KB>/wiki"

# 或分步：1) 回测 → outcomes.jsonl  2) 出榜（--window 10 看 T+10；--report 出 md）
python3 skills/opinion-cross/scripts/build_outcomes.py --vault "<KB>/wiki"
python3 skills/opinion-cross/scripts/winrate_rank.py --vault "<KB>/wiki" --report /tmp/winrate.md

# 出可视化 HTML（双击即开；默认 复盘/winrate/winrate-<date>.html）
python3 skills/opinion-cross/scripts/render_winrate_html.py --vault "<KB>/wiki"
```

**迭代机制**：胜率榜是从 `opinion-events.jsonl` 台账**重算**出的派生视图（非手改、无漂移）。补研报/晨汇 → 入库 append → 重跑 `refresh_winrate.py`。`build_outcomes.py` 日期默认动态（end=今天、start=最早观点日前7天），价格范围感知缓存只抓新交易日；每次重算两个叠加效应：①新观点进入回测；②此前窗口不足的近期观点随交易日推进自动补全。**晨汇看多默认不计入胜率**（`[晨汇转述]` 通道已剔除，只研报算）。

**口径纪律**（遵守 finance「市场假设验证」红线）：进场次日开盘、超额剥大盘 beta、3/5/7/10 多窗口 + 区间最高/峰值/回撤（不只看末日收盘）、样本门槛过滤噪音、窗口不足不计入该窗口分母。**outcomes.jsonl 是派生数据**，与 opinion-events.jsonl/sources.json 同放 KB `wiki/raw/theme-radar/opinion-store/`，不进代码仓。

