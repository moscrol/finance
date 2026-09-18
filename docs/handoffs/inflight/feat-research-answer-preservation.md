# 研究答案保留｜2026-09-19

## 这个分支做什么
同任务安全分析不因普通格式/质量问题整段删除；保留、准入、核验与交付分账。

## 决策与被否方案
- Mapping只在JSON投影边界复制；终态claim与publication分离，不挪claim/不sleep。
- RAG用非阻塞字节读＋显式换行缓冲；不加timeout，不用诊断逐字节reader。半行首次放弃保留，新进程清状态。
- 自然重写不算系统保稿，同源judge通过不代签金融质量。
详见`docs/handoffs/2026-09-19-rag-framing-and-glm-live.md`。

## 当前状态
修复20939b18已提交，**干净完整工程全绿**。隔离8849新GLM首发1/重发0/续问0已结束：run=`run_20260919_002806_645542`，completed/published，2137字公开答案、报告partial。但**整体not_passed**：系统保稿未证明，正文存在可核对质量问题。
R=`~/.finance-runtime/reviews/research-rag-framing-repair-20260919/`，423文件封存。服务PID34684已停，8849/8851/8852不监听、无锁；生产bf662e9310ff/启动器/行情未变。未push/合main/部署。

## 未验证 / 已知边界
- turn13含未转义换行的JSON→not_json_object，candidate=None/retained=0；turn14模型自行改格式，draft2096→2094字仅两替换、绑定/refs不变。不能称机制保稿成功。
- 作者审查：E1双红均值12/13/8却写下限12；终点正收益外推区间无下跌；PCB/PCB概念与D4/题材热度口径未解释；未校准阈值。产品judge passed是同源自审。
- 缺entity_codes后补全有compute结果，但4次find_analogues窗口错误没修好。原缺end未触发；主Episode无kb_search，RAG双响应只离线压到。
- 候选/发布跨进程恢复未实现，旧失败用量/durable未修。KB/web在线未冻结，非严格A/B。旧两live仍not_passed。

## 下一步
1. 用封存turn13单独设计畸形格式候选保留，安全/身份门不撤；不要把诊断strict=False或任意截JSON直接放进准入。
2. 历史窗口纠参、统计外推、同名多口径分开修，不删全文掩盖问题。
3. 再有修复需新精确门禁＋新的有界live授权；本样本不重发。合main/部署仍另确认。

## 已验证
20939b18：11703P/81S/2X，前端115P、E2E34P/2S，ruff/registry绿，收据20260918T162610Z-20939b18。69项定向、六撤保护均承重，旧44证据与保稿回放过。真模型14轮、16工具=11结果+5错误，97旧证据hash保留至122条。公开7产物hash/身份匹配。

## 踩过的坑
首次审查误把私有episode要求进公开列表，exit1保留后纠正；扫描14词形核销未决0≠全包零命中。旧全量/旧live失败不翻案，工程收据不移绑文档tip。
