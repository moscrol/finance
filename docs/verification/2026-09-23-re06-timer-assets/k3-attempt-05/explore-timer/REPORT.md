# K3 审查终稿（stage=explore / group=timer / 仅 C7–C10）

**重要交付说明**：本次 stage 在我写入 `work/timer/` 文件之前即被关闭、工具已禁用，因此 **`work/timer/EXPLORE.md` 与 `work/timer/probes/test_reviewer.py` 未能落盘**（仅目录已建）。两份材料的完整内容内嵌于本回复末尾，供下一场直接落盘使用。本会话未运行任何 pytest 或前端测试，以下全部结论为静态证据。

---

## 静态证据（按主张）

### C7 — 前端计时全生命周期使用 activity-timer / v2（源码+产物一致）
- `intelligence/webapp/src/components/ResearchActivityControl.tsx`
  - L35–46：唯一的 `consent(action, hash)` 构造函数，固定 `event_type:"consent_changed"`、`consent_version:"workbench-activity-v2"`、`scopes:["activity-timer"]`；撤回时 `effective_at = max(now, lastEnd+1)`。
  - 授权：L85 `send([consent("grant", hash)])`；停止：L65–70 `stop()` 内 push `consent("withdraw", ...)`；切会话：`useEffect` 依赖 `[conversationId, user]`（L117），cleanup（L112–116）→ `stop()`；离开页：L108–110 `pagehide` → `stop()`。失败兜底（L87–88、L100–101）也用同一构造器。组件内无 research/logging scope。
- 交付面核对：`intelligence/api/static/index.html` L9 引用 `/assets/index-BobixB9S.js`，文件存在于 `static/assets/`（411798 字节）。`rg -o` 窄查该 bundle：`consent_changed`×1、`consent_version:"workbench-activity-v2"`×1、`scopes:["activity-timer"]`×1、`workbench-activity-v1`×0、无 `scopes:[...research...]`。**产物与组件协议一致**。
- **UI 未动态验证**（未开浏览器、未跑 vitest）。

### C8 — measurement_scopes 分类（`consent.py` L40–61）
- 纯计时：`scopes == {ACTIVITY_TIMER_SCOPE}` → 返回 `None`（L56–57），与版本/来源无关，不表达测量意愿。
- 空 scope：`payload.get("scopes") or ()` → `frozenset()`（**非 None**）→ 读侧 `measure.py` L160–162 只跳 `None`，空集仍入时间线 → `_scopes_at` 返回 `frozenset()` 而非 None；写侧 `run_observer.py` L172–175 `entries` 非空 → 必须覆盖 REQUIRED → False。**空/部分（["research"]）/混合（["activity-timer","research"]→{"research"}）均不错误回落自用默认**。混合含全量时 `{"research","logging"}` 正常覆盖。
- 常数：`contracts.py` L148–153；校验允许空 scopes 列表（`events.py` L271–275），无 consent_version 白名单。

### C9 — 旧 v1 仅完整自用形状对称兼容（`consent.py` L45–55）
转换需**同时**满足：`consent_version=="workbench-activity-v1"`、`scopes=={research,logging}` 精确相等、`source_channel=="frontend"`、`protocol_version=="workbench-self-use/v1"`、`pilot_id` 以 `"workbench:"` 前缀、`participant_id==owner_user_id`、owner 非空、`task_id is None`。任一不满足即不转换（v1 的 {research,logging} 按真实测量同意处理）；分类与 action 无关 → **授权/撤回对称**。严格性细节：`task_id==""` 不通过 `is None`；`pilot_id=None`/`owner==""` 均不转换。

