# 独立 Quality 审核报告（质量轴：工程规范 / 代码质量）

- **审核角色**：独立 Quality 审核者（非作者、非 Spec 审核者）。仅审质量轴，不重复签 Spec 规格矩阵。
- **审核范围**：新片 **R1** + main 合流 **I1**。受审差分 `git diff 34f49ce1...HEAD`；合流背景 `git diff e51c5157...HEAD` 只作上下文，不签原夜跑全部实现或 R2。
- **不做的事**：未执行实现、未提交/push/建PR/合并/部署、未派生子 agent、未修改候选源码（含 code-map 生成物）、未给 main/生产签字。

## 首尾身份核验（首 = 尾）

| 项 | 值 |
|---|---|
| HEAD（首） | `d95b706edc6e44f3dfa54d7b8837dfdd36b16cf2` |
| HEAD（尾） | `d95b706edc6e44f3dfa54d7b8837dfdd36b16cf2` |
| `git status --porcelain`（首/尾） | 空 / 空（`wc -l` = 0） |
| R1 提交 | `d95b706e`（单提交，`d95b706e~1` = `34f49ce1`） |
| 受审差分 vs R1 单提交 | **逐字节 IDENTICAL**（`git diff 34f49ce1...HEAD` ≡ `git show d95b706e`，各 409 行 patch，diff 为空） |

受审差分与 R1 完全一致（356 insertions / 1 deletion），审核对象边界清晰。

## 前置（Spec 轴）

- 报告：`/Users/a77/.finance-runtime/reviews/research-closeout-resume-20260920/nightly-independent/spec-k3/REPORT.md`
- 存在性：存在（7607 字节，mtime 2026-09-20 17:38）
- **SHA256**：`644ba90db91652a9f8aa77410b620a419bf7916b2994989c6f67bd8388b76f1e`
- 结论行：`## 结论：PASS` → 前置满足，继续质量轴。

## 环境 / 命令（全部白名单 env）

解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（→ python3.12.13；duckdb 1.5.4；pytest 8.3.5）。
所有动态复核 env：`env -i HOME=/Users/a77 PATH=/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 TMPDIR=/tmp FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1`（动态复核另加 `PYTHONPATH=<候选>`）。
沙盒与变异副本均只写在 `quality-k3/`；候选树全程只读（仅 `git`/`ruff`/读取）。

## 逐项质量轴

### 1. 异常与失败路径 — PASS
- 新增 `refresh_complete`（`sync_local_sector_members.py:482-490`）只在 `include_completed` 为真时产出三态；判据为「非 dry-run ∧ stitched==candidates ∧ 无 skipped ∧ 无 failed ∧ pending_for_provider==0 ∧ 有 audit 且 audit.complete」。全部为**收窄**条件，未放宽任何既有路径。
- CLI rc2 分支（`cli.py:702-709`）：`include_completed` 时 dry-run 仅打印预览、不 return 2（不写库，合理）；否则 `refresh_complete is not True` → 打印「刷新未完成」+ `return 2`。普通日更不带 `--include-completed` 完全不进此分支，rc 合同不变。
- **无新假成功 / 静默降级**：`test_writer_exception_propagates` 证明写者抛 `OSError` 会穿透 CLI（不被吞）；rc2 被多条测试咬住（见 §4 变异）。

### 2. 职责与重复 — PASS
- 完成判据只算一处：`refresh_complete` 仅在 `stitch_sector_members` 摘要构造里计算，CLI 只做 `is not True` 判定，不复制判据逻辑、不造第二套 freshness 台账（复用既有 `completion_audit`）。
- `recover_local_review.py:124-127` `optional_skip = name in sync.HITHINK_STEPS and result['status'] == 'skip'`：**复用** `run_review_sync.HITHINK_STEPS`（`run_review_sync.py:357` 唯一定义，recover 通过 `load_script` 加载同一模块），非另抄名单。原 `run_review_sync.py:558` 对 HITHINK 失败本就 treat 为非豁免，recover 维持该语义、只放行「可选并行源 + skip」。
- 无死代码、无推测性抽象、无超出本片的通用化：`refresh_complete` 服务于恢复 staging 合同，未向外溢。

### 3. 命名 / 注释 / docstring 与真实行为一致 — PASS
- `sync_local_sector_members.py:379-382` docstring 明确三态：「`refresh_complete` 只证明本轮显式刷新已写完且审计完整；普通日更为 None，dry-run 即使算出了所有行也为 False，旧 success 不能替未完成的刷新作证」——与实现（`not dry_run`、失败路径归 False、仅 `include_completed` 产出非 None）一致。`None/False/True` 三态属实。
- `recover_local_review.py:122-124` 注释（英文）准确描述 optional_skip 收窄意图与「required work 和失败的 Hithink 请求仍须在写成功状态前停止」。
- dry-run 语义文案（cli.py:703-704「刷新预览：未写入，不认证本轮刷新完成」）与行为（dry-run 不写库、`refresh_complete=False`）一致。

