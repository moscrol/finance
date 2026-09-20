# 生成降级尾提交收尾

## 这个分支做什么
接替capability-wiring旧413b7a07的生成失败留痕，不移植旧材料证据实现。

## 当前状态
基底728f327160bbd2485cb635e7ef09d040d718d7b5；代码c45ad5f853a53b96f7f369c1295027770d20aa5d已推，PR #805 open、未合、未部署。本文件与日期快照单独提交，后续tip须另验。

## 决策与被否方案
- fallback_reason即记生成降级；有检索引用不洗掉失败。message/run/report同步，方法论旧措辞不变，正常生成无警告。
- 不加重试、不改预算、检索或材料权限；同步产品入口文档。
- 不整枝摘旧6c7bea6e：聊天文本重建证据不满足当前材料来源合同；同数重算与两参表格单列未决。
- 展开见docs/handoffs/2026-09-20-generation-degrade-closeout.md。

## 未验证 / 已知边界
不是全量合并签字：未跑全量Python、前端、E2E、跨仓registry或独立外审。
只验证显式fallback_reason，不证明所有上游空reason/抛异常的终态行为。
未调用真实模型或8792新会话，不证明答案质量改善；未切生产。
材料/重算由#770对账，不代表该PR已实现；fincalc两参接口及沙箱版本另拆。旧e8a63007交接不复制。

## 下一步
审#805并对最终tip补适用准入，合main须用户确认。
#770先明确冻结材料身份→计算输入哈希→同数重算合同，不绕过权限从聊天拼证据。
旧capability树和来源补丁保留；#732已合不代表三个尾提交已交付。

## 已验证
c45ad5f8干净树白名单环境、umask022、主树venv：584P4S，含orchestrator/lane、Workbench API、materials和test_e2_*；4S为原有嵌套标签用例。全仓Ruff、提交门禁、严格同SHA收据通过。修前2F2P。
证据根~/.finance-runtime/reviews/stale-work-closeout-20260920/；仓内docs/verification/2026-09-20-generation-degrade/。首尾SHA同、状态空。

## 踩过的坑
生成失败+检索成功仍是降级；completed不等于正常综述。
首轮red收据在共享目录，后续仅重定向收据输出。一次性runner沿用既有工具，不新增通用测试框架。
