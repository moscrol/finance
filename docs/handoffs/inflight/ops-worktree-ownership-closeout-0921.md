# 工作树归属与接管

## 这个分支做什么
保护活跃现场，修看板/收据未知误判，协调#812/#813/#814固定组合验收。

## 决策与被否方案
- 归属多源核验，否决凭进程/cherry+接管或删树。
- 身份是执行/只读不变量，新码新收据；否决移签旧绿。
- 独立复核走已登录订阅，否决无预算付费fallback；额度拒绝后停止。
- 本轮展开`docs/handoffs/2026-09-21-ownership-independent-review-blocked.md`；修复前史`2026-09-21-ownership-resume.md`。

## 当前状态
固定47530e20保持净树，代码cdf6647cf已在#814，既有86文件封存60463b703。用户已授权独立复核，不再写“尚未授权”；实际Spec因Codex订阅额度用完退出1，无成功回答/工具执行，Quality未启动，整体BLOCKED。
本地另报缺codex-code-mode-host；初次配置拒绝原件另存（无会话），不是两轮模型审查。未购额/切付费/自动重试；main/8792/生产/定时任务未动、未删树。
新证据`docs/verification/2026-09-21-ownership-independent-v3/`。原目录`~/.finance-runtime/reviews/ownership-independent-v3-20260921/`，两个独占审查树ownership-{spec,quality}-v3-0921保留。

## 已验证
本轮只核身份/日志哈希：候选和两审查树同47530e20且净，main仍728f3271。实际Spec会话8.218秒退出1，无审查产出；根QC只签阻塞事实。
前轮历史：47530e20作者12068P/85S/2X、前端110P、E2E34P2S及registry五项0；唯一收据在ownership-resume的v3/python/receipts/gate-Idx5hl80/pytest.json。本轮未重跑，不升级为独立绿。

## 未验证 / 已知边界
独立Spec/Quality尚缺；订阅登录≠额度可用。服务提示Sep27 1:06AM再试，时区未标。没有真实完整副本回填父子发布/恢复验收。首尾净树不证明期间未改后还原。

## 下一步
先离线修CLI执行组件兼容性，再由用户决定等待订阅或指定可用通道；涉及费用先确认上限。新请求新目录，不覆失败，不自动加额。独立复核过后，合main/生产回填/部署/删树仍分别确认；三单与组合不可重复合。Arena另线不要顺手接管。

## 踩过的坑
latest仅导航，owner启动前认领，读取旧报告也核tree。审查进程启动≠成功模型回答≠有效验收。有限runner随证据保全，不安装长期调度；未改harness共享脏树。
