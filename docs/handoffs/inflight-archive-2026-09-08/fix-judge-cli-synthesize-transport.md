# fix/judge-cli-synthesize-transport（shadow 链 judge 的 cli:// 走 HTTP 必然 URLError）

## 这个分支做什么

修「judge zhipu URLError」（m/n/P1-①c 三轮 R5 同形，遗留排查项）的真根因：
生产 `LLM_JUDGE_BACKEND=grok-cli` 时 `judge_provider()` 返回 `base_url="cli://grok"`
的 CLI provider；`complete()` 有 `is_cli_judge_provider → _complete_cli_judge` 分支
（evidence_judge / episode_semantic_verifier 走它，一直正常），但 shadow 链
grounding judge（`ask_synthesis.py` judge_override 段）走的 `synthesize_messages()`
**没有**该分支——`cli://grok/chat/completions` 被当 HTTP URL 交给 urllib，发包前
即抛 `URLError(unknown url type: 'cli')`，重试同形 → 每轮 `judge_unavailable`。

「zhipu」是两轮误标：shadow 记录的 provider/model 字段填的是 composer 的
（`provider=composed.provider`），judge 从未调用 zhipu。

修法：`synthesize_messages` 的尝试循环内加 cli 分支，镜像 `complete()`——
`_complete_cli_judge` 拿内容，`max_chars` 超长走既有 `LLMOutputTooLong` 降级，
`finish_reason` 置 `"stop"`（CLI 无该语义，正常退出且有输出即完整）。
`synthesize_messages_stream` 刻意不动：judge 均为非流式调用。

## 当前状态

代码完成（`llm_refine.py` +cli 分支、`test_grok_cli_judge.py` +2 测试）。
目标测试 9P、ruff 绿；全量闸见 PR 描述。等用户确认合并。

## 验证判据（合并切码后）

R5 冻结题重放（对话入口）：shadow `status` 应离开 `judge_unavailable`——
judge 真实运行后要么 `accepted`（残差首次上场，公开稿尾段出现档位/集采双重性/
反证解读，名单行零增删），要么 `judge_rejected`（按 #397 fail-closed 回纯包，
但 failure_reason 不再是 URLError）。

## 未验证 / 已知边界

- 未用真实 grok 二进制端到端验证（单测 mock `complete_grok_cli`；live 验证
  属切码后 R5）。launchd 环境 `LLM_JUDGE_GROK_BIN` 已钉，二进制存在。
- n 轮观察「旧入口 `_run_ask` 的 Grounded Presenter 也报 URLError」大概率同根因
  （同一 judge 调用形状），本修复应一并治好，但该路径未单独重放。
- CLI 分支不吃 `temperature/max_tokens`（CLI 侧无对应旋钮），与 `complete()`
  的既有行为一致。

## 踩过的坑

- 定位时别信 shadow 里的 provider 字段——它是 composer 的。判 judge 用哪个
  provider 要看 `judge_provider()` 解析 + 生产启动器 env
  （`~/.local/bin/start-finance-workbench`）。
- 确定性复现不用等生产：cli scheme 在 urlopen 发包前就失败，
  `provider_override` + `synthesize_messages` 本地即可逐字节复现失败 reason。

## 工具沉淀盘点

无新脚本。「认不出来就 fail closed」反向应用：这次是**能力在而路由缺**——
同一 provider 在 A 入口（complete）有 transport 分支、B 入口（synthesize）没有，
仪表只报 B 入口的降级 reason，看不出是路由缺口。可迁移判据：加新 transport 时
grep 所有「把 provider 交给 HTTP 客户端」的入口，逐个补分支或统一收口。
