# 判官校准有效性：并主干 + `identity_state` 跨层一致性（2026-09-16 快照）

分支 `codex/judge-calibration-validity`，工作树 `/Users/a77/fwp-wt-judge-calibration-validity`，HEAD `26f18e99`。
**未合 main、未部署、未调真实判官。** 本文是决策与证据快照，在途状态见 `inflight/codex-judge-calibration-validity.md`。

## 1. 两次合并

实施提交 `7117125e`（代码）/ `445058d7`（文档）落在旧基线上，期间主干两次前进：

| 合并提交 | 并入 | 说明 |
|---|---|---|
| `ffb0d281` | `gitea/main@c29a6401` | 两处内容冲突，见下 |
| `26f18e99` | `gitea/main@d433b907` | 他人 L2 归档质量改动 20 文件，无冲突 |

相对 `d433b907` 的净差：25 文件、3721 insertions、391 deletions。
`gitea_pr.py conflict-check --base gitea/main` → `{"clean": true, "conflicts": []}`。

## 2. 冲突解法：两边意图都保留

冲突在 `intelligence/services/llm_refine.py` 与 `intelligence/services/grok_cli_judge.py`。
主干新增的是**token 计费**（判官成本记账），本枝新增的是**调用身份证据**（谁应答的）。两者都写 `LLMCallRecord`：

- `LLMCallRecord` 同时保留身份/溯源字段与 `input_tokens` / `output_tokens` / `usage_source` / `purpose`。注释写明：`None` 表示**未上报**而不是 0；`purpose` 与 `phase` 互相独立。
- 删掉 `_call_record_snapshot`，统一成 `_record_to_dict(record)`：`asdict` 后丢掉空 `reason` 与四个 `None` 用量字段。`records_for_call()` 与 `summary()` 共用同一投影——**两个读取出口不能各自漂移**，并加断言钉住 `summary()["records"] == [record]`。
- `_record_llm_call(...)` 合并两边签名（`attempt=` 与三个用量参数），并注入 `purpose=_CALL_PURPOSE.get()`；无用量时强制 `usage_source=None`，不猜。
- `_post_chat`（HTTP）与 `_complete_cli_judge`（CLI）都带 `attempt=attempt` 记账。
- 删掉 `GrokCliResponse`，其身份元数据并入 `GrokCliText(..., metadata=payload)`，新增 `reported_model` / `request_id` / `response_id`。保留 `str` 子类契约（`complete()` 三元组、`json.loads(content)`、返回裸 str 的测试替身全不变）。

**没有新开第二本账本**：一个 turn 的花费与溯源在同一条记录上对账。

## 3. P1：`identity_state` 跨层一致性

移交单里唯一成立的待办——三种取值在服务层与评测层各写各的裸字面量，没有一致性断言。

- 新增 `intelligence/call_identity.py`（无依赖）：`IDENTITY_NOT_CALLED` / `IDENTITY_UNREPORTED` / `IDENTITY_REPORTED`。
- 接入 `llm_refine.py`（6 处）、`intelligence/eval/judge_validity.py`（4 处）、`scripts/run_quality_ablation.py`（2 处），消除跨层裸字面量。不在 eval 侧建第二套常量。
- 新增 `intelligence/tests/test_call_identity_contract.py`：钉住取值稳定与未调用默认；身份记录被资格门消费（writer / judge / calibration × reported / unreported）；非 `reported`（含 `not_called`、`unreported`、拼错值、`None`）一律不合格；HTTP 与 CLI 两条传输下，身份+计费在两个读取出口一致且 JSON 往返稳定。

定位是**防漂移**：没有证据表明它此前已放行过未知身份。

自测缺陷更正：初版把 CLI 用例接到只处理 HTTP 的 `_post_chat`，4 项失败。这是测试 bug，改测试入口，**没有动生产路由**。

## 4. 本轮验收读数（全部对 `26f18e99`）

解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

| 叶子 | 命令 | 读数 |
|---|---|---|
| python 全量 | `pytest -q` | **11359 passed / 0 failed / 83 skipped / 2 xfailed**，900.96 s，exit 0 |
| python 定向 | 10 个相关测试文件 | **270 passed**，6.95 s |
| ruff | `ruff check .` | exit 0 |
| frontend | `pnpm lint` / `typecheck` / `test` / `build` | 四步 exit 0，vitest **107 passed**（8 文件）|
| e2e | `pnpm test:e2e` | **34 passed / 2 skipped**，1.7 m，exit 0 |
| registry | 两个 check + 两个 `--check` + crosswalk | 五项 exit 0（61 个 SKILL.md）|

收据：全量 `~/.finance-runtime/test-receipts/20260916T152203Z-26f18e99.json`、定向 `20260916T151400Z-26f18e99.json`，
`check_test_receipt.py --expect-revision 26f18e99` 两份均七项全过（干净树、解释器与依赖指纹一致）。
pre-commit 全绿（detect-private-key、large-files、check-merge-conflict、ruff、工作区事实、layer-audit ERROR 0、path-literals 无新增、unread-fields）。

**历史读数不迁移**：`7117125e` 时点的 9766P 与四叶全绿属于旧代码态，本文不复用。

## 5. 新增门的承重验证（变异）

对新写的跨层一致性测试做两次反证，各自独立进程，跑完工作树仍干净：

| 改坏的地方 | 预期 | 实际 |
|---|---|---|
| 服务层把 `IDENTITY_UNREPORTED` 误标成 `"reported"` | 未上报用例转红 | 3 failed（writer / judge / calibration）|
| 评测层把 `IDENTITY_REPORTED` 拼成 `"reported-typo"` | 已上报用例不再合格 | 3 failed（同三角色）|

还原后 270 项全绿。这证明该测试对这两类反例承重，不宣称它拦得住全部变体。

## 6. 坑

- `intelligence/webapp/e2e/research-evolution-binding.spec.ts` 里硬编码 `RE06_E2E_URL ?? "http://127.0.0.1:8794"`，**端口与 URL 没联动**：只改 `RE06_E2E_PORT`（如 18894）会让该用例连 8794 被拒（`net::ERR_CONNECTION_REFUSED`）。首跑 36 例 1 红即此，带 `RE06_E2E_URL` 重跑全绿——是夹具缺陷，不是代码缺陷。
- 本工作树没有 `.venv-workbench`（在主树），跑 e2e 必须显式 `WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，否则 webServer 在测试起来之前就死。

## 7. 边界（与合并前必读）

- **没调过真实判官**：全部走假传输与内存夹具，零付费调用。「门会拦」已证，「真实模型分差」未测。
- 结论只覆盖 legacy `intelligence.cli ask --compose`（引擎 B），**不代表 Workbench Episode**；已登记在 `docs/agent-product-door.md`。
- `decision=callable` 只表示越过当次判官噪声门，不是合并授权。
- 判官身份取本次响应的结构化字段，只支持「按对端声明相同/不同」的审计强度，不等于已认证真实模型。
- 未改生产判官准入、未改时间长河写入、未部署。合入 main 需用户确认。
