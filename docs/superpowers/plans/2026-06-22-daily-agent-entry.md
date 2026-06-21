# Daily Agent Entry Plan

## 步骤

1. 增加 `tests/test_daily_agent.py`，用临时 finance/wiki fixture 验证日报聚合行为。
2. 增加 `intelligence/workflows/daily_agent.py`：
   - 构建 daily ledger。
   - 调用 logic-match-batch。
   - 生成四类决策桶。
   - 渲染 Markdown。
3. 在 `intelligence/cli.py` 增加 `agent-daily` 命令。
4. 在 `intelligence/routing/path_registry.json` 注册 `agent_daily` 路径。
5. 用真实 `2026-06-11` 数据跑通，生成 md/json。
6. 跑目标测试、编译检查和全量 tests。

## 验收

- `python3 -m unittest tests.test_daily_agent tests.test_logic_market_match` 通过。
- `python3 -m py_compile intelligence/workflows/daily_agent.py intelligence/cli.py` 通过。
- `python3 -m unittest discover -s tests` 通过。
- `python3 -m intelligence.cli agent-daily --date 2026-06-11 ...` 能输出日报。
