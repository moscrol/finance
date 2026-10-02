---
name: up-line
metadata:
  pattern: tool-wrapper
  superseded_by: stock-technicals
description: 已被 stock-technicals 取代，不要调用。原用途是 UP线更新与个股UP/偏离度查询（布林带变体），清单依赖已退役的飞书表、行情依赖 iFinD，2026-09-11 起跑不通；同一公式现由 stock-technicals 在本地 DuckDB 计算。目录按 PR 729 的用户决定保留作公式参考。
---

> **➜ 请直接用 [`stock-technicals`](../stock-technicals/SKILL.md)**：同一 UP 公式，DuckDB 本地批量计算，UP/偏离度是默认输出列，支持 `--as-of` 回溯历史某天。
> 本 skill 已于 2026-09-30 撤出 `.claude/skills/` 视图，不再参与触发匹配；`tests/test_skill_view_supersession.py` 锁住「被取代的不暴露、取代者必须暴露」。

> **⚠ 2026-09-11 飞书整体退役（#727）后的实际可用性**：本 skill 的 UP 计算口径（UP = MA26 + 0.764×STD26，偏离度 =（最新价/UP − 1）×100%）是它的价值所在，已按用户要求保留（#729）。
> 但它的**股票清单来自飞书自选股/强势股/大成交三张表**（`fetch_all_records`），行情走 iFinD——飞书凭证退役、本机亦无 iFinD token，故**当前跑不通**。
> 「把清单换成 DuckDB 侧来源、行情换 `market_feature_store` 日线、公式不动」这条复活路径**已经由 `stock-technicals` 做完**，不要在这里再实现一遍。

# UP 线更新

## 触发条件

用户说"UP线更新""up线""UP线"时触发更新；用户说"查UP""个股UP""UP偏离度""偏离UP"或询问某只股票 UP/偏离度时触发查询。

计算 UP = MA26 + 0.764 × STD26（布林带变体，N=26, P=20）及偏离度 = (最新价/UP - 1) × 100%，写入飞书自选股、强势股、大成交三张表的 UP 和 偏离度 字段。

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/up-line/scripts/update.py
```

查询单只或多只个股 UP/偏离度（只读，不写回飞书）：

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/up-line/scripts/update.py query 亨通光电 中际旭创
```

脚本会：
1. 读取三张飞书表（自选股全量，强势股/大成交取最新日期）
2. 批量查询 iFinD 获取 MA26 和 STD26
3. 计算 UP 值和偏离度，写回三张表的 UP/偏离度 字段
4. 写入后自动回读验证，检查 UP 和偏离度字段是否完整，有空字段会输出 ⚠ 警告
5. 输出对齐表格到终端

每日运行，覆盖更新。

查询模式会：
1. 优先在自选股、强势股、大成交三张飞书表中匹配股票简称/代码
2. 未匹配时按输入名称直接实时查询
3. 优先用本地 `market_feature_store.fact_stock_daily` 最近26个交易日收盘价计算 MA26、STD26、UP 和偏离度
4. 本地缺数据时再批量查询 iFinD 的 MA26、STD26 和今日收盘价
5. 输出最新价、MA26、STD26、UP、偏离度、站上/低于 UP 状态
6. 不创建字段、不更新飞书
