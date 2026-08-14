# UP 线更新

## 触发词：up线更新

计算 UP = MA26 + 0.764 × STD26（布林带变体，N=26, P=20），写入飞书自选股、强势股、大成交三张表。

```bash
python3 /Users/lbq/Desktop/c\ c/金融/skills/up-line/scripts/update.py
```

脚本会：
1. 读取三张飞书表（自选股全量，强势股/大成交取最新日期）
2. 批量查询 iFinD 获取 MA26 和 STD26
3. 计算 UP 值并写回三张表的 UP 字段
4. 输出对齐表格到终端

每日运行，覆盖更新。
