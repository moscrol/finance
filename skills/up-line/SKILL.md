---
name: up-line
description: UP线更新与个股UP/偏离度查询（布林带变体）。触发词：UP线更新、up线、UP线、查UP、个股UP、UP偏离度、偏离UP。
---

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
