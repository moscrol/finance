# K3 修复版真实复验记录（2026-09-21）

## 背景

前一轮旧代码真实验收在首轮完整研究计划漏 `kind=PLAN` 后误走终局校验，K3 被要求直接输出 `FINAL_JSON`，没有工具调用、没有判官调用，最终未交付量价比较。业务补丁 `4c33e0d45` 将“完整计划体但缺 kind”送回严格 PLAN 校验与既有一次纠错，不自动补标签、不接纳候选动作、不扩大研究权限。

本轮按授权，对固定修复版执行一次隔离真实会话。工作树为 `/Users/a77/finance-worktrees/adaptive-research-loop`，加载 revision `72a2ac534449963aec9bc57afbb8f9d74e56d409`，K3 写手 `kimi-k3`，独立判官 `glm-5.3-flash`，只跑 `off` 单臂。生产 8792 未参与请求，旁车 8797 已在收尾时停止。

## 实际观察

1. 父会话首轮自然输出带 `kind=PLAN` 的计划，计划被接受并启动 3 条只读子研究。
2. 子研究中自然出现 `missing plan fields: kind`，但对应分支继续执行 `finance_query`，不是直接进入终局；两个分支返回了个股与板块证据，第三分支因预算耗尽失败。该证据支持“窄识别 + 有界计划纠错”已在真实运行中生效，但不代表所有模型形状都已覆盖。
3. K3 共完成 19 次工具调用，产出 14 条个股行情、板块行情、板块成分股、证据索引和记忆查询，正文含具体日期、数值、来源与证据编号。结构校验完成，所需输出均有绑定。
4. 独立判官配置正确且实际有 2 次判官调用账，但最终 `judge_status=unavailable`，原因是 `semantic judge window exhausted by prior attempt`；`http_status=null`、`exc_class=null`。这不能归因于 K3 400，也不能说判官服务发生了具体 HTTP 故障。由于判官不可用，未进入 repair / rejudge；公开结果降为 `partial` 并附“未完成独立复核”提示。
5. 独立复算发现正文“14日均值约 6.55 亿”应为 `6.6153` 亿、约 `6.62` 亿；区间复利 `-3.0766%` 与 `-3.08%`一致。另“无涨停”超过现有证据边界，证据只支持“本地未收录该股 9 月涨停记录”。本轮不手工改公开稿，不把降级结果冒充质量通过。

## 裁决

- PLAN 路由：本轮自然运行验证通过。
- 真实取证与正文生成：本轮验证通过，未复现上轮零工具提前终局。
- 独立语义复核与完整金融交付：本轮未通过；判官窗口耗尽，且正文存在可复算均值错误和一处证据边界过强表述。
- K3 能力结论：仍可作为写手；本轮失败归因是判官窗口/正文质量边界，不是 K3 不可用。
- 不追加 live 次数以追求 `partial` 以外的特定状态词；不把这一笔当作自然“无工具改稿 + 自报 partial”样本。该路径仍未验证。

## 收据

原始证据目录：`/Users/a77/.finance-runtime/adaptive-k3-plan-fix-live-20260921/`。

关键文件：`probe/off/raw-run/continuous-episode.json`、`probe/off/raw-run/report.json`、`probe/off/answer.md`、`inspection/off.json`、`execution.json`、`production-before.json`、`production-after.json`、`judge-config.json`、`key-scan.json`。目录内 `evidence-manifest.sha256` 固定了排除说明中指定文件之外的逐文件 SHA-256。

本轮未 push、未开 PR、未合 main、未部署。业务补丁仍只有原定向回归收据；旧 `be6602934` 完整门禁不可移签当前 revision。
