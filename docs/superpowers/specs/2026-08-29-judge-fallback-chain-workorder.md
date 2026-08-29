# 2026-08-29 语义判官备链工单

> 来源：rejudge 积压清账归因（台账 2026-08-29 22:15 段升格建议）——判官不可用
> 是慢性病（08-19..28 每日都有），95.5% overturn 首次量化了宕机窗口的内容代价；
> 2026-08-28 grok 402 断供靠手工改 env 切 sol 救场（start-finance-workbench 注释
> 明言临时、留了回切备份）。状态：**已实现（同日收口，台账行 `R-20260829-03`，
> 分支 `fix/judge-fallback-chain`）**。增量 `R-20260830-01`（CLI 形态备胎；
> 激活形态订正为 sol 主 + grok 备）随本 PR。

## 设计（与在案红线的关系）

- `llm_refine.judge_provider_chain()` = 主判官（解析逻辑一字不动：grok-cli 优先
  于 `LLM_JUDGE_API_KEY` 优先于派生模型）+ 显式备胎。
- 备胎用**独立词表** `LLM_JUDGE_FALLBACK_API_KEY` / `_BASE_URL` / `_MODEL`——
  不复用 `LLM_JUDGE_MODEL`（CLI 主判官历史部署用它命名 grok 模型，共用会互踩）。
- **红线不变**：链上永不自动追加合成主链 provider（`judge_provider` docstring
  在案的「不静默退回相关自审」）；只配备胎不配主 = 未接线（空链）；同端点同
  模型的备胎去重。
- verifier 槽位轮转：attempt 0 走主判官，attempt 1+ 走备胎（`MAX_SEMANTIC_
  JUDGE_ATTEMPTS=3` 不变，不加槽）；主判官**放弃**（不可重试/重试额度尽）且
  下一槽换人且窗口未烧穿时放行换人重试；释放安全账（monotonic_release_safe）
  跨人如实累计，不因换人清零。链耗尽仍如实 unavailable。
- 观测：哪位判官服务了本轮由既有 LLM 调用台账逐 attempt 记 provider 名
  （judge-fallback 独立名字可查），零 schema 新增。

## 激活手册（生产 env；形态已按用户拍板更新 2026-08-30）

**用户拍板：sol 长期当主判官，grok（2026-09-02 额度恢复）以备胎身份回归**
——不是原 env 注释里的「切回 grok」。为此补了 CLI 形态备胎
（`R-20260830-01`：`LLM_JUDGE_FALLBACK_BACKEND=grok-cli`，别名同主判官，
显式 backend 优先于 FALLBACK_API_KEY；二进制沿用机器级 GROK_BIN）。

09-02 激活时 `~/.local/bin/start-finance-workbench` 判官段改为：

```bash
export LLM_JUDGE_API_KEY=<现值不动>              # sol 主，三行原样保留
export LLM_JUDGE_BASE_URL="https://x.ailzd.com/v1"
export LLM_JUDGE_MODEL="gpt-5.6-sol"
export LLM_JUDGE_FALLBACK_BACKEND="grok-cli"     # grok 备，新增两行
export LLM_JUDGE_FALLBACK_MODEL="grok-4.6"
export LLM_JUDGE_GROK_BIN="/Users/a77/.grok/bin/grok"   # 机器级二进制路径
# 注意：LLM_JUDGE_BACKEND（无 FALLBACK）三行保持注释——取消注释会把 grok
# 抬成主判官，与拍板形态相反。
```

然后切流当日 main（顺带带上 #514/#515/#516）+ `launchctl kickstart -k
gui/$UID/com.a77.finance-workbench`。当前 sol 单主配置**不改也能继续跑**
（链退化为单主，行为与改动前一致）；已知弱点备忘照旧：sol 与写手兜底
terra 同家族同中转，GLM 主链正常时不受影响——grok 备胎上线后该弱点在
判官侧被对冲（中转挂时 grok CLI 接管）。

## 判据

离线（实施与台账行同 PR，全过）：主 402 → 备胎接管（observed=[主,备]，judge_
status=passed）；主健康 → 备胎零触碰；链耗尽 → 仍 unavailable；链构造五钉
（链头与单主解析全等 / 单主 / 只备不接线 / 同端点去重 / 合成永不自动入链）；
变异「枯死换人判定」精确杀救场钉；存量判官测试 174P 零回退。
live：激活后 30 天窗口内「主判官断供整段 judge_unavailable」不再出现（备胎
接管在调用台账留 `judge-fallback` 记录）。
