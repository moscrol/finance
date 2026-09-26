# #76 L6 自然验收收尾与 #75 准入核对

## 结论与范围

**L6 NOT_PASSED；#75 独立终审未启动；PR #868 不具备合入批准。**

候选始终为 `31f1b40dd788d36c71da249d59fb769c50d7cd30`，首尾干净。live 前分支 head `cd520152f9bbf435de81d7b7f662bfa695eef26a` 含预检/审计脚本及测试，不能冒充 live 候选或完整门禁 revision。`7ad61a0d3..31f1b40dd` 仅 docs 差异；`31f1b40dd..cd520152f` 还新增两个 probe 脚本及一个测试文件，但未改产品运行代码。

本页取代预检文档的“尚未 live / 权重缺失”现态，不修改历史快照。原件根：`~/.finance-runtime/reviews/pr868-l6-natural-20260923-1455/`。本目录 `raw/` 是该根 `live-r2/` 中具名审计/执行文件的逐字节副本，不是第二次运行。大体量原始 Episode、events 与市场数据仍保留在私有证据根。

终态读 `raw/protocol-closure.json`：`AUDIT_COMPLETE_NOT_PASSED`，`can_execute=false`。原 `protocol.json` 的 `LIVE_EXECUTED_PENDING_AUDIT` 是执行结束时快照，原样保留；不可再据它发起请求。原 closure 的 `initial_submissions_per_question=1` 是额度，不是实发计数；实际 **Q1=1、Q2=1、Q3=0**，重发/续问均 0。

## 实际执行

BGE-M3 权重后来可离线加载，重新预检为 `PREFLIGHT_READY`；没有替换模型、降级检索、下载权重或干预其他任务。写手 `kimi-k3`，终稿判官 `llm` / `glm-5.3-flash`，检索判官 `auto`。隔离端口 19897/19898，私有 shim 转发本机 18788，不是生产路径。

| 题 | 唯一 run | 观测 | 结论 |
|---|---|---|---|
| Q1 寒武纪 | `run_20260923_142128_565528` | 415.16s；run completed，答案 partial；4 次工具调用；判官 unavailable；repair 超时无新稿 | `BLOCKED_JUDGE_UNAVAILABLE` |
| Q2 东阳光 | `run_20260923_142823_856635` | 107.45s；首轮及 repair 均 `LLMDeadlineExceeded`；0 工具请求/结果，无答稿 | `NOT_EXERCISED` |
| Q3 固态电池 | 无 | Q2 failed 后按协议停批，未提交 | `NOT_EXERCISED` |

三题的 quality_status 均为 NOT_PASSED。run completed 只代表任务结束，不代表答案或金融质量通过。

Q1 的 8 个 evidence 对照条目可绑定大盘事实、缺值及日期边界；不是 8 条独立数值条件。实际恢复稿写手为 `kimi-k3-eas`，sequence 27 / `finalization_recovery`；不是 repair 生成的新版本。两段确认/证伪框架没有本轮个股证据，不能当成已完成的可证伪数值条件。仍缺 `falsification_conditions`、`change_summary`、`track_quad_or_baseline`、`track_ttl`、`track_next_watch`。

Q1 的 `finance_query=parse_error` 不能证明寒武纪本地无数据；Q2 未发工具调用，不能评价本地数据存在性、finance_query 或板块比较能力。`supported_conditions_lost=[]` 也不能证明删句机制合格：本次无真实 repair 新稿，判官无有效逐句裁决。历史 Q3 的有证据条件被删反例仍为 NOT_PASSED，不由本批翻案。自然迟到判官回包未观测，严格模拟探针另账。

## 工装发现，不归咎产品

1. 原 shim 的 `response.read(65536)` 会积攒流式内容。`probes/probe_shim_streaming.py` 使用原 shim、两个本机假请求、0 模型请求复现：上游先发 51 字节，等待 0.6 秒再结束；直连首块 0.0012s 到达，经 shim 首读 65 字节、0.6066s 才到达，已经是完整响应。结果在 `raw/audits/shim-streaming-characterization.json`。这是 n=1 的行为对照，不是性能基准，也不能确定历史超时的全部根因。
2. shim 日志两次 `BrokenPipeError`，最终计数 requests/dropped_temperature 均为 0，不能解释为没有 writer 请求。计数只在启动和 `finally` 落盘；runner 用 SIGTERM 停进程，而 shim 没有相应信号处理，落盘计数不可靠。
3. 以上工装会影响路径可观测性与首块时间。因此本批只能签 NOT_PASSED，不能把它用作候选相对生产的延迟比较，也不能仅据本批把失败归因到候选或供应商。原 shim 未修、三题未重跑。

离线复现命令（`--output` 必须使用新文件）：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -B \
  docs/verification/2026-09-23-adaptive-l6-closure/probes/probe_shim_streaming.py \
  --shim /Users/a77/.finance-runtime/reviews/pr868-l6-natural-20260923-1455/k3_param_shim_live.py \
  --output /tmp/l6-shim-characterization-new.json
