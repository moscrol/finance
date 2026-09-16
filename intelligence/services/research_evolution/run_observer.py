"""05 自用测量的服务端生产者：观察 run 生命周期，经 06 单 writer 落 product_value 事件。

为什么需要它（QC R3）：05 的 ``measure_pair`` 从 ``run_started`` / ``run_finished`` 事件
发现 attempts，再去 RunStore 解析细节——**仅有真实 RunStore 记录不会自动进入测量分母**。
本模块是 06 规格 §5「服务端观察 run 生命周期」的接线：``RunStore`` 的子类，在三个真实
生命周期漏斗点各写一条事件：

| 钩子 | 事件 |
|---|---|
| ``create_run`` | ``run_started`` |
| ``claim_terminal_run``（completed / failed / cancelled，含 finish_run 与取消） | ``run_finished`` |
| ``claim_failed_run``（执行器失败） | ``run_finished``（status=failed） |

纪律：

- 事件写入失败**不阻断** run 生命周期（测量不能拖垮被测对象），失败原因打印到 stderr；
- 重试 = 新 run = 新 attempt（``attempt_id`` 由 run_id 派生），不新造分配任务；
- 失败 / 取消一样写 ``run_finished``——失败保留在分母里（I08）；
- ``cost_recorded`` 只在 trace 里有可核 token 用量时写，``certainty=unknown``
  （只有用量、没有费率；05 会把它聚成 usage_without_rate，不冒充金额）；
- 自用事件的 ``protocol_version`` 是 ``workbench-self-use/v1``、``pilot_id`` 带会话前缀——
  05 ``summarize`` 按 pilot_id 分区，自用事件永远混不进真人试点读数；
- 同意门（QC I11）：owner 一旦在台账里表达过同意范围，``research`` + ``logging``
  （05 的 ``REQUIRED_MEASUREMENT_SCOPES``）都在事件时刻生效才写这三类事件；撤回其一后
  研究照常跑，测量停。没有任何同意记录时保持自用默认（照写）——owner 观察自己，没人可问；
  注意首条只授部分范围（如只授 ``blind_review``）也算「表达过」，会把自用默认翻成不写（复核 T08）。
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from intelligence.services.research_evolution.contracts import SELF_USE_PROTOCOL_VERSION, stable_id, utc_iso
from intelligence.services.research_evolution.store import EvolutionStore, StoreLockTimeout
from intelligence.services.run_store import Run, RunStore

__all__ = ["SELF_USE_PROTOCOL_VERSION", "ObservingRunStore"]


class ObservingRunStore(RunStore):
    """RunStore + 05 生命周期事件。事件走 06 的 ``EvolutionStore``（同 writer、同 owner 根）。"""

    def __init__(
        self,
        user_id: str | None = None,
        root: Path | None = None,
        *,
        evolution_root: Path | str,
        clock: Callable[[], datetime] | None = None,
        code_sha: str = "",
        maintenance_folder: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(user_id=user_id, root=root)
        self._evolution_store = EvolutionStore(evolution_root, self.user_id)
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._code_sha = code_sha or "unknown"
        # run 终态后的维护项收尾回调（QC Q2）：由 app 接线注入（facade.fold_run_terminal 的闭包），
        # 拿 run_id 查登记关联并折回。回调失败同样只 stderr，不阻断被测 run。
        self._maintenance_folder = maintenance_folder

    # ---- 生命周期钩子 ------------------------------------------------------ #
    def create_run(self, *args: Any, **kwargs: Any) -> Run:
        run = super().create_run(*args, **kwargs)
        self._record_lifecycle("run_started", run, status=str(run.status))
        return run

    def claim_terminal_run(self, run_id: str, status: str, *, error: str | None = None) -> tuple[Run, bool]:
        run, claimed = super().claim_terminal_run(run_id, status, error=error)
        if claimed:
            self._record_lifecycle("run_finished", run, status=status)
            self._record_cost(run)
            self._fold_maintenance(run)
        return run, claimed

    def claim_failed_run(self, run_id: str, *, error: str, degrade: str) -> tuple[Run, bool]:
        run, claimed = super().claim_failed_run(run_id, error=error, degrade=degrade)
        if claimed:
            self._record_lifecycle("run_finished", run, status="failed")
            self._record_cost(run)
            self._fold_maintenance(run)
        return run, claimed

    def _fold_maintenance(self, run: Run) -> None:
        """终态收尾（QC Q2）：失败只留 stderr；回调内部用有界事务，不把终态 claim 堵在测量锁上。"""
        if self._maintenance_folder is None:
            return
        try:
            self._maintenance_folder(run.run_id)
        except Exception as exc:  # noqa: BLE001 - 收尾失败可恢复（客户端 link_run / 重试），不阻断 run
            print(f"[research-evolution] run 终态收尾失败（{run.run_id}）：{exc}", file=sys.stderr)

    # ---- 事件构造与落盘 ----------------------------------------------------- #
    def _record_lifecycle(self, event_type: str, run: Run, *, status: str) -> None:
        payload = {
            "run_id": run.run_id,
            "attempt_id": run.run_id,  # Workbench 自用：一次 run 一次执行；重试是新 run
            "status": status,
            "error_ref": None,
            "initiator": "system",
            "assistance_source": "workbench",
        }
        self._record(event_type, run, payload)

    def _record_cost(self, run: Run) -> None:
        """终态时若 trace 里有可核 token 用量，写一条 certainty=unknown 的 cost_recorded。"""
        try:
            steps = self.load_trace(run.run_id)
        except (OSError, ValueError):
            return
        tokens = sum(int(s["tokens"]) for s in steps if isinstance(s.get("tokens"), (int, float)) and not isinstance(s.get("tokens"), bool))
        if tokens <= 0:
            return
        cost_item = {
            "cost_id": stable_id("cost", {"run": run.run_id, "component": "writer_model"}),
            "component": "writer_model",
            "run_id": run.run_id,
            "attempt_id": run.run_id,
            "span_id": None,
            "coverage_scope": "run",
            "quantity": tokens,
            "unit": "tokens",
            "amount": None,
            "currency": None,
            "certainty": "unknown",
            "evidence_ref": None,
            "rate_version": None,
            "allocation_rule": None,
        }
        self._record(
            "cost_recorded",
            run,
            {"cost_item": cost_item, "initiator": "system", "assistance_source": "workbench"},
        )

    def _measurement_consented(self, at: datetime) -> bool:
        """自用测量的同意门（QC I11）。

        只认 owner 自己的 ``consent_changed`` 记录（``participant_id`` 为空或等于 owner），按
        ``effective_at``（缺则 ``event_at``）排序折叠 grant / withdraw，得到 ``at`` 时刻生效的范围。
        没有任何记录返回 True（自用默认，见模块说明）；有记录则必须覆盖 ``REQUIRED_MEASUREMENT_SCOPES``。
        台账读不出来按「未知」处理并留 stderr 痕迹（门本身放行）；但同一份坏台账会让随后的
        ``append_product_value_event`` 重读时再抛一次，净效果是**不写 + 两行 stderr**（第九轮复核 T12 实测）——
        同意门是测量的门，不是被测 run 的门，两处都不会阻断 run。
        """
        try:
            from intelligence.services.product_value.contracts import REQUIRED_MEASUREMENT_SCOPES
            from intelligence.services.product_value.events import parse_ts

            events = self._evolution_store.list_product_value_events()
        except Exception as exc:  # noqa: BLE001 - 读台账失败不阻断被测对象
            print(f"[research-evolution] 读同意记录失败，按未知处理（继续写测量事件）：{exc}", file=sys.stderr)
            return True
        entries: list[tuple[datetime, str, frozenset[str]]] = []
        for event in events:
            if event.get("event_type") != "consent_changed":
                continue
            if event.get("participant_id") not in (None, self.user_id):
                continue
            payload = event.get("payload") or {}
            effective = parse_ts(payload.get("effective_at")) or parse_ts(event.get("event_at"))
            if effective is None:
                continue
            entries.append((effective, str(payload.get("action")), frozenset(str(s) for s in payload.get("scopes") or ())))
        if not entries:
            return True
        entries.sort(key=lambda item: (item[0], item[1]))
        active: set[str] = set()
        for effective, action, scopes in entries:
            if effective > at:
                break
            if action == "grant":
                active |= scopes
            elif action == "withdraw":
                active -= scopes
        return REQUIRED_MEASUREMENT_SCOPES <= active

    def _record(self, event_type: str, run: Run, payload: dict[str, Any]) -> None:
        """构造 + 05 校验 + 同 writer 落盘；任何失败只留 stderr 痕迹，不阻断 run 生命周期。"""
        try:
            from intelligence.services.product_value import validate_event
            from intelligence.services.product_value.contracts import EVENT_SCHEMA, PROVENANCE_OBSERVED, SOURCE_SERVER

            now = self._clock()
            if not self._measurement_consented(now):
                print(f"[research-evolution] owner 未同意测量范围，跳过 {event_type}（{run.run_id}）；研究不受影响", file=sys.stderr)
                return
            stamp = utc_iso(now)
            session = str(run.session_id or "no-session")
            event = {
                "schema_version": EVENT_SCHEMA,
                "event_id": stable_id("pve", {"type": event_type, "run": run.run_id, "status": payload.get("status")}),
                "event_type": event_type,
                "owner_user_id": self.user_id,
                "pilot_id": f"workbench:{session}",
                "participant_id": None,
                "task_id": None,
                "case_id": None,
                "case_version": None,
                "case_pair_id": None,
                "run_ids": [run.run_id],
                "object_refs": [],
                "assistance_condition": None,
                "event_at": stamp,
                "recorded_at": stamp,
                "source_version": {"code_sha": self._code_sha, "protocol_version": SELF_USE_PROTOCOL_VERSION, "artifact_hash": None},
                "provenance": {"kind": PROVENANCE_OBSERVED, "source_ref": f"run:{run.run_id}", "source_hash": None},
                "source_channel": SOURCE_SERVER,
                "payload": payload,
                "gaps": [
                    {"field": name, "reason": "not_applicable"}
                    for name in ("participant_id", "task_id", "case_id", "case_version", "case_pair_id", "assistance_condition")
                ],
            }
            result = validate_event(event)
            if not result.ok:
                raise ValueError(f"05 校验未过：{[i.code for i in result.issues]}")
            # 有界事务（QC Q9）：拿不到测量锁就跳过本次事件——测量写入绝不把被测 run 堵在锁上。
            with self._evolution_store.try_transaction(timeout=0.2) as txn:
                txn.append_product_value_event(result.normalized or event, content_hash=result.content_hash or "")
        except StoreLockTimeout as exc:
            print(f"[research-evolution] 测量锁被占，跳过本次事件落盘（{event_type} {run.run_id}）：{exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - 测量写失败不阻断被测对象
            print(f"[research-evolution] run 生命周期事件落盘失败（{event_type} {run.run_id}）：{exc}", file=sys.stderr)
