# 研究答案保留｜2026-09-18

## 这个分支做什么
同任务安全分析遇普通质量/格式问题仍保留；展示不等于核验通过。

## 决策与被否方案
- Mapping只在JSON边界投影，不全局解冻/default=str，不猜缺end。
- 终态claim管完成/取消归属，publication管消息/产物完整；不挪claim、不sleep刷绿。
- 精确run/conversation/message发布事件后重读产物，UI/SSE/probe再收口；不猜跨进程稿。
展开：`docs/handoffs/2026-09-18-publication-repair-blocked.md`。

## 当前状态
Mapping已纳入365627fd；发布修复49fd8d72＋静态产物7a9380bd已提交。新量具18c7c7fc。
**干净7a9380bd全量1红，修复版GLM首发0/重发0/续问0**。没有prepare/新协议/数据复制/服务启动。旧5f与35ee两次live均not_passed不改判。
R=`~/.finance-runtime/reviews/research-publication-live-20260918/`，341文件封存；目录名live不是已发题。8792身份/启动器未变，8849/8851/8852不监听、无锁；未push/合main/部署。

## 未验证 / 已知边界
新阻塞：`test_rag_worker.py::test_warm_worker_survives_first_timeout_and_drains_the_late_response`。真消费者＋OS管道确定复现：旧响应丢弃后，新响应留在TextIO预读缓冲，select只看空内核管道→误超时/杀进程。RAG生产代码未修；不把诊断逐字节reader直接上线。
自然纠参/拒收候选保留/金融质量/独立QC未验。候选仅同进程；旧失败用量与durable tools_pending不一致未补，未resume。在线KB/web非冻结，非严格A/B。

## 下一步
1. 单独修RAG按行读取，覆盖合并/半行/UTF-8/EOF/旧ID排除/绝对deadline与连续超时；勿只加时限。
2. 新精确干净revision四叶通过，再更新/审查R内未执行control.py，冻结一次GLM协议。旧样本不重发。
3. 合main/部署/切8792仍另等确认。

## 已验证
7a9380bd：11686P/1F/81S/2X，前端115P，E2E34P/2S，ruff/registry绿，all_green=false；收据`20260918T153933Z-7a9380bd.json`校验exit0只证环境版本。原件44证据/参数不变，保稿回放过；四撤保护各红→恢复绿。18c7干净RAG量具exit0表示缺陷复现，不是修好。
旧365627fd全量11674P但E2E33P/1F/2S；49fd构建弄脏树后Python主动中止，不当全绿。旧214/44/90/6/82及296/338包逐项hash一致。

## 踩过的坑
前端构建改受跟踪static，要提交后再验；收据校验绿不等于pytest绿。首扫词形命中精确核销未决0，不能称零命中。probe保留原失败不改判；GLM已授权，不再等GPT钥匙串。