```

`raw/k3_param_shim_live.py.txt` 为原 shim 字节存档，SHA256 `44d225396320ae9356b03b258456602477aa1256cc9475eb2010698aa1d76bee`。探针验证原工装缺陷，成功退出不表示工装已修。

## #75 输入与未审边界

队列仍为待审，本页是宿主核对/作者侧材料，不是 K3 独立 Spec/Quality 结论。未找到本候选在队列所指目录中的双轴终稿；未把别的 PR 报告或全量测试代签。工单只授权 K3 通道；本会话未发新独立模型请求，不用 Codex 自签。

五处 HTTP wrapper 调用直接来源已逐点阅读，均在 `intelligence/services/llm_refine.py`：

| 行 | 函数 | 直接预算来源 |
|---|---|---|
| 1167 | `_post_chat` | `complete` 传 `deadline.require_remaining(0.001)` 和共享截止；`refine_or_reason:1751` / `vision.describe_image:152` 直接传 timeout，由 `_post_chat:1165` 创建局部 Deadline |
| 1219 | `_post_chat_synthesis` | `synthesize_messages:2151` 先构造 min(共享截止, now+本段片) 的 phase_deadline，重试共用；每次传其剩余量 |
| 1424 | `_post_chat_message_stream` | `chat_with_tools:1631` 建 Deadline，1636 取剩余量；同时转发 is_cancelled |
| 1546 | `_post_chat_message` | 与上行共用 chat_with_tools 的 Deadline/剩余量，但非流式路径未传 is_cancelled |
| 2304 | `_post_chat_stream_raw` | `synthesize_messages_stream:2403` 收窄共享截止，2416 `call_timeout(timeout)`，经 `_post_chat_stream` 转发；含 is_cancelled |

该模块的 Deadline API 为 `from_timeout/remaining/require_remaining/call_timeout`，没有 `slice()`；不能把“全部经 Deadline.slice”作为既成事实。传输层 `llm_http_transport.py:221` 再取 `min(now+timeout, deadline.expires_at)`。以上只核对直接调用链，不是所有上游研究预算的跨模块证明。

取消转发缺口的历史原件已回读：`~/.finance-runtime/adaptive-deadline-0922/mut-cancel2.log`，`15 passed, 125 deselected`，对应 `013eb5c4` 收据。它证明旧测试选择未抓住删除 is_cancelled 转发；不是本次候选重新做过变异，更不能由此断言当前产品取消失效。下一步仍需停顿期取消探针及撤保护/还原对照。

#75 正式启动前，需在独占检出冻结本页候选，区分运行代码与后来审计工装范围；先证明审查器的流式转发和请求计数可靠，再按工单做载荷同形网关预检、explore/execute/report 独立会话。作者测试与审查者自造探针分账，必红探针应进入 probe_bug，空回不签 PASS。本轮没有启动 #75，也未完成其准入自测。

## 验证与哈希

- Q1 审计器重放仍 `BLOCKED_JUDGE_UNAVAILABLE`，exit 1 为拒绝签 PASS；重放 JSON 与原审计逐字节相同。
- 冻结市场文件 751/751，mismatches=[]；数据库 SHA256 `75ff8d41eebf1a514140081c2899c9b4fd8df7287a0e5e3462fd52f3c975c941`。KB/外部输入未冻结。
- live 首尾代码/生产稳定身份未变，拥有的进程/锁已释放；收尾再查 19897/19898 无监听。未修改生产 8792，未合 main、未部署。
- `gitea_pr.py show 868` 重新确认 open、merged=false、WIP，head `cd520152f9bb`；通过 Keychain 认证，未暴露 token。前次裸 curl 的 403 不是 PR 消失。
- fetch 后冻结 `main=bbd53487f4cefdae97eae90f7322394d36e65462`，对 `cd520152f9bbf435de81d7b7f662bfa695eef26a` 的本机 merge-tree clean，预览树 `11654ad4df0dbdd7588497daeca9b1d3595ffe6e`。这是冲突检查，不是合并，也不是联合树测试。
- 工程九项收据只绑定 `7ad61a0d3`；新增预检测试旧读数 27 passed 只绑定相应 revision。本次不重跑全量，也不向最新 main 移签。

| 原件 | SHA256 |
|---|---|
| Q1 episode（私有根） | `e633a45dc4d6e84315b96949a731530237f2551cc43ae49726522354630e7020` |
| 冻结 manifest（preparation） | `5796a9b742eb44b779ed44d94f6ece23ff243e203e7f980e524263b1d1085bbb` |
| l6-closure.json | `596b452fe6c8fabbeeebfb9cb75b53dfbcdf3947e6a6658a42a4355b4234fa67` |
| q1-source-review.json | `9e401b74aa3d7e37edcefd68966e4a688ae645a7e38bc61f2f9a520a33d9a3ed` |
| q1-source-review-audit.json | `bff27b95a3fdf68a1894022617932ea0390d830195219070332c580005675d45` |
| q2-execution-audit.json | `00853df1d2414480119c76c5fec0f5c2df780353b98f76aec7571c6d2eb92d28` |

## 后续约束

先修复并离线验证独立工装，新的自然验收须另行获批、用新证据根；不得向本批补交 Q3、改题或重发。#75 独立结论、最终工程门禁、合入授权仍分别取得，不以此处的收尾记录替代。
