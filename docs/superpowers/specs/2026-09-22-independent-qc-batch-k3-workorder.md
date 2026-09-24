# 2026-09-22 独立 QC 批（K3 通道）工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
本单是**服务单**：为 #60、#62、#65、#66、#67、#69、#70、#71、#72、#73、#74 各出一份第二方 Spec + Quality 结论。各单把候选（PR 号 + head SHA + 证据目录）挂到本单的队列文件，本单按队列跑。**并发 ≤ 2**，一次只审一个候选的一个轴。

## 背景与动机

- 仓规：代码 PR 合入前要有独立审查（第二方读源码或跑探针），作者自验不算 QC；`exit 0` ≠ 审查完成，有 REPORT / verdict 也须读正文。
- 09-22 独立 QC 的可用通道只有 K3（pi + 本机网关），Codex / 外部通道额度耗尽（`credit_exhausted_5h`，HTTP 429；#841 两次均无终稿；#847 桥接三会话 97 请求无批准）。09-12 起独立判官关闭，K3 自审是现状（记忆 `independent-qc-runs-on-k3-via-pi-not-codex`、`independent-judge-off-since-0912-k3-self-review`）。
- 09-22 ReAct trace 那次独立审查（`~/.finance-runtime/reviews/react-trace-k3-20260922/`）三轮才拿到终稿，三条可复用教训：**macOS 不允许沙箱嵌套**（参照的既有 runner 事件流里 bash 调用数是 0，那套分层从来没真正跑通——「有装置」不等于「装置能用」）；**给审查者绝对路径，别让它靠环境变量猜**（第 3 次尝试 16 次写入全被拒，因 bash 挂了读不到 `$REVIEW_WORK`）；**分段交付打败单次长跑**（会话一、二撞 600 秒零终稿；把探针沉淀成文件后会话三 530 秒收工）。代价约 102 次模型请求。
- K3 网关事实：拒收任何 `temperature`（400），需剥参 shim；K3 自审 71.8s 贴 75s 帽，重载荷 `judge_unavailable`；网关活性依赖载荷形状，探 `chat/completions` 不探 `/health`；批前查冷却（记忆 `live-batch-must-precheck-model-gateway-cooldown`、`probe-shared-llm-gateway-before-a-batch`、`gateway-liveness-is-payload-shape-dependent`）。**外审返空是阻塞不是无发现**（记忆 `empty-model-output-is-blocked-not-no-findings`）。
- **已定的形态决策**：审查者自造探针与作者既有测试**分开记账**；三轮分段（explore / execute / report）各自独立会话；审查结论只有 `PASS / PASS_WITH_LIMITS / CHANGES_REQUIRED / BLOCKED_<原因>`，额度失败不改写为审查结论；「超出主张范围、未裁决」的观察单列不冒充 PASS。

## 目标

1. 队列文件 `docs/verification/<日期>-independent-qc-batch/QUEUE.md`：每行「工单号 / PR / head SHA / 候选检出路径（绝对）/ 证据目录 / 主张清单来源 / 状态」。各单往里追加，本单只消费。
2. 每个候选一套三段会话产物：`spec/`（主张逐条 verified / not_verified / out_of_scope）、`quality/`（正确性缺陷：文件:行、触发输入、错误输出；无发现就写「无发现」不凑数）、`report.json`（结论、请求次数、耗时、是否触帽）。审查者自造探针文件落 `probes/`，可复跑。
3. 每个候选一条 PR 评论：结论 + 产物路径 + 「作者测试 N passed（分开记账）/ 审查探针 M passed」。
4. 批级读数：总请求数、每候选平均、触帽次数、被网关 400/429 中断次数；网关探针（批前 / 每候选前）读数落盘。

## 非目标（写死认领）

- ❌ 不用 Codex / 外部通道（额度已尽；恢复后另议）。
- ❌ 不替作者修缺陷；发现写进评论，由各单认领。
- ❌ 不给「额度失败 / 网关空回」补签结论；记 `BLOCKED_PROVIDER_*` 并回队列。
- ❌ 不跑自然金融质量（#76）；本单是工程 / 正确性审查。
- ❌ 不在生产 8792 上做任何事；不重启共享网关。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/.finance-runtime/reviews/react-trace-k3-20260922/`（`pi-config/`、`prompt-session-02.md`、`k3-session-01-explore` / `02-execute` / `03-report`、`k3-blocked-*` 四个失败目录） | 能用的 runner 形状、三段 prompt、四种装置失败各长什么样 |
| `~/.finance-runtime/reviews/research-data-acceptance-20260922-01/` 内 `k3_param_shim.py` | 剥 `temperature` 的 shim 与声明形状 |
| `~/agent-memory/10_knowledge/` 与 `~/.claude/projects/-Users-a77-finance-workspace-private/memory/` 里 `k3-*`、`*gateway*`、`independent-qc*` 记忆 | 网关坑与通道约束 |
| `scripts/agent_review/gate.py` | 仓内既有审查门（复用其结论枚举与产物形状） |
| `docs/workflows/acceptance-workflow.md` §1–2 | 「作者读数与审查读数分账」「翻转率」口径 |
| 各单 PR 描述的「主张清单」 | Spec 轴的输入；没有主张清单的候选退回作者补 |

## 步骤

1. 开工三连；建批目录与 `QUEUE.md`；`pi auth print-api-key` 与网关探针（一发 `chat/completions` 小载荷，记 HTTP 码与耗时），冷却中就等。
2. 取队首候选：为审查者建**独占 detached 检出**（绝对路径写进 prompt），复制 pi-config，剥参 shim 起在避开 8780–8830 的端口。
3. 会话一 explore（只读，产出探针文件）→ 会话二 execute（跑探针 + 作者测试，分开记账）→ 会话三 report（只写结论）。任一会话零终稿即记 `BLOCKED_*` 并换下一候选，不连续重试同一候选超过 2 次。
4. 结论评论到 PR；`report.json` 落盘；更新 `QUEUE.md` 状态。
5. 批结束：批级读数 README；INDEX #75 行。

## 验收

- [ ] 每个已审候选有 `spec/`、`quality/`、`report.json`、`probes/` 四件，且 `report.json.requests` 与 shim 日志请求数一致。
- [ ] 阳性对照：往任一候选的探针集里塞一条必红探针（断言 1 == 2），会话二必须报红并进 report 的 `probe_bug` 分类；证明审查装置真在跑。
- [ ] 无一条结论由额度 / 网关失败改写而来（`BLOCKED_*` 单列）。
- [ ] 每个候选 PR 页有评论，含「分开记账」两组数。
- [ ] 批级读数 README 落盘。

## 红线

- 并发 ≤ 2；批前与每候选前探网关；触 429 / 400 立刻停手记账，不换账号不换模型硬顶。
- 审查者检出独占、只读；不给它主检出树或任何有未提交改动的树。
- 不跑真实金融题；不动 8792；不重启网关。
- 只用 pathspec 提交产物；不写明文密钥；网关钥匙只从 `pi auth print-api-key` 或 launcher 同一 `client-keys.env` 取。
