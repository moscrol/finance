# 在途交接 · 能力放大 / 工具线（spec/capability-amplification-output-gate）

## 这个分支做什么
按 knevo 的工具设计理念补工具面、契约自己做。spec `docs/superpowers/specs/2026-09-02-capability-amplification-output-gate-design.md`；展开 `docs/handoffs/2026-09-03-capability-line-session-handoff.md`。

## 决策与被否方案
- 切流分两次 / 否一次带全 / 重构与行为改动分开归因
- 弃权首句定性 / 否长度阈值 / 快答误判、长拒答漏判
- RAG：保活+菜单裁剪 / 否工具地板、否缩 asked / 9 工具不需要、2 RAG 装不下 90s
- 4 token：摘 prompt 里 task_id / 否放宽容差 / 模型用不上，摘后字节稳定
- 子代理先写 spec / 否现在做 / 结果须带证据、挂哪条 loop 看 P4

## 当前状态
#537–#546 全合；8792=`c88c81da5120`（含本线全部，另一会话切）。本线无未提交改动。`fwp-wt-rag-window` 有他人未提交 `rag_worker.py`，勿拆。

## 未验证 / 已知边界
- `web_search→web_fetch` 零 live 调用（茅台题库里有数）。
- 弃权率只有 08-27 回溯基线，无改后配对；消融壳走 legacy ask 不经 episode。
- 菜单口径不减思考时间，首轮 evidence_search 拿不到 30s。
- worker 保活效果样本 0。

## 下一步
1. 库里没有的题跑两臂：验 web 链路、判官是否删 public_web 句。
2. 源可用性进菜单（worker failed→藏 RAG）。
3. 翻 tool_hunger 遥测定加什么工具。
4. P2 第一步：判官删句结构化落盘。
5. 子代理 spec（dsh tool-subagent 形状、带证据、deep 档预算）。
待用户：P1 第二步 D 组 8 道、P4 sdk_glm、足迹分支认领。

## 踩过的坑
- 同一棵树两个 agent（12:26）：搬独立树、不代解。
- 变异恢复用 StrReplace/.bak，勿 `git checkout --`。
- 收据口径 `intelligence tests` 与整仓差 ~50 条。
- 首发切流探针冷 RAG 超时作废，复跑再采。

## 已验证
P0 live 两臂 1741.44 一手证据 model_finish；三次切流三项验证；菜单裁剪与 worker 计数在生产事件可见；各 PR 干净树全量 7524→7552P/5F。
