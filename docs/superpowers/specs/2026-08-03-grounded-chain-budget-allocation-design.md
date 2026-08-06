# Grounded 合成链预算可达性设计

**日期：** 2026-08-03

**状态：** 实验已完成，方案被证明必要但不足；当前代码不可作为产品修复直接合并

**目标分支：** `fix/grounded-chain-critical-path`

## 0. 实验后更正

post-fix A4 证明 child `90→115` 与新 allocator 已生效，但 brief 仍在 28 秒 grant 硬截断。初版 M2 随后漏读同目录 `smoke-phase-check.json@6c16b73a`：同日同日期、同为17/17 claim与2条 prepared message的 A1 已有 brief `ok 69.740s`，composer 又运行20.261s仍未完成。按当前 `T=115s` 与28.75秒 judge reserve，给足 brief 后 composer 仅约16.5秒，低于其观测下界。

因此方案 A 消除了“预算字段不可达”，却不能让三次串行 LLM 装进现有预算；继续调 brief cap 只会把失败后移。下一步必须在两条架构路线中选择：产品接受约250秒级 deep mode 并重定义 SLA，或工程上采用确定性 DecisionBrief（E）删除一次 LLM 往返。更正后的证据见 `docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md`。

## 1. 问题与实测边界

Grounded Presenter 依次执行：

```text
DecisionBrief → Composer → deterministic gate → semantic judge → present/fallback
```

turn 根预算固定为 120 秒，但子链当前存在两次结构性收窄：

1. `shadow_grounded_timeout` 默认 90 秒，使子链即使在 root 尚有约 118 秒时也只能看见 90 秒。
2. brief/composer/judge 分别按“当时剩余”的 `0.25 / 0.50 / 0.35` 取片。即使每段都用满，三段合计只能触达初始子链预算约 75.6%，越靠后的 judge 越缺时间。

修复前 A4 实测 run：`run_20260803_162718_999605`。

- preflight：`main@e785f833`，正确走 grounded 路径；
- daily-review：1.259 秒完成；
- brief 入口 child 余量：89,999ms；
- brief grant：22 秒；
- brief：22.010 秒后 `deadline_exhausted_local`；
- turn 结束 root 仍余：96,569ms；
- composer/judge：未启动。

因此本设计只确认“预算不可达先造成 A4 失败”。它不声称 brief 最贵，不声称三段真实总需求一定小于 120 秒，也不提前选择确定性 brief（E）。完整 M1 报告见 `docs/verification/2026-08-03-a4-grounded-budget-m1-triage.md`。

## 2. 设计目标

1. 不提高 root 120 秒上限。
2. 不修改 prompt、token 上限、模型、retry、deterministic gate 或 judge fail-closed 语义。
3. 让 Grounded 子链触达 root 本来给得起的时间，同时给 turn 收尾留出约 5 秒外层余量。
4. 串行阶段按初始总额规划，不再递归乘“当时剩余”。
5. brief 提前结束后，未使用时间自动回吐给 composer；composer 提前结束后，剩余全部归 judge。
6. judge 必须有预留，不允许前两段把它饿死。
7. 先用纯预算单元测试建立秒级红/绿环，再做一次真实 A4 M2；不得先跑 A 组。

## 3. 非目标

- 不做 DecisionBrief 确定性投影。
- 不把 judge 异步后置。
- 不新增小模型或切换 provider。
- 不做 token/吞吐预测调度。
- 不改变 `released_unverified` 白名单。
- 不修改 acceptance 正典题面或 SHA256。
- 不合并 `fix/kb-rag-worker-attribution`；该变量在预算实验关账后单独处理。

## 4. 方案比较

### 方案 A：初始总额 + 尾段保留 + 前段回吐（采用）

子链启动时冻结一次初始可用总额 `T`：

```text
brief_cap     = 0.25 × T
judge_reserve = 0.25 × T

brief_timeout    = min(current_remaining, brief_cap)
composer_timeout = max(0, current_remaining - judge_reserve)
judge_timeout    = current_remaining
```

解释：

- brief 延续现有 25% 上限，不让第一段重新吞掉全链；
- composer 不使用固定 50% 片，而是使用“当前剩余减 judge 保留”，所以能接住 brief 回吐；
- judge 最后获得所有剩余，因此 composer 回吐也会自然进入 judge；
- 三段加起来可以触达 100% child，而不是结构性只触达 75.6%。

