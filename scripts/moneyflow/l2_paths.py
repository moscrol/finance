"""L2 文件源的本机路径约定。不写家目录字面量。"""
from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    env = os.environ.get("FINANCE_DATA_ROOT") or os.environ.get("FINANCE_WS")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def cache_dir() -> Path:
    path = Path(os.environ.get("L2_CACHE_DIR") or (data_root() / "state" / "l2-cache"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def share_meta_path() -> Path:
    return Path(os.environ.get("L2_SHARE_META") or (data_root() / "state" / "l2-baidu-share.json"))


def cookie_db_path() -> Path:
    env = os.environ.get("BAIDU_NETDISK_COOKIE_DB")
    if env:
        return Path(env).expanduser()
    return (
        Path.home()
        / "Library/Containers/com.baidu.netdisk/Data"
        / "Library/Application Support/baidunetdisk/Cookies"
    )


def yyyymmdd(date: str) -> str:
    return date.replace("-", "")


def month_dir(date: str) -> str:
    compact = yyyymmdd(date)
    return compact[:6]


def archive_name(date: str) -> str:
    return f"{yyyymmdd(date)}.7z"


def inbox_path(meta: dict | None = None) -> str:
    if meta and meta.get("inbox_path"):
        return str(meta["inbox_path"])
    return os.environ.get("L2_INBOX_PATH") or "/L2-inbox"
