# E2：LLM-as-judge 与 Knevo 对照状态（2026-09-15）

## 结论

本轮**没有完成正式 E2 LLM-as-judge 评分，也没有完成 Knevo 同题 PK**。

- Grok CLI 只完成了一次隔离的、回顾性的语义判卷试跑；使用 `grok 1.0.25` / `grok-4.6`，判了两份已归档 T2/T3 答案。
- 该试跑只把答卷正文和简化 rubric 交给判官，**没有附完整原题、完整材料和 T2→T3 的完整上下文**，因此结果不具备正式验收资格，也不能作为本轮产品分数或胜负。
- 试跑结果均为 `passed=false`，指出答卷混入材料外的真实数据中心板块行情；这与既有 QC 对 E2 材料边界的发现方向一致，但只能算回顾性提示，不能替代完整题面判卷。
- Knevo 本轮没有发新题，没有取得操作者事先不可见的 Knevo 原答，没有形成合法的未揭盲成对样本；因此没有 PK、胜负或吸收结论。

## Grok 试跑收据

执行入口：`/Users/a77/.grok/bin/grok`，版本 `1.0.25 (f7e67d6988e2)`。

第一次按 `read-only` 沙箱启动时，CLI 因 `/var/run/docker.sock` 符号链接无法解析而拒绝启动；该失败保留在 `/tmp/e2-llm-judge-20260915/summary.json`。随后按现有 CLI 适配器支持的 `LLM_JUDGE_GROK_SANDBOX=off` 重跑，工具、联网、子代理均通过参数禁用，但系统沙箱关闭，因此不把它描述为与 P3d 独立 QC 等价的隔离。

第二次结果保存在：

- `/tmp/e2-llm-judge-20260915/summary-sandbox-off.json`
- `/tmp/e2-llm-judge-20260915/T2-sandbox-off.json`
- `/tmp/e2-llm-judge-20260915/T3-sandbox-off.json`

输入答卷 SHA-256：

- T2：`ad501176187443d2772cd27e89a7fddbd869e49c940b0d4ed6132afe81f2a25e`
- T3：`e3c9cd9ef1dab5ab3b35aa25058d6f8df2fdcfaf34d96055a6a1a99f6e99a636`

该记录的用途是说明“确实调用过 Grok 判官并得到结构化响应”，不是正式评分收据。

## Knevo 可用入口与缺口

仓内既有流程记录，Knevo 原答可通过用户已登录 Chrome 的 CDP（Chrome DevTools Protocol，浏览器调试协议）回贴取回；这不是不存在入口，而是本轮没有执行新题流程。正式 PK 还需要：

1. 冻结题面、材料和判卷 rubric；
2. 先生成本地答案并做不可修改的哈希封存；
3. 在操作者/本地评审未见本地答案的情况下取得 Knevo 原答；
4. 再由独立判官分别评分，并记录题面、模型、原答和时间边界。

历史 2026-09-13 T2/T3 只能作为揭盲后复验：文档已明确操作者见过 Knevo 原答，且当时是 K3 自审、材料边界存在缺陷，不能改算为本轮正式 PK。

## 与 P3d 的关系

P3d 独立 QC 是代码读取边界审查，使用 `dcprwo/gpt-6-astra`，不是 Grok，也不是答案级 LLM-as-judge；其局部通过报告见 `p3d-1f6ebc5d-independent-qc-20260915/`。两者不得合并成一个“产品通过”结论。
