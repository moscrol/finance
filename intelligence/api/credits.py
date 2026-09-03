"""每用户额度账本：赠送额度 + 月度充值额度，按 run 次数计。

与 ``quota.RunQuota``（每日上限，防滥用的节流阀）是两件事：本模块是**钱包**——
用户能用多少次，由 owner 赠送和用户充值决定；日配额挡的是「一天内刷太多」。
两者同时生效时先占钱包再占日配额，任何一道拒绝都把已占的那一道退回。

账本形状（``users/<id>/credits.json``）：

- ``grants``：一条 grant = 一次授予（``gift`` 赠送 / ``monthly`` 月度充值），带
  ``amount`` / ``remaining`` / ``expires_at``（``None`` = 不过期）。
- ``ledger``：每次变动一行（grant / run / refund / revoke），append-only，用户对账用。

**消费顺序：先到期的先扣，不过期的（赠送）最后扣**——月度额度是买来在这个月用的，
用不完作废；赠送是 owner 给的缓冲，不该被月度额度挤掉。已过期 grant 的余量不计入
余额、不可用、也不删（账在）。

**首次接触自动赠送**：``WORKBENCH_CREDITS_SIGNUP_GIFT=N`` 时，某用户第一次占额度、
名下还没有账本文件，自动记一条 ``gift`` N 次。判据是「没有账本文件」而不是「余额为 0」，
所以用完不会再送。owner 手工 ``grant`` 走 ``scripts/workbench_credits.py``。

**锁**：进程内 ``threading.Lock`` + 账本旁的 ``credits.lock`` 文件 ``flock``。
后者是必需的：CLI（另一个进程）会与服务进程同写一份账本，只靠进程内锁会丢更新。
同机多进程因此是安全的；跨机器仍需共享存储（与 quota / 准入同一条边界声明）。

**坏账本 fail closed**：JSON 解析失败 → 拒绝扣额、不改写文件。钱的账本坏了不能当空账本
重建——那等于把余额清零再送一次赠送。

预占语义与 ``RunQuota`` 一致：读-判-写在同一临界区完成；占号失败直接 429、零副作用；
``release`` 只用于「预占成功、随后被我们自己拒收（准入满 / 日配额满）」的补偿。
"""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from intelligence import userspace
from intelligence.api.quota import ENV_EXEMPT_USERS

ENV_ENABLED = "WORKBENCH_CREDITS"
ENV_SIGNUP_GIFT = "WORKBENCH_CREDITS_SIGNUP_GIFT"

KIND_GIFT = "gift"
KIND_MONTHLY = "monthly"
KINDS = (KIND_GIFT, KIND_MONTHLY)

REASON_GRANT = "grant"
REASON_RUN = "run"
REASON_REFUND = "refund"
REASON_REVOKE = "revoke"

_STATE_FILENAME = "credits.json"
_LOCK_FILENAME = "credits.lock"
_SCHEMA_VERSION = 1
_LEDGER_CAP = 5000  # 每人每月两百次量级，几年也到不了；封顶只为账本文件不无限长


@dataclass(frozen=True)
class Grant:
    id: str
    kind: str
    amount: int
    remaining: int
    granted_at: str
    expires_at: str | None
    note: str = ""

    def expired(self, now: datetime) -> bool:
        if self.expires_at is None:
            return False
        return datetime.fromisoformat(self.expires_at) <= now

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CreditDecision:
    allowed: bool
    remaining: int
    reason: str  # ok | disabled | exempt | exhausted | corrupt
    grant_id: str | None = None


@dataclass(frozen=True)
class CreditBalance:
    user_id: str
    enabled: bool
    exempt: bool
    remaining: int | None  # None = 不计（关闭或豁免）
    grants: tuple[Grant, ...]
    next_expiry: str | None
    corrupt: bool = False

    def public_dict(self) -> dict[str, object]:
        return {
            "user": self.user_id,
            "enabled": self.enabled,
            "exempt": self.exempt,
            "remaining": self.remaining,
            "next_expiry": self.next_expiry,
            "corrupt": self.corrupt,
            "grants": [g.to_dict() for g in self.grants],
        }

    def summary_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "exempt": self.exempt,
            "remaining": self.remaining,
            "next_expiry": self.next_expiry,
        }


