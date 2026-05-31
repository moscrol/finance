---
name: up-line
description: UP线更新（布林带变体）。触发词：UP线更新、up线、UP线。
---

# UP 线更新

## 触发条件

用户说"UP线更新""up线""UP线"时触发。

计算 UP = MA26 + 0.764 × STD26（布林带变体，N=26, P=20）及偏离度 = (最新价/UP - 1) × 100%，写入飞书自选股、强势股、大成交三张表的 UP 和 偏离度 字段。

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/up-line/scripts/update.py
```

脚本会：
1. 读取三张飞书表（自选股全量，强势股/大成交取最新日期）
2. 批量查询 iFinD 获取 MA26 和 STD26
3. 计算 UP 值和偏离度，写回三张表的 UP/偏离度 字段
4. 写入后自动回读验证，检查 UP 和偏离度字段是否完整，有空字段会输出 ⚠ 警告
5. 输出对齐表格到终端

每日运行，覆盖更新。