### C10 — 撤回不被重计时覆盖 / 计时不授权试点 / 不改写
- 写侧 `_measurement_consented`（`run_observer.py` L138–175）：只认 owner 记录；`measurement_scopes is None` 的记录（纯计时+旧 v1 自用）L169–171 被排除出 `entries`——真实 research/logging 撤回后，重启计时产生的记录**永不进入折叠**，撤回保持生效。
- 读侧 `_consent_timeline`（`measure.py` L147–166）：timer 记录同样被 None 排除 → 仅计时台账 `_scopes_at` 返回 None（unknown limitation），不产生试点授权。
- 不改写：分类纯读；`rg` 全仓（排除测试/前端）仅 `consent.py:45` 出现 `workbench-activity-v1`，**无任何迁移/回写代码**；`measurement_scopes` 只 `get` 不 mutate。内容摘要路径（`summarize.py`）**未审查**，列为边界。

## 疑点与边界（suspected issues / limits）
1. `measurement_scopes` 假设台账已过校验：若 `payload.scopes` 为裸字符串会被逐字符拆解（契约外输入，写入路径有 `validate_event` 拦截，未实证该拦截在全部入口）。
2. 旧 v1 且 `participant_id=None` 的记录不符自用形状 → 被当作真实测量授权（设计内，但值得下一场用探针钉死）。
3. 前端撤回 `lastEnd+1ms` 守卫对测量折叠是冗余的（计时记录本就被排除），无害。
4. `pagehide` 撤回为 fire-and-forget，keepalive 不保证送达（组件注释已声明留缺口）；未动态验证。
5. Tyler：C1–C6 由其他组签字，本场不背书；C5/C6 相关折叠与锁内复核代码已见（`scopes_at`、`run_observer.py` L215+）但不做结论。

## 下一场命令（探针落盘后）
```bash
CAND=/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-05/candidate/finance-workspace-private
W=/Users/a77/.finance-runtime/reviews/re06-timer-scope-qc-20260923-05/work/timer
cd $CAND && PYTHONPATH=$CAND /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest $W/probes/test_reviewer.py -q
# 作者既有测试（对照，非替代）：intelligence/tests/test_re06_activity_consent_gate_effect.py
# 前端（非本场执行）：intelligence/webapp 下 vitest ResearchActivityControl.test.tsx / researchActivity.test.ts
```

## 应落盘而未落盘的材料

**`work/timer/EXPLORE.md`** 内容 = 本回复"静态证据+疑点+边界+命令"各节（可直接复制）。

**`work/timer/probes/test_reviewer.py`**（自造探针，未运行）：

