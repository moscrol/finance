# 600f2aa9 质检：T2 止血通过，发布准备待补

## 这个分支做什么
独立审三个提交；报告见 `docs/handoffs/2026-09-13-route-gate-600f2aa9-qc.md`。本枝仅质检文档，未合并/推送/部署/发模型题。

## 决策与被否方案
| 选了 | 否了 | 理由 |
|---|---|---|
| 生产基线最小候选先验 | 直接部署 600f2aa9 | 生产含其不具备的 551 个提交，会回退现有代码 |
| 探针按 message/run ID 配对 | 仅数新增答案 | 旧 pending 迟到与本轮 failed 均可被报成功 |
| 长 quick_fact 另单 | 泛称同族全部入口修好 | answer_orchestrator 两消费点仍无长度闸 |

## 当前状态
- 审查代码 `600f2aa9`，树 `/Users/a77/fwp-wt-qc-route-600f2aa9`。
- 生产只读实测仍 `2efdff46`，clean、code_matches_repo true；fetch 后 main `883e3d36`，生产差量 86 提交。
- 离线试移植副本 `/private/tmp/route-gate-qc-production` 有本轮未提交补丁，不可部署；父对照 `/private/tmp/route-gate-qc-parent` 干净。

## 已验证
- 干净被审 tip：定向 124P/1x；全量 intelligence/tests 7002P/14S/2x，收据 `~/.finance-runtime/test-receipts/20260912T164818Z-600f2aa9.json`，expect-revision 校验 exit 0（文档提交前）。
- 两道闸分别放开均抓红；T2/T3 与冻结原题去尾 LF 对账一致；触碰 Python Ruff/差异空白检查通过。
- 生产基线最小试移植定向 125P/1x，但 T2 为 theme_analysis/research，不是旧枝的 comparison。现有测试只钉“不扫描 + research”。
- probe 离线反例：旧轮迟到/本轮 failed 都 exit 0。

## 未验证 / 已知边界
- 未跑最终发布候选全仓/前端/E2E/registry 门禁；旧枝全量不可替代合流收据。
- 未走真入口 T2 八问与 T3 继承；theme_analysis 是否违背虚构材料约束待验。
- K3 自审长期质量不在这次代码质检结论内。

## 下一步
1. 执行方修 probe 身份绑定与终态检测，补回归。
2. 当前生产基线移植最小修复成干净候选，主干线另接最新 main；别覆盖整文件。
3. 候选全门禁绿，隔离端口同配置 T2→T3：核实模型执行、八问有答、禁补现实事实、run 配对及增量续问。
4. 证据齐再申请用户确认切流；不捆绑 86 提交。

## 踩过的坑
- 原全量收据 dirty=true，本轮重跑才有可还原证据。
- /private/tmp 代码根触发沙箱读取测试红；移树后残留 pyc 旧 source 路径又触发 inspect 假红。正常用户目录 + 清自有缓存后全量绿，未改测试或 skip。
- “研究车道”不等于“通用 owner”，更不等于真实完整答卷。
