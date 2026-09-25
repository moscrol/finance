# #75 第二批：网关准入阻塞

## 结论

**`BLOCKED_GATEWAY_PREFLIGHT_DEADLINE`**，仅为宿主执行终态，不是独立 Spec / Quality verdict。

用户在上一批封存后授权“执行”。本次使用新证据根重新准入，没有续接旧 explore、补发 report 或重跑金融题。第一发小载荷在 **120.004 秒**处失败，没有观察到上游响应头；本地调用方得到私有 shim 的 **502**，不能记为上游已返回 HTTP 502。

实际仅 **1 次网关转发尝试**。pi 读写往返 0，Spec / Quality 正式会话均 0，探针写入 / 执行均 0，作者测试复跑 0，自然金融题 0，重试 0。下游模型是否开始执行及供应商计费不可从这次日志确认。

报告：[report.json](report.json)。冻结计划：[protocol.json](protocol.json)。归档副本与私有原件的逐字节映射：[archive-manifest.json](archive-manifest.json)。

## 固定身份

- 候选：`31f1b40dd788d36c71da249d59fb769c50d7cd30`；基线仍为 `9a02279863733c9b9f60fd92fcc7e840fa83f878`，不是最新联合 main。
- 新独占 detached / 加锁候选：`~/.finance-runtime/reviews/pr868-k3-qc-20260923-1607/candidate/finance-workspace-private`。结束时 revision 符合、工作树干净。
- 新私有根：`~/.finance-runtime/reviews/pr868-k3-qc-20260923-1607/`。旧 `1530` 根与旧 L6 原件不改。
- 代理仍是工装提交 `2f4b5f089` 的同一份，SHA256 `b5dd3b1d37524fe8060ed7752f1aaf129aaf877f8799932fad313e7b30cd6055`，只监听19899、转发18788，不改生产8792。

## 本次调整

| 项目 | 新批次计划 | 是否实测到 |
|---|---|---|
| 模型 | 仍为 mirasim-kimi / kimi-k3；thinking从xhigh改为medium，pi单发输出上限8192 | 小载荷已带medium；pi实际工具请求未启动，不能签配置有效 |
| 时间 / 请求上限 | 单发120秒、阶段600秒、最多24请求，均不扩大 | 小载荷触单发上限；正式阶段未启动 |
| 网关准入 | 小载荷1次 + pi read/write/final最多3次，共最多4次 | 停在第1次，未做工具往返 |
| 探索交付 | 读一个核心模块后立即写短小探针，逐文件交付 | 未启动，效果未验 |
| 完成校验 | 核轴身份、拒绝length截断；explore必须确有探针文件，不能只靠complete=true | 离线代码冻结；真实阶段未触达 |
| 会话隔离 | 两轴与explore/execute/report各用新会话，不传旧模型输出或对方结论 | 正式会话均未启动 |

上述是新请求形状，不是降低正确性标准。一次失败且没有配对对照，不能认定medium、输出上限、账号、负载或服务中的任何一个是唯一原因。

## 离线准入

- Spec `sandbox-preflight-04` PASS：同一工具沙箱验证候选可读、仅work可写、凭据/作者树/源树写/符号链接逃逸拒绝、外网与网关/生产连接拒绝、假服务可连接。
- Quality `sandbox-preflight-04` 在假服务26001端口绑定时报 EADDRINUSE。失败原始命令与输出保留在 `raw/quality-preflight-04-failure-*`；没有模型请求。
- Quality改为在原白名单26001–26008选择可绑定端口，`sandbox-preflight-05` PASS。没有杀占用者、没有扩大权限，也没有把失败目录覆盖成PASS。
- 宿主必红 `assert 1 == 2` 观察到 exit1；这不是#75独立execute阶段的阳性对照完成，后者NOT_RUN。

工装及六份阶段提示快照见 `tooling/`；绝对路径绑定本次根，仅供审计。通用代理与取消探针仍在仓内scripts/tests，本轮不创建第二套通用审查框架。

## 真实请求与终态

`raw/spec-gateway-shim-requests.jsonl`：admitted=1、dispatched=1、finished failed=1；没有headers事件，最终status=null。`dispatched`为副作用前持久化意图，不是计费收据。

客户端 `raw/spec-gateway-tiny.json`：HTTP502、body为空、耗时120.010秒。代理源码的异常分支在尚未发响应头时生成502/504，因此保留原runner的 `BLOCKED_PROVIDER_HTTP_502` 字段，但宿主根结论纠正为“未观测上游状态的准入截止”，不将原标签照抄为根因。

控制器总耗时121.899秒，代理exit0、active=0、shutdown_complete=true、请求数对账一致；拥有进程已退出，19899无监听。未观察到400/429，但也没有上游HTTP成功资格。

此前第一批为17次请求（网关3 + Spec14），本批为1次转发尝试，累计18次网关尝试；不据此推算已结算模型调用或费用。两次连续候选尝试都未完成，不自动启动第三次。

## 验证范围与下一步

原全量工程收据仍只属于 `7ad61a0d3`；45P定向收据仍分别绑定 `2f4b5f089` 和 `2c61ff825`，本轮未重跑或移签。L6仍NOT_PASSED，本轮没有修自然交付、合入main、前向合流或部署。

下一步先由网关维护方结合此请求时窗核对服务状态与兼容载荷；当前没有足够证据支持改产品、继续升预算、换账号/模型或重启共享网关。重新审查须另定准入方案与新证据根，不能续跑本批execute。合入仍欠独立双轴终稿、自然验收、最新head/main完整门禁和用户明确确认。
