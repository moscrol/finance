# Runtime 恢复与交付收口

## 这个分支做什么
收口 PR #843 的流式完成边界与失败/取消交付合同；不合并、不部署、不启动 K3 续审。

## 决策与被否方案
- 流 EOF/`[DONE]` 无完成原因记 `missing_finish_reason`，保留内容/usage但拒绝工具和终稿；不把 EOF 当 stop，也不暗中换 provider。
- 失败/取消以同 run、会话、助手消息且终态一致的持久化 `message.error` 为凭据；不等不合作 worker，不靠时间宽限猜成功。
- 兼容事件顶层 `status` 与 `payload.message.status`；损坏会话/畸形 payload 不算交付，不放宽为“普通 run”。
- 固定候选不改；修复提交后用 `git archive` 导出只读候选，旧候选和历史收据保留。

## 当前状态
代码 `e7e12a189`，作者树干净。**#69 执行（09-22 夜）：head 已推到远端**（原远端 `a9a112dfb`，1 提交含代码，旧 head 的收据与 K3 候选声明失效，PR 评论已留）。本 PR 是三层栈底层：#843 → #864（入口身份）→ #865（费用对账），按序合、不跳层；#865 head 已前向 main，四叶收据绑在它上面。
新只读候选：`~/.finance-runtime/reviews/runtime-pr843-k3-20260922-followup-01/host-qc-01/candidate-e7e12a189`。
K3 独立审查仍 `BLOCKED`：此前 429 `credit_exhausted_5h`，无报告、无签字；宿主 QC 不能替代。

## 已验证
候选宿主 QC：边界/API `216 passed`，相关 runtime `231 passed`，快照/恢复 `542 passed`；均 exit 0、model_requests=0。
作者侧另有取消/草稿 `94 passed`、前端全量 `112 passed`、Ruff、lint、typecheck、build、`git diff --check` 通过。
提交时 pre-commit 全部通过；导出候选 6118 tracked 文件逐个 Git blob 校验并设只读。
收据目录：`~/.finance-runtime/reviews/runtime-pr843-k3-20260922-followup-01/host-qc-01/`。

## 未验证 / 已知边界
未获得新的独立 K3 终稿，不能判 PASS；历史 #833 finding 未替代。未验最新 main 组合（顶层 #865 的四叶代之）、跨进程续跑 driver/exactly-once、checkpoint 后私有现场。用户绑定与未知效果/费用对账已由 #864/#865 补上。
宿主只读 QC 的 OS 沙箱覆盖测试子进程，不能宣称宿主控制器全进程隔离。

## 下一步
保持 PR WIP 直到用户确认；确认后按 #843 → #864 → #865 顺序合，每合一张在 main tip 复跑 python 叶。若获新模型授权，在新候选和新输出目录独立审查。

## 踩过的坑
baseline 的 EOF 工具派发和失败早于消息事件均可复现，属于既有合同缺口，不是本 PR 新回归。`baseline-probes` 曾误标候选树，已保留并标 INVALID，不得引用。
本 inflight 的 e7e12a189 真值段在作者树里躺了一天没提交，交接靶子指向的是 9fbcc9196 旧态；#69 执行方代为提交。
