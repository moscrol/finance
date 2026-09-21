# feat/adaptive-research-loop

## 这个分支做什么
模型自主研究、同会话修订与公开保真；当前收尾 K3 写手的 PLAN 路由修复。

## 决策与被否方案
- 完整计划体漏 `kind` 送严格 PLAN 纠错；不自动补标签、接纳候选动作或扩大权限，避免误执行。
- K3 可当写手；本轮判官窗口耗尽不能泛化成 K3 不可用，也不能把入口 completed 当研究交付通过。
- 变稿/bindings 即重核；来不及则旧稿+partial+公开提示。研究进度/预算与公开保真正交。
- 不追加 live 次数追特定状态词；不手工改真实公开稿的数值或证据表述。
- 背景与方案见 `docs/handoffs/2026-09-21-adaptive-k3-plan-routing.md`；本轮复验见 `docs/handoffs/2026-09-21-adaptive-k3-live-reverification.md`。

## 当前状态
业务补丁 `4c33e0d458be9cd171c4bb2f7de39b6ccb62d119`；真实被测版本 `72a2ac534449963aec9bc57afbb8f9d74e56d409`，之后仅更新交接文档。一次修复版 K3 真实复验已完成：父计划接受、3 分支启动、19 次工具调用、具体量价/板块正文生成；判官 2 次调用后窗口耗尽，公开结果 `partial`，未进入 repair/rejudge。未 push/PR/合 main/部署。

## 已验证
- 真实 run `run_20260921_203845_282895`：首轮父计划带 `kind=PLAN`；子分支自然出现 `missing plan fields: kind` 后仍继续 finance_query，两个分支返回证据。
- 结构校验完成、required outputs 有绑定；K3 无 HTTP400，production 8792 前后仍 `adcda94b5e40...`，8797 已停，密钥扫描无命中。
- 独立复算：14 日成交额均值 `6.6153` 亿（约 `6.62`），公开稿误写 `6.55`；区间复利 `-3.0766%` 与 `-3.08%`一致。“无涨停”应收窄为“本地未收录 9 月涨停记录”。
- 原始包：`~/.finance-runtime/adaptive-k3-plan-fix-live-20260921/README.md`；固定目录清单见 `evidence-manifest.sha256`。复验包 20:38/20:46 的 8792 快照健康且版本未变；收尾即时探测两次拒绝连接，原因未查明，未重启/操作生产，不覆盖原收据。

## 未验证 / 已知边界
判官真正通过、自然 repair/rejudge、无工具改稿+self partial、正常长答无推理泄漏仍未验证。当前正文还有确定的均值误差和一处超证据表述；不能签完整研究交付。当前补丁尚未取得新 revision 的完整合入门禁；旧 be660 全量收据不可移签。

## 下一步
先由用户决定是否针对判官窗口或正文质量做具体修复；若修代码，先补对应回归与定向门禁，再决定是否需要一次新的真实验收。推送/PR/合 main/部署均需明确授权。

## 踩过的坑
pytest/Ruff 用 `~/finance-workspace-private/.venv-workbench/bin/python`；收据取固定路径，不取 latest；`FWP_TEST_RECEIPT` 只支持 `0` 禁写；入口 status 不等于研究成功；配置判官不等于判官实际通过；无本地涨停记录不等于“没有涨停”。
