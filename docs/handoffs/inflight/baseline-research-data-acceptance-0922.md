# A股研究数据链｜验收在途（baseline/research-data-acceptance-0922）

## 卡点
真实自然会话验收**未开始**：需用户给「期限 / 额度上限 / 独占根」才发题。本轮 0 模型调用、0 网络取数。

## 本轮做了什么
在**冻结候选** `6fb37a6e`（detached、clean，树见 `~/.finance-runtime/convergence-20260919/retention-repair/candidate-6fb37a6e/registry-pinned/finance-workspace-private`）上，
把上轮外审只留文字的两条公告线索固化成可复跑量具 `scripts/review_probes/check_disclosure_attribution_scope.py`（SHA `7c67c7ba…`）：

- **4P/4F**，两条控制 4/4 全过 → 失败是覆盖面缺口，不是检查器没开
- `深交所互动易显示本期没有公告[E2]`：独立来源句连引用被一起删（误删）
- `因此本期无任何披露文件`：完全漏检，status 仍 `completed`，不降级、不续修
  → 与立项要修的**失败形态②同类，只换措辞**
- `target_unchanged=true`，未改业务码、未加 xfail、未放宽判据

证据：`docs/verification/2026-09-22-research-data-acceptance/disclosure-attribution-scope-6fb37a6e.json`，提交 `0f7c41901`。

## 结论口径（三本账分开）
1. 工程绿：`6fb37a6e` 全量 12259P/87S 等读数不变，本轮未移签
2. 交付检查覆盖：`_ABSENCE` / `_ATTRIBUTED` 是**有限词表 + 归属白名单**（见 `research_delivery_checks.py:34,41`），
   非语义判断 → **不能充当验收判据**
3. 自然回答质量：仍 `not_passed`，真实会话 0

## 实盘壳（已备齐，待授权）
- 起法：`zsh scripts/launch_workbench_sidecar.sh <port> <repo> <users> <user>`；拒 8792/8793/8795/8799/8801
- 模型：GLM 云端 `open.bigmodel.cn`（builtin `glm-5.3-flash` / 主 `glm-5.3`），**与 57244 网关无关**（那是旧 sol 模型，当前无监听，不阻塞）
- 凭据：Keychain `finance-workbench-glm` 可读；env `FORESIGHT_BUILTIN_LLM_API_KEY`
- 题集：`~/.finance-runtime/research-data-readiness-20260918/probe_candidate_live.py` 第 22–23 行原题两道，每题**只首发一次**，不重采样挑绿
- 独占根：`~/.finance-runtime/reviews/research-data-acceptance-20260922-01`

## 下一步（二选一，需用户定）
- A｜先修两条线索再发题：省一次实盘窗口，但修的是词表，治标
- B｜直接实盘：看自然答案是否真落在词表外；结果无论好坏都留原件

## 红线
未 push、未开 PR、未合 main、未部署；8792 未动（PID 3095 存活未触碰），8907 未起。
主树 `/Users/a77/finance-workspace-private` 他人未提交改动未碰。