### 4. 测试质量 — PASS
- **fixture tiny 且自建**：复用 `tests/test_tiered_sync_local.py` 的 `:memory:` DuckDB（schema 走 `ensure_schema` 全文）+ `tmp_path` 自建 staging 库/JSONL/JSON；不读生产库、不拉市值、无外呼。fixture 互不污染（`completed` 独立连接，monkeypatch 自动还原），无顺序依赖（`--collect-only` 收集 29 条，参数化 id 独立）。
- **无删除/削弱原测试或参数**：`git diff --stat` 显示 356 insertions / 1 deletion，且唯一 deletion 在 `scripts/recover_local_review.py`（把单行 `if result['status'] != 'ok'` 换成 optional_skip 收窄逻辑）；`tests/test_tiered_sync_local.py` 等原有测试在受审差分中未被触碰。
- **断言能咬住缺陷**（2 次撤保护变异，均在 `quality-k3/mut` 外部副本，已删，未改候选）：
  - 变异1：删 CLI 刷新失败分支的 `return 2`（吞掉 rc2）→ **12 failed / 17 passed**，失败含 `test_refresh_cannot_borrow_old_success_when_baseline_expired`、`test_real_refresh_cli_failure_prevents_child_success` 等。→ 咬住。
  - 变异2：recover `optional_skip` 放宽为 `result['status']=='skip'`（不再限 HITHINK_STEPS）→ **2 failed / 27 passed**，失败恰为 `test_required_failures_and_nonoptional_skips_still_block[index-daily-skip]` 与 `[stitch-sector-stocks-skip]`；同用例的 fail/timeout 变体仍正确通过（未被误伤）。→ 精确咬住。
- **子进程/解释器**：测试内不直接起子进程；recover 生产 `main()` 用 `sys.executable -u` 递归自身，`run_review_sync.run_step` 走 `subprocess.run(argv)` 继承受控 staging 环境。本审核的 pytest 调用全程用候选内（venv-workbench）解释器 + 白名单 env。

### 5. 仓规 — PASS
- 仅 venv-workbench 解释器；受审差分 `git diff 34f49ce1...HEAD | grep '^\+.*(/Users/|/home/)'` **无命中**（无新增写死家目录）。
- 无新增生产 writer / inline SQL 直写 / 第二条写入链：`refresh_complete` 是只读判据；recover 仍走 `run_daily_full_staged` staging 原子换库唯一写入链；测试 SQL 只作用于 `:memory:`/tmp fixture。
- 180 日基线未改：recover `recovery_stitch_command` 仍传 `--max-baseline-age-days 180`；差分中 `180` 仅出现在测试的**防守断言**（`test_recovery_bound_remains_180_days` 断言 recover 仍请求 180）与注释。未改审计历史、未改日期门。

### 6. 可维护性 — PASS
- 改动最小且局部：5 文件、356+/1-；核心逻辑增量约 25 行（含 docstring）。
- 打印文案与 rc 语义一致（「刷新未完成…旧成功记录不能替代本轮刷新」↔ rc2；「刷新完成：本轮写入 N 个板块，无待补且审计完整」↔ rc0；dry-run「预览」不认证）。
- 新增 CLI 分支不影响普通日更与 dry-run 合同：`test_nonrefresh_keeps_provider_fallback_contract` 证明非 refresh 仍 rc0 且 `refresh_complete is None`；`test_dry_run_is_preview_not_completed_write` 证明 dry-run rc0、不写库、`refresh_complete is False`。

## 独立动态复核（最小、精选）

| 动作 | 命令要点 | 结果 |
|---|---|---|
| 新测试精选实跑（非全仓/非前端） | `pytest tests/test_stitch_refresh_completion.py tests/test_recovery_refresh_integration.py -q`（PYTHONPATH=候选） | **29 passed**（rc=0），分母精确 17+12 |
| collect-only 分母核验 | `--collect-only -q` | **29 tests collected** |
| 变异1（吞 rc2） | 外部副本删 `return 2` | 12 failed / 17 passed → 咬住 |
| 变异2（放宽 optional_skip） | 外部副本 `optional_skip = status=='skip'` | 2 failed / 27 passed → 精确咬住 skip 用例 |
| lint | `ruff check <5 个改动文件>` | **All checks passed!** |

变异副本 `quality-k3/mut` 用后已删除；候选树工作区在动态复核后复验 `git status --porcelain` 仍为空。

## 关键证据哈希（受审 5 文件，SHA256）

- `market_feature_store/cli.py`：`0a77292f887740869d42149dda73f9eb70b5621c25eac940cc3f77052c5137a1`
- `market_feature_store/sync/sync_local_sector_members.py`：`335f3a4ea8139da311b6b85b92bd455aefa3b1438eae68d2fbbf24e6b8829c0a`
- `scripts/recover_local_review.py`：`15ef02384841f160ef0da6757f7d219a34c149f7a4344f38e3eed05270f8920f`
- `tests/test_stitch_refresh_completion.py`：`2b85aa0f5f5388a7d84e8490b0838b2c7094f4b2c79f3c544502b1e724cda2ec`
- `tests/test_recovery_refresh_integration.py`：`32b26a480dad2edc39e0b68faa821b5e60fbadf6e9adcde4166ff243187b3102`

## 边界 / 附注（非阻断）

- `.agent-memory` 软链在本候选 review 快照树中不存在，偏好卡原文未能就地读取；已读候选根 `AGENTS.md`（内含用户偏好与全部仓规要点），审核据此执行。不影响代码结论。
- 代码地图未使用（审核范围已固定为 5 文件精确差分，无需地图；未修改地图）。
- 本报告不对 main/生产签字，不签原夜跑全部实现或 R2；R1+I1 的质量轴结论仅针对上述固定提交差分。

## 结论：PASS

**issues = []**
