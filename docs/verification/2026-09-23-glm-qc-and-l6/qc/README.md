# #75 GLM 新授权批：Spec 执行交付被拒

## 结论

**BLOCKED_SPEC_EXECUTE_DELIVERY，尚无独立 Spec / Quality verdict。** 这是宿主根据原始收据作出的运行状态，不是宿主代签审查。PR #868 仍 WIP，不合入、不部署。

用户授权：`那你验证，反正写手可以是不同的llm，然后把75和l6做了`，后续 `继续`。私有根 `~/.finance-runtime/reviews/pr868-glm-qc-20260923-1922/`；L6 独立根 `pr868-l6-glm-20260923-1945/`，不混用本批计数。

冻结产品候选 `31f1b40dd788d36c71da249d59fb769c50d7cd30`，baseline `9a02279863733c9b9f60fd92fcc7e840fa83f878`。协议修复代码来自 `324a76f9a`，本轮分支起点 `a8796ca9c`；两者均不替换产品候选，也不接管历史全量收据。

## 实际执行

| 阶段 | 请求 | 结果 |
|---|---:|---|
| 两轴离线沙箱 | 0 | PASS，未外呼模型 |
| Spec 网关准入 | 4 | PASS：一条小请求，三轮 read / write / final，落盘一致 |
| Spec explore | 15 | STAGE_COMPLETE，生成原始探针；不是审查终稿 |
| Spec execute | 17 | 全部传输完成；交付身份不符，被拒收后耗尽单次收口机会 |
| Spec report / Quality | 0 | 按失败即停规则未启动 |

共 **36 请求，36 传输完成，0 传输失败，0 自动重试**。控制器、代理的 requests / dispatched 对账一致；`dispatched` 是外发意图收据，不是供应商计费收据。explore 有两次工具参数拒收，最后有效提交；它们不另算传输失败。

实际请求中的模型为 `glm-5.3`，官方端点 `https://open.bigmodel.cn/api/coding/paas/v4`，`reasoning_effort=low`，未剥温度参数，不宣称服务端 thinking 被关闭。

## 为什么停

`spec/execute/commands/014-deliver_stage/request.json` 保留原始交付：`stage="EXECUTE"`，而阶段合同要求 `stage="execute"`。其他候选身份相同不抵销这个不匹配。工具返回 `delivery identity mismatch`，没有生成 `submission.json`。

正常轮次 16 次后只有 1 次预留收口机会。该机会已用于上述无效交付，后续本地尝试以 `budget_or_report_already_dispatched` 拦住，exit 75。24 是阶段总上限，不代表收口后可以继续用完余量。本批未放宽协议、修写交付或再开同轴会话。

真实网关已证明前一轮的跨响应读写修复可用；真实 explore 已证明 CLI 中 `deliver_stage` 可调用并成功终止阶段。不能把当前不同的执行交付失败重新记成旧的工具名单遗漏。

## 探针边界

- 原始传输探针的 chunked 帧多了 CRLF，出现 `IncompleteRead`，属于探针错误。
- 审查模型自行修订的取消探针仍不产生换行，迭代器没有返回行，循环内的取消标记从未置位。未测到取消，不是已证明产品取消失败。
- 预算探针没有配置本地假 provider，调用在“未配置 LLM key”处返回，未到预留额度边界。应修探针，不是给沙箱注入真实密钥。
- 区分 10 秒单段额度与 0.5 秒共享截止的 wrapper 探针，观察到 0.50 秒停止、正常对照 2.96 秒成功。它是局部行为证据，不是最终 Spec verdict。
- 迟到判官探针、必红阳性控制、作者 pytest 均未执行。拒收载荷中的聚合计数也未作为有效测试收据采纳。
- 宿主未修改审查模型的探针或加工其终稿。代码、每次写入请求、执行输出均留档，原始模型事件含思考的文件只在私有根保留哈希，不复制进仓库。

## 收尾与未验

生成输入哈希未变，候选/作者检出仍干净，19899 已释放。归档 282 份逐字节原件，密钥扫描无命中；`archive-manifest.json` 不包含本 README。

`a8796ca9c` 对 `gitea/main@626d8a508` 的 merge-tree 无文本冲突，未实际合并、未跑联合树或当前 head 全量门禁。历史全量仍只属于 `7ad61a0d3`，历史 45P、工装 55P 均不移签。

下一批先解决阶段元数据交付及探针可执行性，重新冻结输入和预算；不能复用本批探针输出作为一份已经完成的独立双轴审查。
