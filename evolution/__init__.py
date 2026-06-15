"""策略进化流水线（无前视、可验证、可回溯、可迭代）。

模块：
- strategy1: 策略一确定性生成器（仅用 D0 当日数据）
- validate : 前瞻收益验证（基准 = D0 收盘，T+h 收盘涨幅）

入口 CLI 见 scripts/evolve.py。
"""
