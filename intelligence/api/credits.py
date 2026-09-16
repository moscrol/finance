"""每用户积分账本：赠送积分 + 月度充值积分，按 run 的**真实用量**结算。

单位是**积分**，100 积分 = 1 元（用户定：20 元 = 2000 积分）。与 ``quota.RunQuota``
（每日次数上限，防滥用的节流阀）是两件事：本模块是**钱包**。两者同时生效时先占钱包
再占日配额，任何一道拒绝都把已占的那一道退回。

一次 run 花多少积分（``CreditPricing.cost``）::

    cost_yuan = base_fee
              + markup × Σ_model (input_tokens × input_rate + output_tokens × output_rate) / 1_000_000
              + tool_calls × tool_call_fee
    points    = max(ceil(cost_yuan × 100), min_charge_points)

  - 费率按模型查价目表（``models``），查不到用 ``default`` 档；单位是**元 / 百万 token**，
    与供应商报价同一口径，markup 单列（成本与利润分开看）。
  - run 未产生任何模型用量且**没有完成**（排队中被取消、开跑即挂）：0 积分，预占全退。
  - run 完成但没有模型用量（确定性罐头答案）：只收 base_fee。
  - 价目表从 ``WORKBENCH_CREDITS_PRICING`` 指向的 JSON 读，不设用内置默认——**默认值是占位**，
    上线前按真实供应商报价改。

预占 → 结算（``reserve`` → ``bind_hold`` → ``settle``）::

  - 提问受理时**预占** ``hold_points``（不动 grant，只从可用余额里扣一块），拿到 ``hold_id``；
    run 建好后 ``bind_hold`` 把它绑到 run_id。准入拒收 / 日配额拒绝 / 落盘失败 → ``release_hold``。
  - run 终态（worker 返回）时 ``settle``：按用量算积分，从**先到期的 grant 开始**逐笔扣；
    可用不够就记 **欠账（debt）**——用户已经拿到服务，账要记实；欠账为正时新提问一律拒绝，
    下一笔 grant 先抵欠账。
  - 准入判据：``available = Σ 未过期 grant 余量 − Σ 在途预占 − 欠账 > 0``。余额 3 积分也能再问
    一次（最后一次可能透支成欠账），而不是「还剩 3 分为什么不让我用」。
  - 预占有 TTL（6 小时）：进程崩在 reserve 与 bind 之间留下的孤儿预占不会永远占着余额。

其余纪律与首版一致：``users/<id>/credits.json`` + 旁边 ``credits.lock`` **flock**（CLI 与服务
进程同写一份账本，进程内锁护不住，变异实测）；**坏账本 fail closed**（不改写、拒绝扣额）；
首次接触自动赠送 ``WORKBENCH_CREDITS_SIGNUP_GIFT`` 积分（判据 = 还没有账本文件）；过期 grant
余量不计不删；每笔变动进 append-only ``ledger``（grant / run / revoke / debt_repaid），
run 那一行带用量与算式，用户对账用。
"""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from intelligence import userspace
from intelligence.api.quota import ENV_EXEMPT_USERS

ENV_ENABLED = "WORKBENCH_CREDITS"
ENV_SIGNUP_GIFT = "WORKBENCH_CREDITS_SIGNUP_GIFT"
ENV_PRICING = "WORKBENCH_CREDITS_PRICING"

POINTS_PER_YUAN = 100

KIND_GIFT = "gift"
KIND_MONTHLY = "monthly"
KINDS = (KIND_GIFT, KIND_MONTHLY)

REASON_GRANT = "grant"
REASON_RUN = "run"
REASON_REVOKE = "revoke"
REASON_DEBT_REPAID = "debt_repaid"

_STATE_FILENAME = "credits.json"
_LOCK_FILENAME = "credits.lock"
_EPISODE_FILENAME = "continuous-episode.json"
_SCHEMA_VERSION = 2
_LEDGER_CAP = 5000
_HOLD_TTL = timedelta(hours=6)


# ── 定价 ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ModelRate:
    input_yuan_per_1m: Decimal
    output_yuan_per_1m: Decimal


