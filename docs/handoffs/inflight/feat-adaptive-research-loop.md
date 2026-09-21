# feat/adaptive-research-loop

## 这个分支做什么
模型自主研究、同会话修订与公开保真。树 `~/finance-worktrees/adaptive-research-loop`。

## 决策与被否方案
- 变稿/bindings即重核；来不及则旧稿+partial+公开提示。进展/预算与公开保真正交，不改进度门。
- K3可当写手；缺特定流程样本不等于模型不可用，不再写“等稳定K3”。
- 漏kind的完整计划体送严格PLAN纠错，不自动补标/接纳；带终局字段、模糊片段、已收口不借道。否全局宽解析，防误开研究。
- 股票精确比较拒裸码不猜后缀；不剥已接受句的连接词；不放宽HTTP400重试。
- 背景/方案见 `docs/handoffs/2026-09-21-adaptive-k3-plan-routing.md`。

## 当前状态
业务补丁 `4c33e0d458be9cd171c4bb2f7de39b6ccb62d119` 已提交。单次K3真验收在旧干净129e6cbea：两轮/零工具，漏PLAN标签被误催终局，交付未过；已离线返修，未跑修后真模型。未push/PR/合回main/部署。
本地gitea/main已观察到79b11d4268a3，未追合；旧be660全门禁不移签新补丁。

## 已验证
- 固定干净4c33e0d45相关10文件748P/0F/0E，Ruff全仓过；首尾SHA/树一致，精确收据校验过。
- 收据 `~/.finance-runtime/test-receipts/20260921T114433Z-4c33e0d4.json`，只签定向回归。
- 真实seq6逐字节夹具；开发先9F后264P；四项撤保护均被抓住，不改磁盘源码。
- 证据 `~/.finance-runtime/adaptive-k3-writer-live-20260921/README.md`，71件SHA256SUMS回读通过；run_20260921_192812_245529。8797已停，8792未改，密钥不落盘。
- 历史be660完整12698P/前端110P/E2E34P2S见 `2026-09-21-adaptive-forward-c097-gates.md`，仅签旧revision。

## 未验证 / 已知边界
K3本次两次正常返回，无400；实际judge调用0、repair0，phase_trace的repair投影不算执行。“无工具改稿+自报partial”重核路径未进入；此前GLM修复版均completed。修后自然取证/金融交付、正常长答推理不泄漏仍未验。新补丁完整合入门禁和独立Spec/Quality待做。离线续轮是替身，不翻真实失败结论。

## 下一步
授权下固定修复版单次真入口验收，先查取证和交付，不刷状态词。之后再准备推送/PR；最终待合SHA须取得对应完整门禁。合main/部署待明确授权。

## 踩过的坑
显式cd本树，pytest/ruff用 `~/finance-workspace-private/.venv-workbench/bin/python`；E2E用现有frontend gate传解释器。收据取日志打印的固定路径，不取共享latest；FWP_TEST_RECEIPT这里只支持0禁写，不支持自定义路径。stock14行在，sector25行是上下文截断，不等于库缺日期。
