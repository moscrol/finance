"""每用户每日 run 配额（预占式）。

原则（MOC 已沉淀、真实事故验证过）：**配额要在副作用前「预占」，不是
事后计数**——事后扣费挡不住并发 check-then-act：两个请求同时看到
「还剩 1」会双双执行，最后才有一个扣账失败。实现上，读-判-写在同一把
进程内锁的临界区里完成，先占号、再创建 run；占号失败直接 429，不产生
任何副作用。

状态落盘在 ``users/<id>/run_quota.json``（随用户命名空间走，跨重启保
留当日计数）。写文件用 tmp + ``os.replace`` 原子替换，进程崩溃不会留
半截 JSON。

边界声明（结论携带成立条件）：本实现的互斥范围是**单进程**（当前部署
形态：launchd 单 uvicorn 进程 + 线程池 worker）。若将来 uvicorn 开多
进程 worker 或多实例部署，进程内锁失效，必须换共享存储（如 SQLite
``BEGIN IMMEDIATE`` 或 Redis INCR）——见 hosted-alpha runbook。
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from intelligence import userspace

ENV_DAILY_LIMIT = "WORKBENCH_DAILY_RUN_QUOTA"
ENV_EXEMPT_USERS = "WORKBENCH_QUOTA_EXEMPT_USERS"

_STATE_FILENAME = "run_quota.json"


@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    used: int
    limit: int


class RunQuota:
    """limit<=0 表示不限（默认，本机自用行为不变）。"""

    def __init__(self, daily_limit: int = 0, exempt_users: frozenset[str] = frozenset()) -> None:
        self.daily_limit = int(daily_limit)
        self.exempt_users = exempt_users
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RunQuota":
        env = os.environ if env is None else env
        raw_limit = (env.get(ENV_DAILY_LIMIT) or "").strip()
        try:
            limit = int(raw_limit) if raw_limit else 0
        except ValueError as exc:
            raise ValueError(
                f"{ENV_DAILY_LIMIT} 必须是整数，得到 {raw_limit!r}"
            ) from exc
        exempt = frozenset(
            item.strip()
            for item in (env.get(ENV_EXEMPT_USERS) or "").split(",")
            if item.strip()
        )
        return cls(daily_limit=limit, exempt_users=exempt)

    @property
    def enabled(self) -> bool:
        return self.daily_limit > 0

    def reserve(self, user_id: str) -> QuotaDecision:
        """占一个当日名额。返回 denied 时调用方必须放弃创建 run。"""
        if not self.enabled or user_id in self.exempt_users:
            return QuotaDecision(allowed=True, used=0, limit=self.daily_limit)
        today = date.today().isoformat()
        path = userspace.user_space(user_id).root / _STATE_FILENAME
        with self._lock:
            used = self._read_used(path, today)
            if used >= self.daily_limit:
                return QuotaDecision(allowed=False, used=used, limit=self.daily_limit)
            used += 1
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps({"date": today, "used": used}, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(tmp, path)
            return QuotaDecision(allowed=True, used=used, limit=self.daily_limit)

    @staticmethod
    def _read_used(path: Path, today: str) -> int:
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        if not isinstance(state, dict) or state.get("date") != today:
            return 0
        try:
            used = int(state.get("used", 0))
        except (TypeError, ValueError):
            return 0
        return max(used, 0)