class CorruptLedger(Exception):
    """账本文件存在但解析不出来。调用方 fail closed。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("时间必须带时区（账本跨时区可读）")
    return moment.isoformat()


def _new_grant_id(now: datetime) -> str:
    return f"g-{now.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"


def _consumption_order(grant: Grant) -> tuple[int, str, str]:
    # 先到期先用；不过期的排最后；同一到期日按授予先后（FIFO）
    if grant.expires_at is None:
        return (1, "", grant.granted_at)
    return (0, grant.expires_at, grant.granted_at)


class CreditStore:
    def __init__(
        self,
        enabled: bool = False,
        signup_gift: int = 0,
        exempt_users: frozenset[str] = frozenset(),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.signup_gift = int(signup_gift)
        self.exempt_users = exempt_users
        self._clock = clock or _utcnow
        self._lock = threading.Lock()
        if self.signup_gift < 0:
            raise ValueError(f"{ENV_SIGNUP_GIFT} 不能为负")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CreditStore":
        env = os.environ if env is None else env
        raw_enabled = (env.get(ENV_ENABLED) or "").strip().lower()
        if raw_enabled in {"", "0", "off", "false", "no"}:
            enabled = False
        elif raw_enabled in {"1", "on", "true", "yes"}:
            enabled = True
        else:
            raise ValueError(f"{ENV_ENABLED} 只接受 0/1，得到 {raw_enabled!r}")
        raw_gift = (env.get(ENV_SIGNUP_GIFT) or "").strip()
        try:
            gift = int(raw_gift) if raw_gift else 0
        except ValueError as exc:
            raise ValueError(
                f"{ENV_SIGNUP_GIFT} 必须是整数，得到 {raw_gift!r}"
            ) from exc
        exempt = frozenset(
            item.strip()
            for item in (env.get(ENV_EXEMPT_USERS) or "").split(",")
            if item.strip()
        )
        return cls(enabled=enabled, signup_gift=gift, exempt_users=exempt)

    # ── 预占 / 退回 ────────────────────────────────────────────────────────

    def reserve(self, user_id: str) -> CreditDecision:
        """占 1 次额度。denied 时调用方必须放弃创建 run。"""
        if not self.enabled:
            return CreditDecision(allowed=True, remaining=0, reason="disabled")
        if user_id in self.exempt_users:
            return CreditDecision(allowed=True, remaining=0, reason="exempt")
        now = self._clock()
        with self._locked(user_id) as path:
            try:
                state = self._load_or_bootstrap(path, now)
            except CorruptLedger:
                return CreditDecision(allowed=False, remaining=0, reason="corrupt")
            grants = [Grant(**g) for g in state["grants"]]
            usable = sorted(
                (g for g in grants if g.remaining > 0 and not g.expired(now)),
                key=_consumption_order,
            )
            if not usable:
                return CreditDecision(allowed=False, remaining=0, reason="exhausted")
            chosen = usable[0]
            updated = replace(chosen, remaining=chosen.remaining - 1)
            state["grants"] = [
                (updated if g.id == chosen.id else g).to_dict() for g in grants
            ]
            self._append_ledger(
                state, now, delta=-1, grant_id=chosen.id, reason=REASON_RUN, actor="api"
            )
            self._write(path, state)
            remaining = sum(g.remaining for g in usable) - 1
            return CreditDecision(
                allowed=True, remaining=remaining, reason="ok", grant_id=chosen.id
            )

    def release(self, user_id: str) -> None:
        """退回最近一次 run 扣账。只用于预占后被我们自己拒收的补偿。"""
        if not self.enabled or user_id in self.exempt_users:
            return
        now = self._clock()
        with self._locked(user_id) as path:
            try:
                state = self._load(path)
            except (FileNotFoundError, CorruptLedger):
                return
            debit = next(
                (
                    row
                    for row in reversed(state["ledger"])
                    if row["reason"] == REASON_RUN and not row.get("refunded")
                ),
                None,
            )
            if debit is None:
                return
            grants = [Grant(**g) for g in state["grants"]]
            target = next((g for g in grants if g.id == debit["grant_id"]), None)
            if target is None or target.remaining >= target.amount:
                return
            debit["refunded"] = True
            state["grants"] = [
                (
                    replace(g, remaining=g.remaining + 1) if g.id == target.id else g
                ).to_dict()
                for g in grants
            ]
            self._append_ledger(
                state,
                now,
                delta=+1,
                grant_id=target.id,
                reason=REASON_REFUND,
                actor="api",
            )
            self._write(path, state)

    # ── 运营操作（CLI / 将来的支付回调）───────────────────────────────────

    def grant(
        self,
        user_id: str,
        kind: str,
        amount: int,
        *,
        expires_at: datetime | None = None,
        note: str = "",
        actor: str = "cli",
    ) -> Grant:
        """授予额度。不看 enabled——owner 可以在开钱包之前先把账铺好。"""
        if kind not in KINDS:
            raise ValueError(f"kind 只能是 {'/'.join(KINDS)}，得到 {kind!r}")
        if int(amount) <= 0:
            raise ValueError("amount 必须是正整数")
        expires = _isoformat(expires_at) if expires_at is not None else None
        now = self._clock()
        grant = Grant(
            id=_new_grant_id(now),
            kind=kind,
            amount=int(amount),
            remaining=int(amount),
            granted_at=_isoformat(now),
            expires_at=expires,
            note=str(note or ""),
        )
        with self._locked(user_id) as path:
            try:
                state = self._load(path)
            except FileNotFoundError:
                state = self._empty_state()
            # 坏账本上不能叠新账（CorruptLedger 直接抛给运营者看）
            state["grants"].append(grant.to_dict())
            self._append_ledger(
                state,
                now,
                delta=grant.amount,
                grant_id=grant.id,
                reason=REASON_GRANT,
                actor=actor,
                note=grant.note,
            )
            self._write(path, state)
        return grant

    def revoke(
        self, user_id: str, grant_id: str, *, note: str = "", actor: str = "cli"
    ) -> Grant:
        """把某条 grant 的余量清零（退款 / 发错了）。历史扣账不动。"""
        now = self._clock()
        with self._locked(user_id) as path:
            state = self._load(path)
            grants = [Grant(**g) for g in state["grants"]]
            target = next((g for g in grants if g.id == grant_id), None)
            if target is None:
                raise KeyError(grant_id)
            revoked = replace(target, remaining=0)
            state["grants"] = [
                (revoked if g.id == grant_id else g).to_dict() for g in grants
            ]
            self._append_ledger(
                state,
                now,
                delta=-target.remaining,
                grant_id=grant_id,
                reason=REASON_REVOKE,
                actor=actor,
                note=note,
            )
            self._write(path, state)
        return revoked

    def balance(self, user_id: str) -> CreditBalance:
        exempt = user_id in self.exempt_users
        if not self.enabled or exempt:
            return CreditBalance(
                user_id=user_id,
                enabled=self.enabled,
                exempt=exempt,
                remaining=None,
                grants=(),
                next_expiry=None,
            )
        now = self._clock()
        with self._locked(user_id) as path:
            try:
                state = self._load(path)
            except FileNotFoundError:
                state = self._empty_state()
            except CorruptLedger:
                return CreditBalance(
                    user_id=user_id,
                    enabled=True,
                    exempt=False,
                    remaining=0,
                    grants=(),
                    next_expiry=None,
                    corrupt=True,
                )
        grants = tuple(Grant(**g) for g in state["grants"])
        live = sorted(
            (g for g in grants if g.remaining > 0 and not g.expired(now)),
            key=_consumption_order,
        )
        expiring = [g.expires_at for g in live if g.expires_at is not None]
        return CreditBalance(
            user_id=user_id,
            enabled=True,
            exempt=False,
            remaining=sum(g.remaining for g in live),
            grants=tuple(live) + tuple(g for g in grants if g not in live),
            next_expiry=min(expiring) if expiring else None,
        )

    def history(self, user_id: str, *, limit: int = 50) -> list[dict[str, object]]:
        with self._locked(user_id) as path:
            try:
                state = self._load(path)
            except FileNotFoundError:
                return []
        rows = list(state["ledger"])
        return rows[-limit:] if limit > 0 else rows

    def list_users(self) -> list[CreditBalance]:
        """有账本文件的全部用户（运营总览）。"""
        root = userspace.users_dir()
        if not root.is_dir():
            return []
        out: list[CreditBalance] = []
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / _STATE_FILENAME).is_file():
                out.append(self.balance(child.name))
        return out

    # ── 落盘 ───────────────────────────────────────────────────────────────

    @contextmanager
    def _locked(self, user_id: str) -> Iterator[Path]:
        root = userspace.user_space(user_id).root
        root.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with open(root / _LOCK_FILENAME, "a+b") as lock_fd:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
                try:
                    yield root / _STATE_FILENAME
                finally:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _empty_state() -> dict[str, object]:
        return {"version": _SCHEMA_VERSION, "grants": [], "ledger": []}

    @staticmethod
    def _load(path: Path) -> dict[str, object]:
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise
        try:
            state = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CorruptLedger(str(path)) from exc
        if (
            not isinstance(state, dict)
            or not isinstance(state.get("grants"), list)
            or not isinstance(state.get("ledger"), list)
        ):
            raise CorruptLedger(str(path))
        return state

    def _load_or_bootstrap(self, path: Path, now: datetime) -> dict[str, object]:
        try:
            return self._load(path)
        except FileNotFoundError:
            state = self._empty_state()
            if self.signup_gift > 0:
                gift = Grant(
                    id=_new_grant_id(now),
                    kind=KIND_GIFT,
                    amount=self.signup_gift,
                    remaining=self.signup_gift,
                    granted_at=_isoformat(now),
                    expires_at=None,
                    note="首次使用自动赠送",
                )
                state["grants"].append(gift.to_dict())
                self._append_ledger(
                    state,
                    now,
                    delta=gift.amount,
                    grant_id=gift.id,
                    reason=REASON_GRANT,
                    actor="signup",
                    note=gift.note,
                )
            return state

    @staticmethod
    def _append_ledger(
        state: dict[str, object],
        now: datetime,
        *,
        delta: int,
        grant_id: str,
        reason: str,
        actor: str,
        note: str = "",
    ) -> None:
        row: dict[str, object] = {
            "at": _isoformat(now),
            "delta": int(delta),
            "grant_id": grant_id,
            "reason": reason,
            "actor": actor,
        }
        if note:
            row["note"] = note
        ledger = state["ledger"]
        assert isinstance(ledger, list)
        ledger.append(row)
        if len(ledger) > _LEDGER_CAP:
            del ledger[: len(ledger) - _LEDGER_CAP]

    @staticmethod
    def _write(path: Path, state: dict[str, object]) -> None:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        os.replace(tmp, path)
