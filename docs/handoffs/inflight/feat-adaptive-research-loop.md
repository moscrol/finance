# feat/adaptive-research-loop 在途

## 这个分支做什么
#72/PR #868，#75双轴独审及#76 L6。WIP，不合入、不部署。

## 决策与被否方案
- 明确货币字段换算，否决裸数字泛化；身份归控制器，拒绝模型注入而非宽松归一。
- 下一题必须等精确Episode内容审计PASS；completed不等于质量合格。
- 旧失败批不可续跑；新准入红也不重跑洗绿、不扩大预算。
- 详见 `../2026-09-23-adaptive-repaired-verification.md`。

## 当前状态
前向main626d8a508后，三修复已提交ac11027fa：金额单位、阶段身份、题间审计屏障。未push/合/部署。
新批已结束并归档：`docs/verification/2026-09-23-repaired-qc-and-l6/README.md`。
#75共65请求，Spec PASS_WITH_LIMITS、Quality BLOCKED_INCOMPLETE_EVIDENCE；宿主总态BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE。两轴均有终稿但覆盖不足，不能合。
新L6因严格deadline越窗与检索就绪超时停止，首发0/0/0、模型0、旁车0；自然质量NOT_EXERCISED。旧L6误删失败仍NOT_PASSED。
私有根 `~/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/`、`pr868-l6-repaired-20260923-2118/`，均不可续跑。干净候选检出/绿测试临时目录已清，日志与失败数据保留。
PR868评论6498、852评论6500及WIP阻塞标题已回读；远端head重查超时，不声称当前远端代码已同步。

## 未验证 / 已知边界
两轴作者测试/必红控制未跑；Spec C3/C5/C6未验及C2第五调用点缺覆盖；Quality取消探针异常类型未裁决。三修复的完整独立正确性覆盖未闭合。
严格body_stall输入0.8s、容差0.2s，实测1.378s且HTTP请求0，不能推断上游停滞；RAG离线120s超时亦未定位根因。高负载不能作免责。
新题间屏障仅离线验证；自然修订保真、迟到判官未验。当前完整/联合main门禁未跑，历史全量7ad61a0d3不移签。

## 下一步
1. 新证据根诊断两项准入阻塞，完善独审有界覆盖与必红对照，不改已封存交付。
2. 按新协议另开受限#75/L6；不补旧题、不续旧批、不以机械PASS代自然验收。
3. 合前完整门禁、最新main联合树和用户确认仍必需。

## 已验证
ac11027fa干净定向328P/0F，指定revision收据可采信；全仓Ruff/diff check过。原件金额正反例零网络通过，原hash不变；题间失败反例下一题请求0、PASS允许继续。
499份原件归档/密钥扫描；751冻结文件与生产七身份不变；19897/19898/19899释放、进程退出。main626d8a508合入预览无冲突，非联合测试。

## 踩过的坑
审查脚本exit0可含失败子项；探针脚本数与子项数不加总。harness-reference/BUILD.md有他人改动，未碰。