```python
"""K3 reviewer probes C7-C10 (group=timer). 自造构造器 + tmp_path；不触生产/网络/真实LLM。"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from intelligence.services.product_value import measure as M, validate_event
from intelligence.services.product_value.consent import measurement_scopes, covers_measurement
from intelligence.services.product_value.contracts import (
    ACTIVITY_TIMER_SCOPE, EVENT_SCHEMA, PROVENANCE_OBSERVED,
    REQUIRED_MEASUREMENT_SCOPES, SOURCE_FRONTEND, SOURCE_SERVER,
)
from intelligence.services.research_evolution.run_observer import ObservingRunStore

OWNER = "k3-reviewer-owner"
T0 = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)

def at(m): return T0 + timedelta(minutes=m)

def make_event(m, action, scopes, *, version="bench-v9", source=SOURCE_SERVER,
               protocol="workbench-self-use/v1", pilot=f"workbench:{OWNER}",
               participant=OWNER, owner=OWNER, task=None, tag="x"):
    stamp = at(m).isoformat()
    return {"schema_version": EVENT_SCHEMA, "event_id": f"k3-{tag}-{m}-{action}",
        "event_type": "consent_changed", "owner_user_id": owner, "pilot_id": pilot,
        "participant_id": participant, "task_id": task, "case_id": None,
        "case_version": None, "case_pair_id": None, "run_ids": [], "object_refs": [],
        "assistance_condition": None, "event_at": stamp, "recorded_at": stamp,
        "source_version": {"code_sha": "k3", "protocol_version": protocol, "artifact_hash": None},
        "provenance": {"kind": PROVENANCE_OBSERVED, "source_ref": "k3", "source_hash": None},
        "source_channel": source,
        "payload": {"consent_version": version, "scopes": scopes, "effective_at": stamp,
            "action": action, "terms_hash": "sha256:" + "ab" * 32,
            "initiator": "user", "assistance_source": "workbench"},
        "gaps": []}

def legacy_timer(m, action, tag="legacy", **over):
    return make_event(m, action, ["research", "logging"], version="workbench-activity-v1",
                      source=SOURCE_FRONTEND, tag=tag, **over)

def v2_timer(m, action, tag="v2", **over):
    return make_event(m, action, [ACTIVITY_TIMER_SCOPE], version="workbench-activity-v2",
                      source=SOURCE_FRONTEND, tag=tag, **over)

def store_with(tmp_path, events):
    store = ObservingRunStore(user_id=OWNER, root=tmp_path / "runs", evolution_root=tmp_path / "evo")
    with store._evolution_store.transaction() as txn:
        for e in events:
            r = validate_event(e); assert r.ok, [i.code for i in r.issues]
            txn.append_product_value_event(r.normalized or e, content_hash=r.content_hash or "")
    return store

def gate(tmp_path, events, m): return store_with(tmp_path, events)._measurement_consented(at(m))
def read_side(tmp_path, events, m):
    evs = store_with(tmp_path, events)._evolution_store.list_product_value_events()
    return M._scopes_at(M._consent_timeline(evs), OWNER, at(m))

# --- C8 分类 ---
def test_pure_timer_is_none_any_version():
    assert measurement_scopes(v2_timer(0, "grant")) is None
    assert measurement_scopes(make_event(0, "withdraw", ["activity-timer"], version="anything")) is None

def test_empty_scope_is_record_not_default():
    r = measurement_scopes(make_event(0, "grant", []))
    assert r == frozenset() and r is not None and not covers_measurement(r)

def test_partial_and_mixed_scopes():
    assert measurement_scopes(make_event(0, "grant", ["research"])) == {"research"}
    assert measurement_scopes(make_event(0, "grant", ["activity-timer", "research"])) == {"research"}
    full = measurement_scopes(make_event(0, "grant", ["activity-timer", "research", "logging"]))
    assert full == REQUIRED_MEASUREMENT_SCOPES and covers_measurement(full)

def test_missing_payload_and_scopes_key():
    assert measurement_scopes({"payload": {}}) == frozenset()
    assert measurement_scopes({}) == frozenset()

# --- C9 旧形状 ---
@pytest.mark.parametrize("action", ["grant", "withdraw"])
def test_legacy_full_shape_symmetric(action):
    assert measurement_scopes(legacy_timer(0, action)) is None

@pytest.mark.parametrize("over", [
    {"source": SOURCE_SERVER}, {"protocol": "pilot/v1"}, {"pilot": "pilot-9"},
    {"participant": "other-user"}, {"task": "t-1"}, {"participant": None},
    {"version": "workbench-activity-v2"},
])
def test_legacy_mismatch_not_converted(over):
    assert measurement_scopes(legacy_timer(0, "grant", **over)) == REQUIRED_MEASUREMENT_SCOPES

def test_legacy_partial_scopes_not_converted():
    assert measurement_scopes(legacy_timer(0, "withdraw", scopes := None) if False
        else make_event(0, "withdraw", ["research"], version="workbench-activity-v1",
                        source=SOURCE_FRONTEND)) == {"research"}
    extra = make_event(0, "grant", ["research", "logging", "blind_review"],
                       version="workbench-activity-v1", source=SOURCE_FRONTEND)
    assert measurement_scopes(extra) == {"research", "logging", "blind_review"}

# --- C10 写侧门 + 读侧 ---
def test_no_records_default_open(tmp_path):
    assert gate(tmp_path, [], 1) is True

@pytest.mark.parametrize("cycle", ["v1", "v2"])
def test_timer_only_keeps_default_and_read_unknown(tmp_path, cycle):
    mk = legacy_timer if cycle == "v1" else v2_timer
    evs = [mk(0, "grant", "a"), mk(5, "withdraw", "b")]
    assert gate(tmp_path, evs, 6) is True and read_side(tmp_path, evs, 6) is None

def test_real_withdrawal_survives_timer_restart(tmp_path):
    for mk in (legacy_timer, v2_timer):
        evs = [make_event(-9, "grant", ["research", "logging"], tag="m1"),
               make_event(-7, "withdraw", ["logging"], tag="m2"),
               mk(-5, "grant", "t1"), mk(-4, "withdraw", "t2"), mk(3, "grant", "t3")]
        for m in (-6, 0, 4):
            assert gate(tmp_path / mk.__name__, evs, m) is False, mk.__name__
            assert read_side(tmp_path / f"{mk.__name__}r", evs, m) == {"research"}

def test_timer_withdraw_never_revokes_measurement(tmp_path):
    evs = [make_event(-2, "grant", ["research", "logging"], tag="m"),
           v2_timer(-1, "withdraw", "t"), legacy_timer(0, "withdraw", "t2")]
    assert gate(tmp_path, evs, 2) is True

def test_partial_grant_flips_default_despite_timer(tmp_path):
    evs = [make_event(-1, "grant", ["blind_review"], tag="p"), v2_timer(0, "grant", "t")]
    assert gate(tmp_path, evs, 1) is False

def test_empty_scope_record_blocks_default_both_sides(tmp_path):
    evs = [make_event(-1, "grant", [], tag="e")]
    assert gate(tmp_path, evs, 0) is False
    assert read_side(tmp_path, evs, 0) == frozenset()  # 非 None：不算未知/默认

def test_ledger_and_hashes_not_rewritten(tmp_path):
    evs = [legacy_timer(0, "grant", "a"), legacy_timer(2, "withdraw", "b"),
           v2_timer(4, "grant", "c"), v2_timer(6, "withdraw", "d")]
    store = store_with(tmp_path, evs)
    before = deepcopy(store._evolution_store.list_product_value_events())
    for m in (1, 3, 5, 7):
        store._measurement_consented(at(m))
        M._consent_timeline(store._evolution_store.list_product_value_events())
    after = store._evolution_store.list_product_value_events()
    assert after == before
    for orig, stored in zip(evs, after):
        r = validate_event(orig); assert r.ok
        assert stored.get("payload", {}).get("scopes") == orig["payload"]["scopes"]
```

