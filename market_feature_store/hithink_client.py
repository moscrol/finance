"""同花顺金融数据服务 REST 客户端。

契约对照：HiThink-Tech/Financial-API ``docs/api/``（2026-09-08 实测，见
``docs/data-sources/hithink-finance-api-assessment-2026-09-08.md`` §2.5）。

Key 只从环境变量 ``HITHINK_FINANCE_API_KEY`` 或 macOS 钥匙串
（service=``hithink-finance`` / account=``a77-api-key``）读取，不进日志、
不进异常消息、不进仓库。默认 5 QPS（0.2 s）；超限 ``code=4001`` 退避。
预签名下载链接只对 GET 有效，HEAD 会 403，有效期约五分钟。
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

BASE_URL = "https://fuyao.aicubes.cn"
DEFAULT_GAP_SECONDS = 0.2
KEYCHAIN_SERVICE = "hithink-finance"
KEYCHAIN_ACCOUNT = "a77-api-key"
ENV_KEY_NAME = "HITHINK_FINANCE_API_KEY"
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_last_request_monotonic = 0.0


class HithinkAPIError(RuntimeError):
    """上游返回非 0 业务码或 HTTP 失败。消息里不得带 key / 预签名 query。"""


def has_api_key() -> bool:
    """只回答有没有 key，不回值。daily-full 缺 key 时靠这个 skip，不让整条链失败。"""

    try:
        load_api_key()
    except HithinkAPIError:
        return False
    return True


def load_api_key() -> str:
    """环境变量优先，否则读钥匙串。都没有就 fail closed。"""

    env_key = (os.environ.get(ENV_KEY_NAME) or "").strip()
    if env_key:
        return env_key
    try:
        proc = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                KEYCHAIN_ACCOUNT,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise HithinkAPIError("读不到钥匙串，也没有 HITHINK_FINANCE_API_KEY") from exc
    key = (proc.stdout or "").strip()
    if proc.returncode != 0 or not key:
        raise HithinkAPIError(
            "没有 HITHINK_FINANCE_API_KEY，钥匙串 hithink-finance/a77-api-key 也是空的"
        )
    return key


def shanghai_midnight_ms(day: date) -> int:
    """Asia/Shanghai 当日零点的 Unix 毫秒。"""

    dt = datetime(day.year, day.month, day.day, tzinfo=_SHANGHAI)
    return int(dt.timestamp() * 1000)


def ms_to_shanghai_date(date_ms: int) -> date:
    """把上游毫秒戳（上海零点）转回日期。"""

    return datetime.fromtimestamp(date_ms / 1000.0, tz=_SHANGHAI).date()


def _throttle(gap_seconds: float) -> None:
    global _last_request_monotonic
    wait = gap_seconds - (time.monotonic() - _last_request_monotonic)
    if wait > 0:
        time.sleep(wait)


def _mark_request() -> None:
    global _last_request_monotonic
    _last_request_monotonic = time.monotonic()


def _safe_netloc(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc or "unknown-host"
    except ValueError:
        return "unknown-host"


def get_json(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    gap_seconds: float = DEFAULT_GAP_SECONDS,
    timeout: float = 60.0,
    retries: int = 4,
) -> dict[str, Any]:
    """GET JSON。``path`` 以 ``/api/`` 开头。返回整段 JSON（含 code/data）。"""

    key = load_api_key()
    query = urllib.parse.urlencode(
        {k: v for k, v in (params or {}).items() if v is not None}
    )
    url = BASE_URL + path + (("?" + query) if query else "")
    last_err: Exception | None = None
    for attempt in range(retries):
        _throttle(gap_seconds)
        req = urllib.request.Request(
            url,
            headers={
                "X-api-key": key,
                "User-Agent": "finance-workspace-hithink/0.1",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
            last_err = exc
        except urllib.error.URLError as exc:
            _mark_request()
            last_err = exc
            time.sleep(min(8.0, 0.5 * (2**attempt)))
            continue
        _mark_request()
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise HithinkAPIError(
                f"非 JSON 响应 http={status} path={path}"
            ) from exc
        code = payload.get("code")
        if code == 0:
            return payload
        if code == 4001 and attempt + 1 < retries:
            time.sleep(min(8.0, 0.8 * (2**attempt)))
            continue
        raise HithinkAPIError(
            f"hithink {path} http={status} code={code} {payload.get('message')}"
        )
    raise HithinkAPIError(f"hithink {path} 重试耗尽") from last_err


def download_presigned(
    url: str,
    dest: Path,
    *,
    timeout: float = 180.0,
) -> Path:
    """GET 预签名对象到 dest。不打 URL（query 里有签名）。"""

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except urllib.error.HTTPError as exc:
        raise HithinkAPIError(
            f"预签名下载失败 http={exc.code} host={_safe_netloc(url)}"
        ) from exc
    tmp.replace(dest)
    return dest


def fetch_dump_parquet(kind: str, dest: Path) -> Path:
    """签出并下载 market-dumps 的一种：daily-k / daily-k-10d / adjustment-factors。"""

    if kind not in {"daily-k", "daily-k-10d", "adjustment-factors"}:
        raise ValueError(f"未知 dump kind: {kind}")
    payload = get_json(f"/api/dump/market-dumps/{kind}/download-url")
    data = payload.get("data") or {}
    url = data.get("presigned_url")
    if not url:
        raise HithinkAPIError(f"dump {kind} 没有 presigned_url")
    return download_presigned(url, dest)