当 `T=115s` 且 brief 用满时，约为：

```text
brief ≤ 28.75s
composer ≤ 57.50s
judge ≥ 28.75s
```

若 brief 只用 20 秒，composer 上限自动增加到约 66 秒；如果 composer 提前完成，judge 获得更多时间。

优点：沿用既有 brief 25% 约束；不依赖未经测量的 token/s；可用一个纯函数完整测试。

缺点：A4 brief 的真实自然完成耗时仍未知，28.75 秒可能仍不够；这正是 post-fix A4 要回答的问题，而不是现在拍数字规避的问题。

### 方案 B：固定秒数 35/45/30（不采用）

优点是直观、容易解释。缺点是这些秒数来自有限旧样本与代码推演，模型、题型或 prompt 长度变化后需要人工重拍；还会把一次性能诊断变成永久产品常量。

### 方案 C：按 token 与吞吐自适应（后续候选）

优点是理论上能按每轮复杂度动态分配。缺点是当前 phase telemetry 没有可靠 token 对账，provider 也不保证每次返回完整 usage；现在实施会混入估算误差、调度策略与新的降级分支，破坏本轮单变量实验。

## 5. Child deadline

`AskOptions.shadow_grounded_timeout` 默认值从 90 改为 115 秒：

```text
child_deadline = min(now + 115s, parent_deadline)
```

这不扩大 root 权限：parent 少于 115 秒时仍以 parent 为准；没有 parent 时维持 child 自己的硬上限。

选择 115 而非 120 的原因是让外层 turn 保留约 5 秒用于投影、artifact 写入、stream 收尾和 report 完成。该余量不是 phase 质量预算，不允许被 composer/judge 借用。

环境变量 `WORKBENCH_SHADOW_GROUNDED_TIMEOUT` 仍可显式覆盖默认值；受控实验与产物必须记录实际 child 入口余量，不能只相信配置声明。

## 6. 预算组件边界

在 `intelligence/services/ask_synthesis.py` 内新增一个只处理数值的私有预算计划对象，例如：

```python
@dataclass(frozen=True)
class _GroundedPhaseBudget:
    initial_seconds: float
    brief_cap_seconds: float
    judge_reserve_seconds: float

    @classmethod
    def from_total(cls, total_seconds: float) -> "_GroundedPhaseBudget":
        total = max(0.0, float(total_seconds))
        return cls(
            initial_seconds=total,
            brief_cap_seconds=total * 0.25,
            judge_reserve_seconds=total * 0.25,
        )

    def timeout_for(self, phase: str, remaining_seconds: float) -> int:
        remaining = max(0.0, float(remaining_seconds))
        if phase == "brief":
            grant = min(remaining, self.brief_cap_seconds)
        elif phase == "composer":
            grant = max(0.0, remaining - self.judge_reserve_seconds)
        elif phase == "judge":
            grant = remaining
        else:
            raise ValueError(f"unsupported grounded phase: {phase}")
        return max(0, int(grant))
```

职责只有三项：

1. 从初始 child 总额冻结 brief cap 与 judge reserve；
2. 根据实际 current remaining 给当前 phase 返回 grant；
3. 保证返回值不超过 current remaining，且本地 grant 小于 1 秒时由现有 admission control fail-closed。

它不读取 AnswerSpec、prompt、provider、token 或环境变量；这样预算算法可作为纯函数测试，不需要真的等 20–120 秒。

原 `_shadow_phase_timeout(deadline, configured, share)` 将不再作为三段主链的分配入口。Admission control 应检查“实际 grant 是否塌到下限”，不再重新计算 `remaining × share`，避免执行器和准入器各算一套预算。

## 7. 数据流

```text
root ResearchDeadline (≤120s)
        │
        ├─ _shadow_deadline → min(parent, 115s)
        │
        ├─ freeze T and _GroundedPhaseBudget
        │
        ├─ brief: min(remaining, 0.25T)
        │      └─ unused time remains on shared deadline
        │
        ├─ composer: remaining - 0.25T judge reserve
        │      └─ unused time remains on shared deadline
        │
        └─ judge: all remaining
               └─ deterministic/semantic result → present or fail-closed
```