# 占位价目：按 GLM 系列公开报价量级取整，markup 2 倍。上线前改 WORKBENCH_CREDITS_PRICING。
_DEFAULT_PRICING: dict[str, object] = {
    "markup": "2.0",
    "base_fee_yuan": "0.10",
    "min_charge_yuan": "0.05",
    "hold_yuan": "1.00",
    "tool_call_fee_yuan": "0",
    "models": {
        "default": {"input_yuan_per_1m": "3.0", "output_yuan_per_1m": "12.0"},
        "glm-5.3": {"input_yuan_per_1m": "3.0", "output_yuan_per_1m": "12.0"},
    },
}


def _dec(value: object, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:  # noqa: BLE001 - 统一成 ValueError 给启动期
        raise ValueError(f"价目表 {name} 不是数字：{value!r}") from exc
    if result < 0:
        raise ValueError(f"价目表 {name} 不能为负：{value!r}")
    return result


@dataclass(frozen=True)
class CostBreakdown:
    points: int
    cost_yuan: str
    base_fee_yuan: str
    token_yuan: str
    tool_yuan: str
    markup: str
    rule: str  # metered | base_only | free
    by_model: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        # 账本里的算式行是对外协议（用户对账、CLI 展示），逐字段写死键名，不跟 dataclass 字段名漂。
        return {
            "points": self.points,
            "cost_yuan": self.cost_yuan,
            "base_fee_yuan": self.base_fee_yuan,
            "token_yuan": self.token_yuan,
            "tool_yuan": self.tool_yuan,
            "markup": self.markup,
            "rule": self.rule,
            "by_model": dict(self.by_model),
        }


@dataclass(frozen=True)
class CreditPricing:
    markup: Decimal
    base_fee_yuan: Decimal
    min_charge_yuan: Decimal
    hold_yuan: Decimal
    tool_call_fee_yuan: Decimal
    models: Mapping[str, ModelRate]
    source: str = "builtin-default"

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object], *, source: str) -> "CreditPricing":
        models_raw = raw.get("models")
        if not isinstance(models_raw, Mapping) or "default" not in models_raw:
            raise ValueError("价目表 models 必须含 default 档")
        models: dict[str, ModelRate] = {}
        for name, rate in models_raw.items():
            if not isinstance(rate, Mapping):
                raise ValueError(f"价目表 models.{name} 必须是对象")
            models[str(name)] = ModelRate(
                input_yuan_per_1m=_dec(
                    rate.get("input_yuan_per_1m"), f"models.{name}.input_yuan_per_1m"
                ),
                output_yuan_per_1m=_dec(
                    rate.get("output_yuan_per_1m"), f"models.{name}.output_yuan_per_1m"
                ),
            )
        return cls(
            markup=_dec(raw.get("markup", "1"), "markup"),
            base_fee_yuan=_dec(raw.get("base_fee_yuan", "0"), "base_fee_yuan"),
            min_charge_yuan=_dec(raw.get("min_charge_yuan", "0"), "min_charge_yuan"),
            hold_yuan=_dec(raw.get("hold_yuan", "1"), "hold_yuan"),
            tool_call_fee_yuan=_dec(
                raw.get("tool_call_fee_yuan", "0"), "tool_call_fee_yuan"
            ),
            models=models,
            source=source,
        )

    @classmethod
    def default(cls) -> "CreditPricing":
        return cls.from_mapping(_DEFAULT_PRICING, source="builtin-default")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CreditPricing":
        env = os.environ if env is None else env
        raw_path = (env.get(ENV_PRICING) or "").strip()
        if not raw_path:
            return cls.default()
        path = Path(raw_path).expanduser()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"{ENV_PRICING}={path} 读不出来：{exc}") from exc
        if not isinstance(raw, Mapping):
            raise ValueError(f"{ENV_PRICING}={path} 必须是 JSON 对象")
        return cls.from_mapping(raw, source=str(path))

    @property
    def hold_points(self) -> int:
        return _yuan_to_points(self.hold_yuan)

    @property
    def min_charge_points(self) -> int:
        return _yuan_to_points(self.min_charge_yuan)

    def rate_for(self, model: str | None) -> ModelRate:
        key = (model or "").strip()
        return self.models.get(key) or self.models["default"]

    def cost(self, usage: "RunUsage | None", *, completed: bool) -> CostBreakdown:
        if usage is None or not usage.has_model_usage:
            if not completed:
                return CostBreakdown(
                    points=0,
                    cost_yuan="0",
                    base_fee_yuan="0",
                    token_yuan="0",
                    tool_yuan="0",
                    markup=str(self.markup),
                    rule="free",
                )
            base_points = max(
                _yuan_to_points(self.base_fee_yuan), self.min_charge_points
            )
            return CostBreakdown(
                points=base_points,
                cost_yuan=str(self.base_fee_yuan),
                base_fee_yuan=str(self.base_fee_yuan),
                token_yuan="0",
                tool_yuan="0",
                markup=str(self.markup),
                rule="base_only",
            )
        token_yuan = Decimal(0)
        by_model: dict[str, dict[str, int]] = {}
        for model, (inp, out) in usage.tokens_by_model.items():
            rate = self.rate_for(model)
            token_yuan += (
                Decimal(inp) * rate.input_yuan_per_1m
                + Decimal(out) * rate.output_yuan_per_1m
            ) / Decimal(1_000_000)
            by_model[model or "default"] = {"input_tokens": inp, "output_tokens": out}
        token_yuan *= self.markup
        tool_yuan = Decimal(usage.tool_calls) * self.tool_call_fee_yuan
        cost_yuan = self.base_fee_yuan + token_yuan + tool_yuan
        points = max(_yuan_to_points(cost_yuan), self.min_charge_points)
        return CostBreakdown(
            points=points,
            cost_yuan=str(cost_yuan),
            base_fee_yuan=str(self.base_fee_yuan),
            token_yuan=str(token_yuan),
            tool_yuan=str(tool_yuan),
            markup=str(self.markup),
            rule="metered",
            by_model=by_model,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "points_per_yuan": POINTS_PER_YUAN,
            "markup": str(self.markup),
            "base_fee_yuan": str(self.base_fee_yuan),
            "min_charge_yuan": str(self.min_charge_yuan),
            "hold_yuan": str(self.hold_yuan),
            "tool_call_fee_yuan": str(self.tool_call_fee_yuan),
            "models": {
                name: {
                    "input_yuan_per_1m": str(rate.input_yuan_per_1m),
                    "output_yuan_per_1m": str(rate.output_yuan_per_1m),
                }
                for name, rate in self.models.items()
            },
        }


