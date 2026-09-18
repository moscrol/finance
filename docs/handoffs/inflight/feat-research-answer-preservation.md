# 研究答案保留｜2026-09-18

## 这个分支做什么
同任务安全分析遇普通质量/格式问题仍保留，疑点与修订追加；展示不等于核验通过。

## 决策与被否方案
| 选了 | 否了 | 原因 |
|---|---|---|
| 候选与准入分账 | 放宽身份/历史门 | 保稿不能授予完成 |
| 格式修结构、缺口继续研究 | 共用一次纠正后重写 | 不无故丢研究能力 |
| 原稿＋必要证据完整承接 | 短稿覆盖/无限重试 | 保上下文，根预算不变 |
| 清洗→判正文→附注 | notice撑空稿 | 存在性不由派生说明证明 |
展开：`docs/handoffs/2026-09-18-finish-candidate-preservation.md`。

## 当前状态
代码已提交35ee8a5c（前片5f3b5b59、原live文档af9500ec），本轮收尾为文档。未push/开PR/合main/部署，未动8792；本轮未重新核生产health。
原live整体仍not_passed；新固定原件离线回放保住四段原文，不是新产品提交。新证据根R=`~/.finance-runtime/reviews/research-candidate-preservation-20260918/`；原214/44文件包逐个hash未变。

## 已验证
干净35ee：Python11664P/81S/2X/17warnings；前端107P与lint/typecheck/build、E2E34P/2S、静态/registry通过，crosswalk98warnings保留。收据 `~/.finance-runtime/test-receipts/20260918T101211Z-35ee8a5c.json`，不移绑文档SHA。
原件继续/恢复两路径：3512字合稿、3722字公开，原两拒收码不变，partial/unavailable，0真模型/工具。八类内存撤保护均红，原代码专项68P。

## 未验证 / 已知边界
候选账仅同进程；未接EpisodeState跨进程恢复，terminal restore仍可能空稿。旧helper/eval动态链未全审，旧answer_query真模型、新Workbench真模型交付及独立QC未跑。
普通工具900/240预览、进度、板块比较覆盖、按E扩读及原金融问题另线。Mac/Node26/DuckDB1.5.4非CI镜像；基座0a1cb8c4是本地冻结ref，本轮未fetch。

## 下一步
先读本轮verification。要扩跨进程恢复，单列候选持久化/身份/崩溃点合同，不从任意model_turn猜稿。新版live或A/B另冻结模型/数据/预算和一次提交协议并确认；不能覆盖旧not_passed。合main/部署仍等用户确认。

## 踩过的坑
后稿精确包含旧稿也不能清复核债务；同hash须核语义，旧未知E号不能复活。恢复需正文引用卡，不只binding。模型返回后取消仍failed/cancelled，资源照结算。E2E改RE06端口须同步RE06_E2E_URL；首败1F/33P保留，不能隐去。源码点号/测试假秘密命中扫描须分类，不能称整包零命中。
