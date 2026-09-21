# feat/adaptive-research-loop

## 这个分支做什么
模型按证据选视角、同会话修订与公开保真。树 `~/finance-worktrees/adaptive-research-loop`。

## 决策与被否方案
- 修稿/bindings 变更即重核；来不及则旧稿+partial+公开提示。否修改进度门：进展/预算与公开保真正交。
- 股票后缀闸 `d9e2875c0` 已修：精确比较拒裸六位码并提示后缀，否猜交易所；contains 保持可用。
- 残片不做正文手术：兼类连接词会误剥，否改已接受句；复现频率先量化。
- K3 同一请求 200/400/200，不能归因确定性格式错误；否放宽全局 400 重试。并非所有变体都混合，不能把小样本定为稳定50%故障率。
- 详细决定、原件纠正、历史指针见 `docs/handoffs/2026-09-21-adaptive-forward-830-closeout.md`。

## 当前状态
固定 `be66029342bfe2c57e62c78be3a6c502fdb73543` 已前向合入 #830 及后来 main=c097d712f；后续仅文档。11:06Z fetch 无新漂移，后续看 `worktree_board.py --this`。最新门禁/临时目录清理见 `docs/handoffs/2026-09-21-adaptive-forward-c097-gates.md`。未push/PR/合回main/部署。

## 已验证
以下只签 be6602934，不移绑文档tip：
- Python全量12698P/87S/2X/17W、exit0，Ruff过；原c07收据保留不移签。
- 收据 `~/.finance-runtime/test-receipts/20260921T110550Z-be660293.json`，精确revision/依赖/干净代码/基座漂移0均校验通过。
- 证据根 `~/.finance-runtime/adaptive-forward-c097-20260921/`：`frontend-be6602934/frontend.json` 六步全过，110P、E2E34P/2S；首尾同SHA、dirty=false、identity_stable/complete=true。
- `local-checks.json`：registry四项+台账对账exit0；仅本仓在场，23个跨仓skill跳过；台账反向98行warning。不声称跨三仓或零警告。

## 未验证 / 已知边界
“无工具修复+自报partial”自然模型仍未闭合；GLM修复版三次均completed，K3此前受间歇400阻断。证据 `~/.finance-runtime/k3-gateway-intermittent-400-20260921/README.md`（抓包代理/拒绝载荷/重放表）。缺tool_call id有合成补位，content泄漏推理不是本轮已修。#830合流后未重跑真模型；离线和无密钥E2E不证明金融质量。独立Spec/Quality未做。

## 下一步
需要闭目标格时，先获稳定K3/第二模型及live授权再自然触发，不刷次数。推送/PR/合main/部署待明确授权；最终待合SHA须重新绑定工程门禁，不能沿用旧收据冒签。

## 踩过的坑
必须显式cd目标树，解释器用 `~/finance-workspace-private/.venv-workbench/bin/python`；本树无venv。E2E用现有 `scripts/run_frontend_gate.py` 自动传解释器和端口，避免宿主Python缺uvicorn。前序主树b4a35fa零执行收据作废，不修无关主树文件。原24KB交接在 `git show cb47cc3b6:docs/handoffs/inflight/feat-adaptive-research-loop.md`，含过期状态，只作历史。
