# 2026-10-01 harness 优化（与 2×2 实验不冲突的部分）

基线：origin/main `3a2718c6` + `qc-p0-fixes.patch`（`259e9378`）。四个独立提交，可分别合入或回滚。

## 1. 换库锁在 Linux 上失效 → OFD 锁 + 自检（`market_feature_store/db.py`）

- 实测（duckdb 1.5.4，Linux）：DuckDB rw 写者在场时 `flock(LOCK_SH|LOCK_NB)` **照样拿到**——flock 与 DuckDB 的 fcntl 记录锁在 Linux 上互不可见，换库窗口形同虚设。macOS 上二者互斥，所以 Mac 生产一直是对的。
- 修法：Linux 用 `F_OFD_SETLK F_RDLCK`（与传统记录锁互斥、同进程也互斥、不因关别的 fd 丢锁；经典 `lockf` 恰恰会丢，故不用）；macOS 保持 flock；其他平台 `SwapLockUnsupportedError`（DatabaseLockedError 子类 → 编排 rc=2）。每进程首次拿锁前跑一次约 10ms 的进程内语义自检。
- 结果：基线里 6 条 Linux 专属 staging_swap 失败中 5 条转绿；第 6 条（克隆后窗口）依赖 APFS `cp -c`，与锁无关，改为非 macOS 跳过。变异测试：强制回 flock → 6 红。
- Mac 行为不变（同一 flock 路径，只多一次自检）。

## 2. finance_query schema 瘦身（工具面 −32%）

- 8 个工具菜单 35,939 字符，finance_query 占 89%。其中 10,742 字符的「全字段并集 enum」重复 5 次（metrics / dimensions / filters.field / group_by / order_by.field），而它从没拦住过错槽（rank 塞进 dimensions 就发生在 enum 在场时）。
- 改后：字段槽为普通 string，说明指向每张表的「可用字段」；校验仍由 `FinanceQuerySpec` / `_compile_query` + `validation_retry_hint` 负责。finance_query 31,927 → 20,477；合计 → 24,489。
- 守卫：`intelligence/tests/test_tool_surface_budget.py`（预算 finance_query ≤ 22.5K、合计 ≤ 27K；只允许 dataset / filters.op / order_by.direction 三处 enum）。度量：`PYTHONPATH=. python3 scripts/tool_surface_report.py [--json]`。
- **⚠ 与实验的关系**：这会改变所有臂看到的工具面。2×2 实验进行中请**不要**合入这一条，等实验收口后单独合并并单独测（见下方预测）。

## 3. 预测台账只读周报（`scripts/prediction_ledger_status.py`）

- 2026-10-01 实测：Open 表 162 条 = 证实 45 / 部分证实 2 / 证伪 3 / **过期 106**（pending 超 14 天，即全部 pending）/ 其他 6；最新编号 R-20260916，已 15 天没有新预测。
- `--max-silence-days N` 超期退出码 1，可挂 SessionStart / CI 提醒。不改台账；fix_type 冻结枚举未动（报告建议的 MODEL_FIX 需走 known-gaps 晋级线）。

## 4. 路由改写探针 + 口语 market_watch

- `intelligence/eval/cases/route_paraphrase_v1.jsonl`：uq15 每题 3 条改写（口语 / 调序 / 极简）。`scripts/route_paraphrase_probe.py` 走生产同款 `QueryResolver.resolve`，报一致率、兜底率、不一致明细。
- **必须在 Mac（有知识库）上跑**；沙箱锚点命中 0，数字不可引用。沙箱里只有不依赖实体的那组可信：「今天大盘咋样/怎样/走势如何」原先掉进 `general_finance_qa`，已修（谓词扩充，锚不变；题材题不被吞，有反向测试）。
- 仍未修、待 Mac 数据确认：调序（「今天成交额多少？大盘表现怎么样？」）与极简（「今日大盘 成交额」）仍落兜底；沙箱里原题兜底率 0.667，需看有知识库时是多少。

## 建议台账条目（只给 ID 草案，未写入 `docs/prediction-ledger.md`，避免与实验 agent 冲突）

| 草案 ID | fix_type | verification_prediction | 怎么验 |
|---|---|---|---|
| R-20261001-01 | HARNESS_FIX | 实验收口后合入 §2：同模型同题集下，finance_query 空参数/畸形参数率下降，字段错槽率不升（≤ 基线 +1pp），单题 prompt token 下降 ≥ 8K | 合入前后各跑同一 uq15 臂，比 tool_call 校验失败分类 |
| R-20261001-02 | HARNESS_FIX | Linux 上 staging_swap 套件全绿（除 APFS 专属 1 条跳过）；Mac 生产换库行为不变 | CI + Mac 跑 `tests/test_market_feature_store_staging_swap.py` |
| R-20261001-03 | ROUTING_FIX | Mac 上 `route_paraphrase_probe.py` 改写一致率 ≥ 0.85；若兜底率 > 0.5，说明 8792 的改写失分主要在路由层而非模型层 | Mac 跑探针，`--json` 存档 |

## Mac 上验证

```bash
cd ~/finance-workspace-private && git fetch origin && git worktree add -b feat/harness-opt-1001 /tmp/harness-opt origin/main && cd /tmp/harness-opt && git am ~/Downloads/qc-p0-fixes.patch ~/Downloads/harness-opt-1001.patch && python3 -m pytest -q tests/test_market_feature_store_staging_swap.py tests/test_prediction_ledger_status.py intelligence/tests/test_tool_surface_budget.py intelligence/tests/test_market_watch_colloquial.py && python3 scripts/route_paraphrase_probe.py
```
