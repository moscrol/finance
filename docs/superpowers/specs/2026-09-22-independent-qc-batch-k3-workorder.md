# 2026-09-22 独立 QC 批（K3 / GLM 可替换通道）工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
本单是**服务单**：为 #60、#62、#65、#66、#67、#69、#70、#71、#72、#73、#74 各出一份第二方 Spec + Quality 结论。各单把候选（PR 号 + head SHA + 证据目录）挂到本单的队列文件，本单按队列跑。**并发 ≤ 2**，一次只审一个候选的一个轴。

## 当前模型授权（2026-09-23 更新）

用户纠正：“k3不行的时候，就用glm，不要太死板，都可以做写手。”K3 / GLM 是可替换的执行模型，不是任务资格本身；写手和本单审查均可在现有已配置通道间切换。09-22“只有K3”仅是当时可用性事实，不是永久禁用GLM的规则。

切换记录实际模型、端点、预算与新证据根，失败原件保留；独立会话、作者/审查分账、真实探针与终稿标准不变。不自动改生产配置，不用模型切换替旧失败补签，不因换模型无限重置预算。

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

- ❌ 不启用未授权模型或新账号；现有 K3 / GLM（含已配置智谱直连）可按上述授权替换。Codex 等其他审查通道仍不在本次授权内。
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

1. 开工三连；建批目录与 `QUEUE.md`；从 pi 认证或 launcher 既有钥匙串引用取钥匙，只驻内存。先做 `chat/completions` 小载荷与实际工具往返，记录状态/耗时；K3不可用时选已配置GLM，不仅等待原网关恢复。
2. 取队首候选：为审查者建**独占 detached 检出**（绝对路径写进 prompt；同一拥有者已锁定的干净只读候选可复用），复制 pi-config；有需要才用模型专属适配，私有监听避开8780–8830。K3剥temperature的要求不套到GLM。
3. 会话一 explore（只读，产出探针文件）→ 会话二 execute（跑探针 + 作者测试，分开记账）→ 会话三 report（只写结论）。任一会话零终稿即记 `BLOCKED_*`，不续跑后阶段补签；同一路由不连续重试同一候选超过2次。授权的K3/GLM切换另开证据根、先冻结有限预算，不继承旧批PASS资格。
4. 结论评论到 PR；`report.json` 落盘；更新 `QUEUE.md` 状态。
5. 批结束：批级读数 README；INDEX #75 行。

## 验收

- [ ] 每个已审候选有 `spec/`、`quality/`、`report.json`、`probes/` 四件，且 `report.json.requests` 与 shim 日志请求数一致。
- [ ] 阳性对照：往任一候选的探针集里塞一条必红探针（断言 1 == 2），会话二必须报红并进 report 的 `probe_bug` 分类；证明审查装置真在跑。
- [ ] 无一条结论由额度 / 网关失败改写而来（`BLOCKED_*` 单列）。
- [ ] 每个候选 PR 页有评论，含「分开记账」两组数。
- [ ] 批级读数 README 落盘。

## 红线

- 并发 ≤ 2；批前与每候选前验证所选模型通道。触429/400先停失败路由并记账，不用换账号绕额度；K3传输不可用可按现授权换GLM，模型身份与失败账本不得混写。
- 审查者检出独占、只读；不给它主检出树或任何有未提交改动的树。
- 不跑真实金融题；不动 8792；不重启网关。
- 只用 pathspec 提交产物；不写明文密钥；凭据只从 pi 认证、launcher 既有钥匙串引用或同一 `client-keys.env` 取，不复制到审查者工具环境。
