# 2026-08-16 观点题核验预算降级回归（分诊先行，未确认根因）

roadmap_ref: 另案（P5 质量战线；观点题四层 `2026-08-16-outlook-question-empty-delivery.md` 的直接后续，其 §4 回归条款当前在生产不成立）

> 本文件是主 checkout（`docs/dsh-absorption-spec`）上的未跟踪交接，**不要在本分支提交**。
> 执行 agent 把权威版带进自己的分诊/修复分支（从 `gitea/main` 拉）。

一句话：四层修复合入并部署（8792=`773b3d7e`）后，观点题不再假绿空壳，但也交付不出判断正文——核验/修复阶段以 ~151-159s 的高度一致时长撞预算，落 `evidence_gap_fallback` 边界句降级。失败形状从「假 completed + 剥光」迁移成「诚实 degraded + 无正文」。预注册回归标准「判断句存活」当前不成立。**先分诊后修，本文件不预设根因。**

证据等级：**[实测]** = 2026-08-16 13:0x-13:3x 读过 run 产物 / 健康端点 / 进程现场。

## 1. 症状 [实测]

均为长尾 A/B off 臂（= 生产 8792 `773b3d7e`，`ASK_LONGTAIL_BASELINE` 默认 off，用户 `longtail-ab-0816`）：

| 槽位 | run（`~/.local/share/finance-workbench/users/longtail-ab-0816/runs/`） | 环境 | 时长 | 结果 |
|---|---|---|---|---|
| off:L01（原题「基于8.15的行情现状，你认为周一的机会在哪」） | `run_20260816_131941_597875` | **ready 绿、rag_worker=true** | 153.9s | degraded；答案 134 字纯边界句：「已取得 60 条证据，但未完成核验绑定，暂不能引用」 |
| off:L05（超纯应材估值） | 13:33 收（progress.jsonl） | 同上 | 159.2s | degraded 同形 |
| off:L01/L02/L03/L05（首轮，已清出收据） | `run_20260816_1251xx`-`1302xx` 四个 | rag_worker 挂死期 | 151.0-153.0s | degraded 同形 |
| off:L04（立新能源怎么看）反例 | `run_20260816_125920_927309` | 挂死期 | 37.0s | **completed** |

关键交叉验证：**rag_worker 修好（13:08 kickstart，ready 绿三读数过）之后 L01 原样复现**——排除环境因，坐实代码路径。

对照修复前（`437cd5e9`，当日上午 UI 直跑）：`run_20260816_102941_554059` / `run_20260816_103318_230845` 是 `completed`、0 degrade、判断句被剥的空壳（outlook handoff §1）。即：第 4 层诚实闸**按设计生效了**（degrades=「证据或语义核验未完全通过，已按证据边界降级」、report.status=partial，这部分不是回归），但层 0-3 想要的「判断句存活」没有发生，丢失点从 judge 剥句移到了「核验未完成」。

## 2. 已排除 / 已知线索 [实测]

- 非 rag_worker：ready 绿后复现（上表）。
- 非长尾开关：off 臂即默认关。
- 时长特征：~151-159s 高度一致 → 预算常量嫌疑。`continuous-episode.json` 里有 `time_budget_injected=True`、`timeout_configured=75.0`、`timeout_asked≈30.0`。launcher 侧常量：`WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS=300`、`LLM_TIMEOUT=180`、`ASK_TOOL_BATCH_TIMEOUT=60`、verification_reserve=min(40, T/3)（`research_contract.py:356` 一带）。151s 对应哪个组合是**分诊问题**，不要拿 2×75 当结论写。
- trace.jsonl 阶段序列：`verification running`（「正在核验证据绑定与回答完整性」）→ `repair running`（「核验发现关键缺口，正在定向补证」）→ `finalizing`（「核验已完成，正在生成可公开回答」）→ 公开答案却是边界兜底。检索侧正常（5 次 research 各 ~1s，60 条证据入账）。
- 嫌疑面（并列，未验证）：#79 比较集绑定把同题整段观察扩进绑定 → judge payload 变大变慢；#72 判断槽走 model_reasoning 后 judge/repair 轮次变多；repair「定向补证」循环耗尽预算后与 `evidence_gap_fallback` 兜底路径的交互。

## 3. 分诊指令（trace-first，M1 形制）

素材（只读，全部已落盘，**不需要占 8792 重跑**，可即刻开工）：

- 主样本：`run_20260816_131941_597875/{trace.jsonl,continuous-episode.json,report.json,answer.md,stream.jsonl}`
- 反例对照：`run_20260816_125920_927309`（L04，37s completed）
- 修复前对照：`users/default/runs/run_20260816_102941_554059` / `run_20260816_103318_230845`

要回答的问题：

1. 首个分叉 step：150s 烧在哪个 span（judge LLM 调了几轮、每轮多长；repair 补证跑了几轮）。
2. `773b3d7e` 相对 `437cd5e9` 在该 span 上的行为差异归到哪一刀（#72 路由 / #75 标记 / #79 绑定扩张），或都不是。
3. 「未完成核验绑定」的兜底句由哪条分支产出，与 #327 partial 镜像、第 4 层 `uncheckable_judgment_empty` 的关系（预期行为 vs 意外交互）。

输出：Evidence→Finding、PRIMARY/SECONDARY、fix_type，报告形制照 `docs/verification/2026-08-15-b-group-evidence-bound-zero.md`（M1 先例）。未确认单一根因就写 `ROOT_CAUSE_NOT_CONFIRMED`，不许为了收口硬钉。

## 4. 修复的预注册验收（引用，不重钉）

outlook handoff §4 全套原样适用：原题回归（判断句存活、evidence_bound_rate 不降）、10 题修前/修后对照（另有执行窗交接 `2026-08-16-outlook-ten-question-window.md`）、假数字反向护栏、`_CLAIM_POLICY` 七闸单测不动。追加一条：

- 修后原题在生产预算内完成核验（判断正文存活且 status=completed）。**不许靠单纯调大预算糊**——若分诊结论确是预算不足，调预算须照 launcher 2026-08-08 换型先例给延迟实测依据，并说明对全路由的影响面。

## 5. 与既有账的关系

- 不并入 B 组三形状编号；与 outlook handoff §5 说的「第四形状」（draft 满、repair 剥、uncheckable 放行）也不同——本形状是「核验未完成 → 兜底降级」。若要入账作新形状，另开观测台 PR，不覆盖既有编号。
- 长尾 15 题窗（正在跑）会在 outlook 档系统性量出本现象；其收据可直接引为本案证据，但**不要等窗收口才开分诊**——素材已够。

## 6. 边界 / 不做什么

- 分诊阶段只读产物；长尾窗收口前不在 8792 跑任何 live 重放。
- 不动 8792 配置与部署；修在 main，上生产走部署窗（`2026-08-16-deploy-window-773b3d7e.md`）。
- 不放宽 5pp；不动 `_CLAIM_POLICY`；不改 `ASK_JUDGE_RECHECK` 默认 off。
- 不在 `docs/dsh-absorption-spec` 提交本文件。
