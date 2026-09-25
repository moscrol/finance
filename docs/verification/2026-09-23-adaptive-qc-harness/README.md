# #75 工装收口与 PR #868 独立审查阻塞

## 结论

**`BLOCKED_REVIEW_TRANSPORT_DEADLINE`**。这是宿主对执行状态的封存，不是 K3 签发的 Spec / Quality 结论。

- 新工装离线回归与停顿期取消对照通过；作者定向测试 **45 passed**，绑定干净 `2f4b5f089cbdffdb4ebf4ffea1bf0c896cb436a0`。
- K3 网关预检通过，正式 Spec explore 发出 14 次请求后，在第 14 次的 120 秒单发上限处中断。无探针文件、无终稿；不能签 PASS，也不能签产品 CHANGES_REQUIRED。
- 按 #75 的“任一会话零终稿即停该候选”规则，不再请求 execute / report，也不启动 Quality 模型会话。没有重试、换模型或加预算。
- 先前 L6 仍 **NOT_PASSED**，本轮没有金融题请求，不补 Q3。PR 保持 WIP，不合入、不部署。

机器可读终态：[report.json](report.json)。全部归档文件与私有原件逐字节一致，映射及 SHA256 见 [archive-manifest.json](archive-manifest.json)。原始事件流和命令全量输出留在私有根，其摘要哈希见 [raw/private-manifest.json](raw/private-manifest.json)；不在仓内复刻模型思考正文。

## 身份与分账

| 对象 | 固定身份 / 范围 |
|---|---|
| 独立审查候选 | `31f1b40dd788d36c71da249d59fb769c50d7cd30` |
| 比较基线 | `9a02279863733c9b9f60fd92fcc7e840fa83f878`，该候选与前次冻结 main 的 merge-base；不是最新联合树 |
| 独占候选目录 | `/Users/a77/.finance-runtime/reviews/pr868-k3-qc-20260923-1530/candidate/finance-workspace-private`，detached / worktree lock / 审查工具只读 |
| 本轮私有证据根 | `/Users/a77/.finance-runtime/reviews/pr868-k3-qc-20260923-1530/` |
| 工装提交 / 45P | `2f4b5f089cbdffdb4ebf4ffea1bf0c896cb436a0`，不是独立候选 |
| 历史全量工程收据 | 仍只属于 `7ad61a0d3fd9ee63abe2089a4049a0a1b4a8bc16`，不移签新工装或联合 main |
| 先前自然验收 | `../2026-09-23-adaptive-l6-closure/`，原件及 NOT_PASSED 不变 |

| 账本 | 实际结果 |
|---|---|
| 宿主工装 / 取消 / L6审计定向回归 | 45P，正确解释器、Python 3.12.13、依赖指纹 `3328bed61f3e21ea`、干净树；收据校验通过 |
| 宿主停顿取消 triplet | 3 原版绿 / 3 撤保护红 / 3 还原绿；0 模型请求 |
| 独立 K3 自造探针 | 0 个落盘、0 个执行，不能借用宿主探针数字 |
| 独立 K3 作者测试复跑 | 0；停在 explore，不冒充 execute |
| 必红 `assert 1 == 2` | 宿主沙箱准入观察到 exit 1；独立 execute 未执行，#75 的该项仍未完成 |

45P 的收据原件：`~/.finance-runtime/test-receipts/20260923T073620Z-2f4b5f08-5a926a26676f.json`，仓内副本 [raw/host-targeted-pytest-receipt.json](raw/host-targeted-pytest-receipt.json)。之前脏树 45P、初版 12P 只作开发读数，不替代此收据。没有重跑全仓四叶门禁。

## 工装修复

新增 [k3_review_shim.py](../../../scripts/review_probes/k3_review_shim.py)，保留旧 L6 shim 原件不改。本轮仍只走私有 `19899 -> 18788`，不改生产入口。

- HTTP 响应使用 `read1()` 小块读取，已到达的 SSE 块立即透传；测试要求第一块在假上游 EOF 前可读，不只比较最终文本。
- 监测客户端断连和截止，主动关闭上游 socket；SIGTERM 中断正在等待读取的请求并收尾，SIGKILL 后至少有预先持久化的准入记录，不能声称干净完成。
- 在副作用前持久化 `admitted` 和 `dispatched` 意图，再记录 HTTP 状态及 terminal outcome；并发请求不能超额预占。`dispatched` 是发出意图，不是供应商计费收据；本批 17 次均另有 HTTP 响应头可对照。
- 400/429 锁住后续准入；固定 K3 / 回环路由 / 有限请求数与存活期限 / 新目录拒覆盖。中途截断的响应不写成功的 chunked 结束标记。
- 凭据、提示词和响应正文不进代理日志。`completed` 仅指传输结束，不表示语义任务或审查完成。