所有 provider retry 继续在各自 phase deadline 内共享 grant，保持 `8ed66020` 的约束不变。

## 8. 失败与降级语义

- grant 小于 1 秒：不发 provider 请求，记录 phase=`skipped`、reason=`insufficient_budget`，继续 fail-closed。
- provider 在 grant 内失败：phase=`failed`，保留现有稳定 reason code。
- brief/composer 本地 deadline 耗尽：不得借 judge reserve。
- judge 本地 deadline 耗尽：仍不得伪装成瞬时 provider outage；不得进入 `released_unverified`。
- deterministic gate 或 semantic judge 拒绝：行为完全不变。
- 顶层 `completed` 仍只表示存在可交付 fallback；合成健康只能读四态诊断。

## 9. 测试设计

### 9.1 纯预算红/绿环

在 `intelligence/tests/test_synthesis_phase_observability.py` 增加以下不变量：

1. `T=115` 时 brief grant 约 28 秒、judge reserve 约 28 秒。
2. brief 使用 20 秒后，composer 可以使用 brief 回吐，但仍不能侵占 judge reserve。
3. composer 提前结束后，judge 获得全部剩余。
4. 任一 grant 不超过 current remaining。
5. 极小 child 预算下 admission control 不发请求。
6. 显式较小 parent deadline 时，child 不突破 parent。
7. 默认环境未覆盖时 `shadow_grounded_timeout=115`；显式环境值仍优先。

该测试必须在秒级完成，不调用网络、不 sleep 真实 phase 时长。

### 9.2 现有回归

至少运行：

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_synthesis_phase_observability.py \
  intelligence/tests/test_phase_slice_enforced.py \
  intelligence/tests/test_judge_outage_degrades.py -q
```

随后运行相关 ask/conversation deadline 套件和全量测试；基线 13 个 userspace/vault 环境红必须按修改前后同名同数对账，不得把“全量不全绿”模糊报告为本次回归。

### 9.3 Live A4 M2

固定不变量：

- query/case：`A4-dual-red`；
- revision 之外的题面、模型、provider、用户、知识库、数据日期不变；
- `ASK_CONTINUOUS_RUNTIME` 未设置；
- base 显式为 `http://127.0.0.1:8801`；
- root 仍为 120 秒；
- 唯一有意变量：child cap + phase allocator。

命令：

```bash
.venv-workbench/bin/python -m intelligence.eval.acceptance run \
  --base http://127.0.0.1:8801 \
  --user linxiaoqi5111 \
  --case A4-dual-red \
  --timeout 180 \
  --output "intelligence/eval/runs/$(date -u +%Y%m%dT%H%M%SZ)-a4-post-budget-fix.json"
```

成功必须同时满足：

- phase 名为 `[brief, composer, judge]`；
- 三段 `status=ok`；
- judge 记录存在；
- `synthesis_diagnostic.state=accepted`；
- `judge.remaining_ms_at_entry - judge.elapsed_ms > 0`；
- 无 `grounded_required_fallback`、无 `released_unverified`。

`elapsed_s<=120` 与 turn `status=completed` 不进入成功判据。

## 10. 决策门

Post-fix A4 只有三种解释：

1. **三段全过且有 slack**：H5 被拒绝，先跑 A 组 10 题，不做 E。
2. **brief 仍在约 29 秒 grant 内失败**：只证明 brief 需要更大 grant；比较调整初始分配与确定性 brief（E），不能直接声称总链装不下。
3. **brief/composer 均完成但 judge 用尽剩余**：H5 获得支持；此时才比较 E、root scoped extension 或其他架构方案，judge 仍不默认异步。

完整 A 组只在单题门通过后运行，四态对照使用最近同组基线：

```text
完整通过 1 / 放行未核验 1 / 模板降级 8
```

## 11. 提交与回滚

提交顺序：

1. 文档 commit：M1 报告、trace profile、本设计；不含运行产物。
2. 首个代码 commit：只修改 child 默认 cap、phase allocator 与对应确定性测试；不含 E、prompt、token 或 judge 时序变化。
3. 若需要，单独提交验收读数/文档，不与运行逻辑混在一起。

回滚首个代码 commit 即恢复原 90 秒 child 与递归比例分片；run artifact 和 M1/M2 报告保留用于解释为什么回滚。
