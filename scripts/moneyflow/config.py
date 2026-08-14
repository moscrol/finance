#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moneyflow 模块公共配置。

- ClickHouse 连接凭证一律走环境变量，不硬编码（守 AGENTS.md 红线）：
    CH_HOST / CH_PORT / CH_USER / CH_PASSWORD
- 图表/CSV 产物统一落到 outputs/（已在 .gitignore 忽略，不入库）。
"""
import os
from pathlib import Path

HOST = os.environ.get("CH_HOST", "db.base32.cn")
PORT = int(os.environ.get("CH_PORT", "9000"))
USER = os.environ.get("CH_USER", "hisdata180")
PASSWORD = os.environ.get("CH_PASSWORD", "")

OUTPUT_DIR = Path(os.environ.get(
    "MONEYFLOW_OUTPUT_DIR", Path(__file__).resolve().parent / "outputs"))


def out_path(name: str) -> str:
    """产物路径（自动建目录）。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return str(OUTPUT_DIR / name)


def to_ts_code(code: str) -> str:
    """裸代码转带交易所后缀的 ts_code，便于与其它特征表 join。
    6/9 开头为上交所(.XSHG)，其余为深交所(.XSHE)。"""
    return f"{code}.XSHG" if code[0] in ("6", "9") else f"{code}.XSHE"


_ENV_DB = os.environ.get("MARKET_FEATURE_STORE_DB")
DUCKDB_PATH = str(Path(_ENV_DB).expanduser()) if _ENV_DB else str(
    Path(__file__).resolve().parents[2] / "db" / "market_feature_store.duckdb")
