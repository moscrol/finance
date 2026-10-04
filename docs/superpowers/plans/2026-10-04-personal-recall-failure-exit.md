# 个人回顾仲裁失败出口实施计划

Goal: 阻止未经语义确认的个人回顾请求继续执行另一任务；沿现有失败终态保留原题和可重试提示。

Architecture: 不改controller语义规则、TaskFrame字段或仲裁预算。Workbench在decision交给后续计划前消费已有personal_recall_*失败标识，保存失败trace，使用既有_fail出口；成功true/false全部保留原路径。即使混合请求失败也不靠猜测降为纯记忆。

Files: intelligence/runtime/conversation_orchestrator.py；新增intelligence/tests/test_controller_failure_http.py；产品门文档和后续规格/交接按实现同时更新。

1. 新HTTP回归使用真实Controller和QueryResolver；provider边界合成。所有用户/Episode/数据库/Wiki/index/缓存/待重判/部署账本指临时根，socket拒绝。分别注入None响应、抛异常、超时（虚拟monotonic，不真实睡8秒）、空响应、非JSON、非布尔schema；纯回顾、含公司主体、混合任务参数化。
2. 断言run/message失败；原用户正文不变；内容是故障提示且无provider私有错误；仲裁≤1次，chat_with_tools与ask.answer_query为0；trace controller.failed保存原题/失败枚举，未落研究计划及Episode。失败后的追问无新错误turn_intent继承。先运行原头确认能抓到completed/错误正文/多余调用。
3. 在restricted_history的受信重编译之后、turn_intent和research_plan之前检查decision.llm_failure_reason.startswith("personal_recall_")。失败记录self._trace(..., status="failed")（raw_question、failure_reason、经redact的detail），text_chunks加入固定中文故障提示；raise RuntimeError("personal_recall_scope_unresolved")交公共except/_fail处理。避免给report写候选TaskFrame或会话保存候选turn_intent。
4. 原HTTP记忆交付与Controller/个人回顾全组回归，加普通finance成功false/true对照；Ruff。候选修复只声称故障下不偏题，不写模型能力收益。
5. 最终SHA独立Spec/Standards，完整本机与GitHub门禁；绿后合入备份。发布仍须内容质量准入，不抢PR30活动树。

计划约束：_fail的既有终态抢占、取消竞态与安全snapshot规则继续负责落盘，不另造状态机；原始trace保存枚举和有界脱敏detail，用户正文不暴露服务实现。若现有_fail不保存可读故障正文则在实施中按其接口最小修正，并用实际HTTP和artifact回读验证。
