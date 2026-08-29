# 2026-08-29 语义判官备链工单

> 来源：rejudge 积压清账归因（台账 2026-08-29 22:15 段升格建议）——判官不可用
> 是慢性病（08-19..28 每日都有），95.5% overturn 首次量化了宕机窗口的内容代价；
> 2026-08-28 grok 402 断供靠手工改 env 切 sol 救场（start-finance-workbench 注释
> 明言临时、留了回切备份）。状态：**已实现（同日收口，台账行 `R-20260829-03`，
> 分支 `fix/judge-fallback-chain`）**。

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

## 激活手册（生产 env，等 grok 额度恢复时执行）

`~/.local/bin/start-finance-workbench` 判官段改为：

```bash
export LLM_JUDGE_BACKEND="grok-cli"          # 取消注释（主判官回 grok）
export LLM_JUDGE_GROK_BIN="/Users/a77/.grok/bin/grok"
export LLM_JUDGE_MODEL="grok-4.6"
export LLM_JUDGE_FALLBACK_API_KEY=<现 LLM_JUDGE_API_KEY 的值>   # 现 sol 三行改名
export LLM_JUDGE_FALLBACK_BASE_URL="https://x.ailzd.com/v1"
export LLM_JUDGE_FALLBACK_MODEL="gpt-5.6-sol"
```

然后 `launchctl kickstart -k gui/$UID/com.a77.finance-workbench`。当前 sol 单主
配置**不改也能继续跑**（链退化为单主，行为与改动前一致）；已知弱点备忘照旧：
sol 与写手兜底 terra 同家族同中转，GLM 主链正常时不受影响。

## 判据

离线（实施与台账行同 PR，全过）：主 402 → 备胎接管（observed=[主,备]，judge_
status=passed）；主健康 → 备胎零触碰；链耗尽 → 仍 unavailable；链构造五钉
（链头与单主解析全等 / 单主 / 只备不接线 / 同端点去重 / 合成永不自动入链）；
变异「枯死换人判定」精确杀救场钉；存量判官测试 174P 零回退。
live：激活后 30 天窗口内「主判官断供整段 judge_unavailable」不再出现（备胎
接管在调用台账留 `judge-fallback` 记录）。
