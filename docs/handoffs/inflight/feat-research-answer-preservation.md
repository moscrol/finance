# 研究答案保留｜2026-09-18

## 这个分支做什么
同任务安全分析遇普通质量/格式问题仍保留；展示不等于核验通过。

## 决策与被否方案
- 候选与准入分账；不放松身份/历史/证据门，保稿不授予完成。
- 原稿＋必要证据完整承接，修订追加；不短稿覆盖、不无限重试。
- 新live一次首发零重发；不因失败换版本/模型刷绿。GLM已实际响应，不等GPT钥匙串。
- 本轮只验与诊断；复用邻枝Mapping投影修复，不全局解冻/default=str、不猜缺失日期。
展开：`docs/handoffs/2026-09-18-finish-candidate-glm-live.md`；保稿设计见同日`finish-candidate-preservation.md`。

## 当前状态
业务代码仍35ee8a5c；工程文档baf10987、模型纠偏69c056f6。新run=`run_20260918_213933_397262`：独立8849首发1/重发0/续问0，3轮glm-5.3-flash响应，failed/blocked，无答案。**新旧live均not_passed，保稿路径未触发**。
根R=`~/.finance-runtime/reviews/research-candidate-glm-live-20260918/`，82文件封存。8849已停、锁已释放，8792仍bf662身份/启动器未变；未push/合main/部署/整合邻枝。仅新增原件重放量具与文档。

## 未验证 / 已知边界
history_query缺end→参数正确拒绝→进展记账mappingproxy JSON崩溃；不是模型凭据失败。候选账仍仅同进程；自然保稿/跨进程恢复/独立QC未验。失败report used=false/tool_calls=0不等于零消费；durable state仍tools_pending，未尝试resume。KB/web等在线输入没冻结，非严格A/B。

## 下一步
1. 将已有a969d30a的research_progress Mapping投影小片纳入下一候选，保留未知对象拒绝/loop回归；不盲合整包邻枝。原件量具` scripts/review_probes/replay_history_progress_failure.py`。
2. 新精确revision工程验证后，再冻结/确认新live额度；本次样本不重发、不改判。失败用量与durable终态缺口另行处理。
3. 合main、部署、切8792仍等确认。跨进程恢复需另建持久化/身份/崩溃合同。

## 已验证
本轮：35ee既有全量收据条件校验exit0（未重跑）；原请求在35ee复现stack、邻枝干净068e2a46生成正确纠参反馈，44证据不变；邻枝相关24P。量具两正确方向exit0/交换期待各exit1/覆写exit2，0网络/模型/DB调用。旧214/44/90/6包逐文件hash一致，行情/导出未改。
旧35ee收据：11664P/81S/2X、前端107P、E2E34P/2S；不移绑文档/量具SHA。

## 踩过的坑
protocol起初读CLI90s，首发前另写amendment纠正为Workbench max600s/40步；原件保留。环境LLM_TIMEOUT300s不等于实际Episode75s。扫描首封exit1的6词形为代码，精确核销未决0，不称全包零命中。后稿包含原稿也不能清复核债，附注不能撑空稿。
