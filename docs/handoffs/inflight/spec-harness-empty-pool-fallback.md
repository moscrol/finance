# 在途交接 · spec/harness-empty-pool-fallback

更新：2026-09-02 19:46 CST · **已闭环：PR #533 已合 `gitea/main=7c241ac0`，主干门禁可采信（7443P/5F 同基线红
`test_dream_mine` 五例，收据 `20260902T114611Z-7c241ac0.json`，见 `inflight/main.md` 顶行），8792 未切。
ResearchHarness 接缝线（decouple spec §4 表）至此抽完，本线无后续单。**

原文（合并前最后一版）：**`fallback_after_empty_batch` 画完即抽，两个提交（spec + 实施）已推 gitea，PR 见下。
合 main 等用户确认；8792 未切。**

## 一句话

decouple spec §4 表里最后一行要抽的接缝。与 `repair_policy` 同一套判据画状态机，结论不同：这台机器只有
一条入口、九道判定全在 `services/empty_pool_fallback.propose_empty_pool_fallback`（纯函数）、恰好一次靠扫
durable 事件——**没有方向相反的错层，不需要先拆再搬**。要收的只有 loop「凑领域判定的输入 + 认识回退
概念」两处。`ResearchHarness` 十五 → 十六方法；`HarnessReferenceLoop` 同位跑同一枪，文首「无空池回退」
那条差消掉。**零行为改动**：既有 4 条 Episode 级用例原样绿，默认接缝与直接调纯函数四形状逐字段相同。

spec：`docs/superpowers/specs/2026-09-02-empty-pool-fallback-state-machine.md`（头部「状态：已实施」）
父线：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md` §4 #8 / §5（十六方法）/ §9 P2

## 提交

| SHA | 内容 |
|---|---|
| `15a7cbe7` | spec：一条入口、九道判定归层、出口、与补枪的双向互斥、两处混合（X1 凑输入 / X2 accumulator 认 call_id 前缀）、接缝签名、三种替代方案为何不选、四条验收 |
| `23a3868f` | 实施：`ToolCallOutcome`（结构声明）+ `FallbackCall{call, request_extras}` + `fallback_after_empty_batch`；Episode 只判剩余槛、算可派工具集、问 harness、派、记 extras，不再 import `empty_pool_fallback`，accumulator 的前缀兜底删掉；参考 loop 每批后同位问同一方法并执行，`_ingest_batch` 加 `request_extras`，pending 深度消息挪到停机判定之后（与 Episode 同序） |

## 接缝

```python
def fallback_after_empty_batch(
    self, batch: Iterable[ToolCallOutcome], *,
    context, registry, authorized_tools: frozenset[str], events: Iterable[object], in_repair: bool,
) -> FallbackCall | None
```

底座递五样自己拥有的事实（本批 `(call, status)` / 此刻真能派的工具 / 事件流 / 阶段 / **调用前**先判剩余槛）；
领域从 `context.information_cutoff` / `registry.opening_prefetch` / `events` 读其余。返回 harness 自己的值
对象而不是 `FallbackProposal`——第二条 loop 的「不 import 任何领域模块」棘轮不动。

## 验证（venv 解释器，cwd 本树）

- `test_empty_pool_fallback.py` +3：等价（空池命中 / 首轮有行 / 预取有行 / 已补过·修复轮 四形状逐字段）；
  有牙（从不回退的 harness → Episode 只跑一次 `finance_query`、无 `fallback_query` 事件；改排涨幅的
  harness → runner 真收到的参数与事件标记随之变）；第二条 loop（同一空池脚本下两条 loop runner 收到的两次
  参数逐字段相同、补查 `tool_request` 领域投影相同、模型消息相同只差 `runtime_budget`、outcome 相同）。
- `test_research_harness.py` +1 棘轮：Episode 不 import `empty_pool_fallback`、源码无 `"empty-pool-fallback"` /
  `"fallback_query"` 字面量、必经 `self._harness.fallback_after_empty_batch`。
- 变异：默认实现硬写 `in_repair=True` → 红 5，恢复后绿。
- 宽网 `-k "repair or episode or harness or glm or sub_research or continuous or runtime or adapter or
  conformance or fallback or empty_pool or backfill or issue or reference or steering or protocol"`
  **2072P / 5S / 1xfail**；ruff `intelligence/` 全过；`layer_audit` ERROR 0 == 基线；pre-commit 十一道门禁全过。

## 下一步

1. 用户确认 → 合 PR；合后跑主干门禁写台账（与 #532 同规程）。
2. 8792 切流时带上（零 live 判据）。
3. **decouple 线 §4 表已抽完。** 剩下的都是明写「属底座、不抽」或「独立决定」的：#9 预算可见性（底座）、
   `_run_sub_research`（需协调器）、`_recover_finalization` 是否并进 repair cycle（需用户拍）、
   `_carry_repair_finish` 两行取舍。再往下是 09-01 spec §11 的「真接 pi-agent-core / 真接 dsh」，那要先推翻
   08-17「不保留运行时依赖」的裁定，不是本线能自行立案的。

## 红线遵守自证

- `empty_pool_fallback.py` 九道判定 / as-of 口径 / `FALLBACK_LIMIT` / 与补枪的互斥零改动；`resume()` 仍不回退。
- 事件 payload：`tool_request` 的回退标记键名与值不变（`fallback_query` / `original_arguments` / `as_of`）。
- 提交一律 pathspec；生产快照 / 8792 / 启动器未碰。