（注：`test_legacy_partial_scopes_not_converted` 首段写法啰嗦，落盘时可化简为直接构造。）

## 未完成工作声明
- `EXPLORE.md` 与 `test_reviewer.py` **未写入磁盘**（stage 提前关闭），内容以上述内嵌为准；**探针未执行**，不得视为通过。
- C7 前端仅源码+bundle 静态核对，**UI 未动态验证**；作者前端测试未读全文、未运行。
- `summarize.py` 摘要路径、`postResearchEvolutionEvents` 服务端补戳逻辑未审查；C1–C6 不属于本场。

```json
{"stage":"explore","group":"timer","revision":"b24c86f87aaef6244dc6a2c6cf80f74ae1918943","baseline":"ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb","complete":true,"artifacts":[],"suspected_issues":["measurement_scopes 假定台账已过校验：payload.scopes 为裸字符串会逐字符拆解（契约外输入，未实证全部写入入口均有 validate_event 拦截）","participant_id=None 的旧 v1 全形状记录不转换、被当作真实测量同意（设计内但需探针钉死）","内容摘要 summarize.py 与事件接收端补戳路径未审查：C10『摘要不改写』仅有 consent.py 无回写代码的间接证据"],"limits":["EXPLORE.md 与 probes/test_reviewer.py 因 stage 提前关闭未写入 work/timer/，内容内嵌于本回复","所有 pytest 探针未执行，不构成通过证据","前端 UI 未动态验证；bundle 核对基于 rg -o 窄查","仅审 C7-C10，C1-C6 不背书"]}
```
