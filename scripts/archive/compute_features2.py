#!/usr/bin/env python3
"""兼容入口：计算大盘与连板窗口，写入 canonical DuckDB。"""
from scripts.compute_features import main


if __name__ == "__main__":
    raise SystemExit(main(default_selected=("market", "limit-advance")))