离线 12 项包括首块时序、载荷保真、断连、SIGTERM、SIGKILL、响应头 / 正文等待截止、400/429、并发额度、截断响应、错误模型拒发、生命周期收尾。另 6 项取消回归，加原 L6 审计 / compare 的 27 项，共 45P。

## 取消缺口

[probe_stalled_cancellation.py](../../../scripts/review_probes/probe_stalled_cancellation.py) 明确接收候选路径和 SHA；检查首尾干净、源文件 SHA256 相同。AST 只在进程内删除 wrapper 向 opener 转发的一个 `is_cancelled` keyword，不修改候选磁盘文件。

假上游先发 1 字节、停 1.6 秒；0.3 秒翻转取消；片与共享预算均 10 秒。相同断言要求 `LLMStreamCancelled` 且耗时 <1 秒、只发一次。

| 路径 | 原版秒 | 撤保护秒 | 还原秒 |
|---|---:|---:|---:|
| wrapper | 0.331 | 1.705，无取消异常 | 0.355 |
| tools stream | 0.319 | 1.711，取消但已迟到 | 0.348 |
| synthesis stream | 0.357 | 1.741，取消但已迟到 | 0.353 |

原始结果：[raw/cancellation-triplet.json](raw/cancellation-triplet.json)。对应普通测试已加入 `tests/test_stalled_cancellation_probe.py`。旧 `013eb5c4` 的“15P、变异存活”仍是历史事实；本轮补了新候选的宿主行为证据，但未完成独立 K3 审查。

## 审查器准入

复用已有 pi + K3 分段 runner 的结构，凭据经 `pi auth print-api-key` 仅驻留控制进程内存。工具 read / write / bash 都经同一 macOS 沙箱，工具进程无密钥。只写本轴 work，不能写候选、读作者树 / 凭据 / 历史结论，也不能访问外网、18788、19899、8792。

三次未通过的离线尝试保留在私有 `spec/sandbox-preflight*`：第一次宽泛回环规则没挡住网关 TCP 连接；第二次直接 IP 地址语法不被 sandbox 接受；第三次排除式回环规则仍未挡住。均未发 HTTP 模型请求。最终改为仅允许 26001–26008 八个假服务端口，`sandbox-preflight-04` 的正反断言通过。网络规则不能仅凭文本“看起来限制了”就视为生效。

Quality 目录也仅完成相同离线准入，未请求模型。两轴目录相互隔离，没有把 Spec 未完成的判断传给 Quality。工装快照在 `tooling/`，仅用于审计；其中绝对路径绑定本次私有根，不应原样作为下一批执行脚本。作者 HTTP 测试的随机端口并不在工具白名单内，后续审查须明确这一工装边界，不能将 EPERM 算成产品失败。

## 网关与停批

| 阶段 | 模型请求 | 结果 |
|---|---:|---|
| 小载荷完成请求 | 1 | HTTP 200，约 3.02 秒 |
| pi tools / stream 往返 | 2 | 一次 read，随机 fixture 内容正确返回 |
| Spec explore | 14 | 前 13 次传输完成；第 14 次流未在 120 秒内结束 |
| Spec execute / report | 0 | 未启动 |
| Quality 模型会话 | 0 | 停候选后未启动 |
| 总计 | **17** | 16 传输完成、1 单发截止；0 重试、0 HTTP 400/429 |

Spec 耗时 324.64 秒，没有触 600 秒阶段帽，也没有触 24 请求帽。末次 6.61 秒收到 HTTP 200 头，120.007 秒失败；pi 报 `terminated`，有流式数据但没有终稿。不能把 HTTP 200、进程 exit 0 或 `execution.complete=true` 当通过：后者只表示宿主完成了记账。

独立会话实际执行了 17 次只读工具调用，未写探针、未执行测试。命令及出口摘要见 [raw/reviewer-tool-summary.json](raw/reviewer-tool-summary.json)。所有 C1-C7 仍为 not_verified，不从未收尾的模型过程文字提取“批准”。没有证据把历史 L6 超时或本次未完成唯一归因于产品、供应商或 shim。

## 收尾与后续

- 模型会话、控制器与私有 shim 已退出，19899 无监听；候选首尾干净、输入哈希不变，账本准入 / 发出意图 / 响应头数量一致。
- 归档前扫描私有工装 / 事件 / 命令文件的 JWT / bearer / sk 前缀模式，无命中；精确数量以 `raw/key-scan.json` 为准，不代表任意秘密检测器的完备性。
- 下一次 #75 须新证据根、重做准入并明确请求形状及预算，不续接本轮 execute，不提高本轮预算补签。优先让探索阶段更早落盘局部探针；任何设置调整都应显式登记。
- 自然验收另获授权，不补本批金融题。合入仍需最新 head / main 的完整门禁、联合树验证、独立结论及用户明确确认。
