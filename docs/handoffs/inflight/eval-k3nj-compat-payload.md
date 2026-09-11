# eval/k3nj-compat-payload 在途交接

## 这个分支做什么

k3nj 臂：能力基线的「kimi-k3 × 无独立判官 × 检索语义闸关」对照臂，30 题全量首跑。车道运行时目录 `~/.finance-runtime/capability-benchmark-00-k3nj/`（sidecar 8814 + preflight + 编排脚本）；被测树是本 worktree（fwp-wt-k3nj-00）。背景与被否方案全量见 `docs/handoffs/2026-09-11-k3nj-arm.md`。

## 决策与被否方案

- 选了开新臂全量；否了给 00 臂（gpt-5.6）中途换/关判官——判官在被测环路里（semantic verifier 边审边修），混臂读数不可比。
- 选了撤独立判官（unset LLM_JUDGE_*，回落主模型自审，receipt 记 correlated_judge=True）；否了「判官全关」——verifier 在 api/app.py 装配层硬接线，配置层无此开关。
- 选了移植 LLM_COMPAT_PAYLOAD shim（c423c8bd，自 e480e6c7 快照逐字节，未设 env 零行为变化）；否了 LLM_API_KEY 改走 OPENAI key 路（推理模式跑偏、辅助调用仍留坏路、池容量未证）；否了改共享 00 树（8813 provenance 会炸）；否了直接用 e480 快照树（与 00 代码差未知）。
- 否了 LLM_THINKING=enabled：mirasim 路本来就收 thinking.disabled，enabled 反而让 kimi-k3 推理模式与 00 臂不对齐。

## 当前状态

已跑完（03:51 收工，rc=2）：28/30 completed 全真形状，judge 分布 repaired 19 / passed 5 / unavailable 7；chain-01/02 engine_missing=澄清闸过触发（见快照「更正」节，两臂同病）。tokens 4.93M in，零配额污染。事故件在 runs/attic-misconfig-20260911/（未入链）。**用户验收（09-11）：看过问答后判「关掉判官回答的也不错」——无独立判官臂质量获认可。**

## 已验证

- 400 根因（双钥双门禁，均实测）：mirasim key 路拒 temperature 字段（只认摘除）；OPENAI key 路拒 thinking.disabled。探针用 OPENAI key 且不带这两字段，两种 400 都探不出。
- shim 冒烟（摘帽/他模型惰性/未设 env 零变化）+ llm_refine 相关 27 单测绿；preflight-k3nj 四查 GO。
- provenance：372d047c→6bea3197 的 services/runtime/api 零改动；k3nj 树=6bea3197+shim。

## 未验证 / 已知边界

- 本臂 judge=自审，与 00 臂 grok 独立判官门槛不同：通过率不可直接比，只能比形状/降级率。
- 自审 unavailable 7 题（多集中在隐藏题）读数偏弱，验卷按合同标明，不与完整复核题混算。

## 下一步

- **收口已完成**：终件入仓 intelligence/eval/runs/，验收文 docs/verification/2026-09-11-capability-benchmark-00-k3nj.md（含判官口径边界：已测=自审在环，连自审也撤是未测形态）。
- 剩下：两臂人工评审 + aggregate（00 臂评审也没做，建议同尺度同期）。
- 00 臂 7 题 resume 与本臂无关；grok 充值用户顺延至下周三，若独立判官终弃则 00 尾题价值降级为存档。

## 踩过的坑

- bash 3.2 + UTF-8 locale：`$VAR` 紧跟多字节字符会把首字节吞进变量名，set -u 下报张冠李戴的 unbound variable。一律 `${VAR}`。00 臂 preflight-00.sh 有两处同款未修。