def _yuan_to_points(yuan: Decimal) -> int:
    return int((yuan * POINTS_PER_YUAN).to_integral_value(rounding=ROUND_CEILING))


# ── 用量 ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunUsage:
    """一次 run 的可计费用量。``tokens_by_model``：模型名 → (input, output)。"""

    tokens_by_model: Mapping[str, tuple[int, int]]
    llm_calls: int = 0
    tool_calls: int = 0

    @property
    def input_tokens(self) -> int:
        return sum(inp for inp, _ in self.tokens_by_model.values())

    @property
    def output_tokens(self) -> int:
        return sum(out for _, out in self.tokens_by_model.values())

    @property
    def has_model_usage(self) -> bool:
        return self.input_tokens > 0 or self.output_tokens > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "by_model": {
                model or "default": {"input_tokens": inp, "output_tokens": out}
                for model, (inp, out) in self.tokens_by_model.items()
            },
        }


def _int_or_zero(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def read_run_usage(run_dir: Path) -> RunUsage | None:
    """从 run 目录读用量。没有 episode 文件（legacy 路径 / 罐头答案）或读不出来 → None。

    逐条 ``model_turn`` / ``branch_completed`` 事件按 ``served_model`` 归模型；事件里没有
    token 的回退到 ``outcome.usage`` 总量（归 default 档）。不编造：两处都没有就是 None。
    """
    path = run_dir / _EPISODE_FILENAME
    try:
        episode = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(episode, dict):
        return None
    by_model: dict[str, list[int]] = {}
    for event in episode.get("events") or []:
        if not isinstance(event, dict) or event.get("kind") not in {
            "model_turn",
            "branch_completed",
        }:
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        inp = _int_or_zero(payload.get("input_tokens"))
        out = _int_or_zero(payload.get("output_tokens"))
        if inp == 0 and out == 0:
            continue
        model = str(payload.get("served_model") or payload.get("model") or "").strip()
        slot = by_model.setdefault(model, [0, 0])
        slot[0] += inp
        slot[1] += out
    outcome = episode.get("outcome") or {}
    usage = outcome.get("usage") if isinstance(outcome, dict) else None
    usage = usage if isinstance(usage, dict) else {}
    llm_calls = _int_or_zero(usage.get("llm_calls"))
    tool_calls = _int_or_zero(usage.get("tool_calls"))
    if not by_model:
        total_in = _int_or_zero(usage.get("input_tokens"))
        total_out = _int_or_zero(usage.get("output_tokens"))
        if total_in == 0 and total_out == 0:
            if llm_calls == 0 and tool_calls == 0:
                return None
            return RunUsage(
                tokens_by_model={}, llm_calls=llm_calls, tool_calls=tool_calls
            )
        by_model[""] = [total_in, total_out]
    return RunUsage(
        tokens_by_model={m: (v[0], v[1]) for m, v in by_model.items()},
        llm_calls=llm_calls,
        tool_calls=tool_calls,
    )


# ── 账本 ─────────────────────────────────────────────────────────────────────


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
    available: int
    reason: str  # ok | disabled | exempt | exhausted | corrupt
    hold_id: str | None = None
    hold_points: int = 0


@dataclass(frozen=True)
class Settlement:
    charged: int
    available_after: int
    debt_after: int
    breakdown: CostBreakdown | None
    hold_released: int


@dataclass(frozen=True)
class CreditBalance:
    user_id: str
    enabled: bool
    exempt: bool
    remaining: int | None  # 可用积分 = 未过期余量 − 在途预占 − 欠账；关闭/豁免为 None
    grants: tuple[Grant, ...]
    next_expiry: str | None
    holds: int = 0
    debt: int = 0
    corrupt: bool = False

    def public_dict(self) -> dict[str, object]:
        return {
            "user": self.user_id,
            "enabled": self.enabled,
            "exempt": self.exempt,
            "remaining": self.remaining,
            "points_per_yuan": POINTS_PER_YUAN,
            "holds": self.holds,
            "debt": self.debt,
            "next_expiry": self.next_expiry,
            "corrupt": self.corrupt,
            "grants": [g.to_dict() for g in self.grants],
        }

    def summary_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "exempt": self.exempt,
            "remaining": self.remaining,
            "points_per_yuan": POINTS_PER_YUAN,
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


def _new_id(prefix: str, now: datetime) -> str:
    return f"{prefix}-{now.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"


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
        pricing: CreditPricing | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.signup_gift = int(signup_gift)
        self.exempt_users = exempt_users
        self.pricing = pricing or CreditPricing.default()
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
        return cls(
            enabled=enabled,
            signup_gift=gift,
            exempt_users=exempt,
            pricing=CreditPricing.from_env(env),
        )

    # ── 预占 / 绑定 / 释放 ─────────────────────────────────────────────────

    def reserve(self, user_id: str) -> CreditDecision:
        """提问受理前预占 ``hold_points``。denied 时调用方必须放弃创建 run。"""
        if not self.enabled:
            return CreditDecision(allowed=True, available=0, reason="disabled")
        if user_id in self.exempt_users:
            return CreditDecision(allowed=True, available=0, reason="exempt")
        now = self._clock()
        with self._locked(user_id) as path:
            try:
                state = self._load_or_bootstrap(path, now)
            except CorruptLedger:
                return CreditDecision(allowed=False, available=0, reason="corrupt")
            self._prune_holds(state, now)
            available = self._available(state, now)
            if available <= 0:
                self._write(path, state)
                return CreditDecision(
                    allowed=False, available=available, reason="exhausted"
                )
            hold_id = _new_id("h", now)
            hold_points = self.pricing.hold_points
            state["holds"][hold_id] = {
                "points": hold_points,
                "at": _isoformat(now),
                "run_id": None,
            }
            self._write(path, state)
            return CreditDecision(
                allowed=True,
                available=available - hold_points,
                reason="ok",
                hold_id=hold_id,
                hold_points=hold_points,
            )

    def bind_hold(self, user_id: str, hold_id: str | None, run_id: str) -> None:
        """run 建好后把预占绑到 run_id，结算时按 run_id 找。"""
        if not self._metered(user_id) or not hold_id:
            return
        with self._locked(user_id) as path:
            try:
                state = self._load(path)
            except (FileNotFoundError, CorruptLedger):
                return
            hold = state["holds"].get(hold_id)
            if hold is None:
                return
            hold["run_id"] = run_id
            self._write(path, state)

    def release_hold(
        self, user_id: str, *, hold_id: str | None = None, run_id: str | None = None
    ) -> int:
        """预占成功但 run 被我们自己拒收 / 没跑起来：释放预占，不记任何扣账。返回释放的积分。"""
        if not self._metered(user_id) or (hold_id is None and run_id is None):
            return 0
        with self._locked(user_id) as path:
            try:
                state = self._load(path)
            except (FileNotFoundError, CorruptLedger):
                return 0
            released = self._pop_hold(state, hold_id=hold_id, run_id=run_id)
            if released:
                self._write(path, state)
            return released

    # ── 结算 ───────────────────────────────────────────────────────────────

    def settle(
        self,
        user_id: str,
        run_id: str,
        usage: RunUsage | None,
        *,
        completed: bool,
        hold_id: str | None = None,
    ) -> Settlement | None:
        """run 终态：按用量算积分并扣账。可用不够记欠账（用户已拿到服务）。

        关闭 / 豁免返回 None。找不到预占也照扣——账按实际发生记，不依赖预占是否还在。
        """
        if not self._metered(user_id):
            return None
        breakdown = self.pricing.cost(usage, completed=completed)
        now = self._clock()
        with self._locked(user_id) as path:
            try:
                state = self._load_or_bootstrap(path, now)
            except CorruptLedger:
                return None
            released = self._pop_hold(state, hold_id=hold_id, run_id=run_id)
            grants = [Grant(**g) for g in state["grants"]]
            usable = sorted(
                (g for g in grants if g.remaining > 0 and not g.expired(now)),
                key=_consumption_order,
            )
            due = breakdown.points
            allocations: list[dict[str, object]] = []
            for grant in usable:
                if due <= 0:
                    break
                take = min(grant.remaining, due)
                allocations.append({"grant_id": grant.id, "points": take})
                grants = [
                    (
                        replace(g, remaining=g.remaining - take)
                        if g.id == grant.id
                        else g
                    )
                    for g in grants
                ]
                due -= take
            if due > 0:
                state["debt"] = int(state.get("debt", 0)) + due
            state["grants"] = [g.to_dict() for g in grants]
            if breakdown.points > 0 or usage is not None:
                self._append_ledger(
                    state,
                    now,
                    delta=-breakdown.points,
                    reason=REASON_RUN,
                    actor="api",
                    extra={
                        "run_id": run_id,
                        "completed": completed,
                        "allocations": allocations,
                        "debt_added": due,
                        "usage": usage.to_dict() if usage is not None else None,
                        "cost": breakdown.to_dict(),
                    },
                )
            self._write(path, state)
            return Settlement(
                charged=breakdown.points,
                available_after=self._available(state, now),
                debt_after=int(state.get("debt", 0)),
                breakdown=breakdown,
                hold_released=released,
            )

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
        """授予积分。不看 enabled——owner 可以在开钱包之前先把账铺好。有欠账先抵欠账。"""
        if kind not in KINDS:
            raise ValueError(f"kind 只能是 {'/'.join(KINDS)}，得到 {kind!r}")
        if int(amount) <= 0:
            raise ValueError("amount 必须是正整数")
        expires = _isoformat(expires_at) if expires_at is not None else None
        now = self._clock()
        grant = Grant(
            id=_new_id("g", now),
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
            debt = int(state.get("debt", 0))
            if debt > 0:
                repaid = min(debt, grant.remaining)
                grant = replace(grant, remaining=grant.remaining - repaid)
                state["debt"] = debt - repaid
            state["grants"].append(grant.to_dict())
            self._append_ledger(
                state,
                now,
                delta=grant.amount,
                reason=REASON_GRANT,
                actor=actor,
                extra={"grant_id": grant.id, "note": grant.note},
            )
            if debt > 0:
                self._append_ledger(
                    state,
                    now,
                    delta=-(grant.amount - grant.remaining),
                    reason=REASON_DEBT_REPAID,
                    actor=actor,
                    extra={"grant_id": grant.id, "debt_before": debt},
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
                reason=REASON_REVOKE,
                actor=actor,
                extra={"grant_id": grant_id, "note": note},
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
            remaining=self._available(state, now),
            grants=tuple(live) + tuple(g for g in grants if g not in live),
            next_expiry=min(expiring) if expiring else None,
            holds=self._active_hold_points(state, now),
            debt=int(state.get("debt", 0)),
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

    # ── 内部 ───────────────────────────────────────────────────────────────

    def _metered(self, user_id: str) -> bool:
        return self.enabled and user_id not in self.exempt_users

    def _available(self, state: dict[str, object], now: datetime) -> int:
        grants = (Grant(**g) for g in state["grants"])  # type: ignore[union-attr]
        live = sum(
            g.remaining for g in grants if g.remaining > 0 and not g.expired(now)
        )
        return live - self._active_hold_points(state, now) - int(state.get("debt", 0))

    def _active_hold_points(self, state: dict[str, object], now: datetime) -> int:
        total = 0
        for hold in state.get("holds", {}).values():  # type: ignore[union-attr]
            if self._hold_stale(hold, now):
                continue
            total += _int_or_zero(hold.get("points"))
        return total

    @staticmethod
    def _hold_stale(hold: Mapping[str, object], now: datetime) -> bool:
        try:
            at = datetime.fromisoformat(str(hold.get("at")))
        except ValueError:
            return True
        return now - at > _HOLD_TTL

    def _prune_holds(self, state: dict[str, object], now: datetime) -> None:
        holds = state.setdefault("holds", {})
        for hold_id in [
            hid for hid, hold in holds.items() if self._hold_stale(hold, now)
        ]:  # type: ignore[union-attr]
            del holds[hold_id]  # type: ignore[index]

    @staticmethod
    def _pop_hold(
        state: dict[str, object], *, hold_id: str | None, run_id: str | None
    ) -> int:
        holds = state.setdefault("holds", {})
        assert isinstance(holds, dict)
        target: str | None = None
        if hold_id is not None and hold_id in holds:
            target = hold_id
        elif run_id is not None:
            target = next(
                (hid for hid, h in holds.items() if h.get("run_id") == run_id), None
            )
        if target is None:
            return 0
        released = _int_or_zero(holds.pop(target).get("points"))
        return released

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
        return {
            "version": _SCHEMA_VERSION,
            "grants": [],
            "ledger": [],
            "holds": {},
            "debt": 0,
        }

    @staticmethod
    def _load(path: Path) -> dict[str, object]:
        raw = path.read_text(encoding="utf-8")  # FileNotFoundError 原样抛给调用方
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
        state.setdefault("holds", {})
        state.setdefault("debt", 0)
        if not isinstance(state["holds"], dict):
            raise CorruptLedger(str(path))
        return state

    def _load_or_bootstrap(self, path: Path, now: datetime) -> dict[str, object]:
        try:
            return self._load(path)
        except FileNotFoundError:
            state = self._empty_state()
            if self.signup_gift > 0:
                gift = Grant(
                    id=_new_id("g", now),
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
                    reason=REASON_GRANT,
                    actor="signup",
                    extra={"grant_id": gift.id, "note": gift.note},
                )
            return state

    @staticmethod
    def _append_ledger(
        state: dict[str, object],
        now: datetime,
        *,
        delta: int,
        reason: str,
        actor: str,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        row: dict[str, object] = {
            "at": _isoformat(now),
            "delta": int(delta),
            "reason": reason,
            "actor": actor,
        }
        for key, value in (extra or {}).items():
            if value not in (None, "", [], {}):
                row[key] = value
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


def points_to_yuan_text(points: int) -> str:
    """积分 → 元的展示文本（100 积分 = 1 元）。"""
    sign = "-" if points < 0 else ""
    yuan, fen = divmod(abs(points), POINTS_PER_YUAN)
    return f"{sign}¥{yuan}.{fen:02d}"


__all__ = [
    "CostBreakdown",
    "CreditBalance",
    "CreditDecision",
    "CreditPricing",
    "CreditStore",
    "CorruptLedger",
    "Grant",
    "KIND_GIFT",
    "KIND_MONTHLY",
    "KINDS",
    "POINTS_PER_YUAN",
    "RunUsage",
    "Settlement",
    "points_to_yuan_text",
    "read_run_usage",
]
