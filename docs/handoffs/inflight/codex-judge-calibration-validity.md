# codex/judge-calibration-validity

## 这个分支做什么

实施 `docs/superpowers/plans/2026-09-14-judge-calibration-validity.md`：让主评、补评、完整重评**只能用同一有效评审批次**的评分与校准出实验结论。未知身份或不兼容的记录保留、可读、可探索，但不产生 `callable`。

工作树 `/Users/a77/fwp-wt-judge-calibration-validity`（不是 `.claude/worktrees/` 下那棵）。基线 `gitea/main@1fef3d276d0e`，未合并。

## 当前状态

Task 1–5 代码与验收全部完成。提交链：

| revision | 内容 |
|---|---|
| `64c8f90c` / `c9ac0f42` | 方案与四处指针订正（本轮之前） |
| `09c3a8b5` | Task 1–4：v2 manifest、逐次调用证据、唯一资格门、双模式重评 |
| `184eac97` | 资格门反向钉住（身份 / 校准绑定 / 噪声三层） |
| `7117125e` | 覆盖率台账收口到 `batch_coverage`；失败响应保留 `request_id` |
| `87845e09` | 产品门登记 legacy 评测边界；本交接 |
| `7074f4cc` | 计划状态改为「Task 1–5 已实施并验收」，20 项清单勾选 |

## 已验证（读数与条件）

- **全量 9766 passed / 0 failed / 77 skipped / 2 xfailed**，344 s，`ruff check .` 全绿。收据 `~/.finance-runtime/test-receipts/20260914T152057Z-7117125e.json`，`check_test_receipt.py --expect-revision 7117125e` 七项全过（**干净树**、解释器/依赖指纹一致）。
- **Task 5 反向证明**：逐个拆掉四道门，每次只改一处、跑对应验收、`git checkout --` 还原并校验树干净——

  | 拆掉的门 | 对应验收 | 拆后读数 |
  |---|---|---|
  | 判官身份（`allowed_reported_models`） | V1 | 1 failed, 3 passed |
  | 源 writer 独立性（`family in writer_families`） | V4 | 1 failed |
  | 校准绑定哈希（`batch_id`/`judge_spec_sha256`） | V6 | 1 failed, 5 passed |
  | 非有限数检查（`_number` 三连） | V8 | 15 failed |

  还原后 85 项全绿。V1/V6 只红了部分参数化分支，是因为其余变体被相邻检查先接住——这证明**该门对它那一类反例承重**，不宣称它独自拦住全部变体。
- **覆盖率分叉是实测的，不是推演**：把 rejudge 的行内重算副本改回去，两个模式的同源断言都变红（人读报告「已评分=4」/ JSON 收据 `scored=3`）。
- `graph_audit.py` exit 0，62 节点 / 115 断言无漂移；本轮新增行的 6 个符号都被识别为 `@codex/judge-calibration-validity` 分支待合。
- `registry-check` 两步 exit 0（60 个 SKILL.md 可解析、注册表与源一致）。

## 未验证 / 已知边界

- **没调过真实判官**。全部验收走假传输（fake HTTP / CLI 子进程 / 流式）与内存夹具，零付费调用。「门会拦」已证，「真实模型分差如何」未测。
- **不给历史收据追认身份**。旧 v1 收据只可读、可探索重评，永远拿不回 `callable`。
- **结论只覆盖 legacy CLI ask（引擎 B）**：runner 经 `run_ask` 调 `intelligence.cli ask --compose`，不代表 Workbench Episode（引擎 A）。已登记在 `docs/agent-product-door.md` 新增小节。
- `decision=callable` 只表示越过**当次判官**的噪声门，不是合并授权，也不证明跨任务或未来效果。
- 判官身份取本次响应的结构化字段，只支持「按对端声明相同/不同」的审计强度，**不等于已认证真实模型**；CLI 无该字段记 unknown，不从自述或当前环境补齐。
- 本轮未重测生产库覆盖面，未改生产问答判官准入策略、未改时间长河写入。

## 下一步（合入前）

1. **frontend / e2e 两片叶子还没结论**。本枝 21 个改动文件里零个在 `intelligence/webapp/**`，但仓库规矩是四叶都要有读数：`cd intelligence/webapp && pnpm lint && pnpm typecheck && pnpm test && pnpm build`；e2e 记得把 venv 放进 PATH（`PATH=.venv-workbench/bin:$PATH pnpm test:e2e`），否则 playwright 会退回宿主 python 而没有 uvicorn。`data-quality-check` 按 paths 触发，本枝没碰那些路径，**不算缺结论**。
2. 合入 main 必须等用户确认；本计划不含合并授权。
3. 若要拿真实模型跑一轮消融：先按 `probe-shared-llm-gateway-before-a-batch` 预检网关（一次深 episode 能触发 75 分钟整模型冷却），再串行、逐题预检。

## 踩过的坑

- **上个会话被中断，留下零字节 `index.lock`**（`.git/worktrees/fwp-wt-judge-calibration-validity/index.lock`，22:45）。当时 `git add` 没落成，状态里文件仍是未暂存。确认无 git 进程后清掉即可——但先确认，别默认它陈旧。
- `git commit -- <paths> -m "msg"` 会把 `-m` 当 pathspec。正确顺序是 `git commit -m "msg" -- <paths>`。
- 覆盖率那处分叉的成因值得记：**一份台账、两个渲染出口**，行内那份用 `scored is True`、收据那份用 `_score_is_numeric`，平时读数一样，遇到 `scored=True` 但 `total` 非有限数才劈开。已收口成 `batch_coverage` 单点供给，并加了两个模式的同源断言防它长回来。
- `source_preflight` 已在源侧用 `manifest_denominator_mismatch` 拦住删行，所以「分母用 `len(answers)`」在 rejudge **不可达**——这条查证后没当缺陷记。
