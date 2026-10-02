# 第20号资源政策与比较器整改：工程验证结果

R-20261002-12；独立分支 `fix/resource-profile-contract-1002`，基座 `19c820824`。
启动预测 `2026-10-02-resource-profile-contract.md` 不追加结果；本文件只记事后事实。
本地工程预测限定 confirmed，**不是模型效果、泛化、完整四格或合入验收**。

## 实际修改与取舍

| 选择 | 没做什么 | 理由 |
|---|---|---|
| Controller 恢复第20号前字节一致版本，移除 profile 消费 | 不全面重写旧路由，不宣称已开放通用任务修订 | 最小撤销新添的档位语义分权，避免把修漏洞变成未验证架构改造 |
| `FWP_RESOURCE_PROFILE=standard/expanded`；旧名字仅作资源别名 | 不依 served_model 自动选档；不保留未消费 escalation 字段 | 资源与模型身份/语义解释权分开；标准预算不变 |
| 明确旧 agent 循环与 KB 有资源消费者 | 不擅自将8步接到 Workbench Episode | Episode 仍由研究 tier 决定；不能为“接线完整”扩大预算 |
| 分数比较器 FAIL / INCONCLUSIVE / 输入错误 | 不输出 PASS/WARN；不建议只给弱侧启用绕过回退 | 布尔分数没有完整答案、身份、成本、留出与可比资源证据 |

新配置存在但为空/未知时保持 standard，不能落入遗留 frontier；不新增授权能力或产品入口。
比较器四臂同一非空题号集合、严格布尔、拒重复JSON键；summary计数需一致，不能混用两种格式。
任一题回退不允许被净分抵消。两臂分数都改善仍只 INCONCLUSIVE / exit3。

## 按发生顺序的实际读数

1. 19c 原产品源码上新增契约：**25 failed，exit1**，失败留存。不是引用他人探针冒充自跑。
2. 第一次改后：115 passed / 2 failed。新 Episode 测试误以为没有工厂已有的能力地板，且两次复用
   仍存活的根任务ID。改测试为与未配置时的真实能力集比较，使用不同ID；没有修改权限或工厂。
   Ruff 的测试 lambda E731 改为 def。保留 `green-initial.log` 与 `fixture-correction.txt`。
3. 校正后定向117 passed；增加全空四臂、两臂同涨分、混合报告格式三个边界测试。
4. 最终相关回归 **383 passed / 0 failed，6.43秒**：profile/policy新旧测试、比较器、Controller、
   agent_research、KB三组及 Episode 工厂，共9个测试文件。全仓 Ruff 通过，软件 selftest 通过。
5. 最终源码做四项刻意破坏：恢复按frontier改变政策、布尔分数给PASS、允许全空、允许非布尔。
   **4/4被测试捕获**，每次恢复原字节；随后重跑383项通过。该变异只证明这些工程约束可被测到，
   不证明所有漏洞被覆盖或真实模型行为有效。

最终测试收据：`20261002T042130Z-19c82082-29e636417424.json`。收据HEAD显示基座19c，
因为测试时本分支修改尚未提交；不能把它说成未改动19c的绿。最终产品文件hash另存私有 `product-manifest-final.json`。末尾空行整理后已重跑4项变异和383项回归，前序日志也保留。

## 环境与证据边界

- doctor blocked：共享venv httpx实际0.25.2，lock要求0.28.1。未改共享环境。
  本地定向读数带此限制；干净环境全仓CI要另验，不移签旧全量读数，不称同SHA全量绿。
- code-map query为空/vault不可用，只按源码调用链确认上述消费者，不声称完整架构地图。
- 旧用户纠偏不变：本次恢复旧Controller只撤新增差别，**旧硬路由与可修订任务框架尚未整改完**。
- 工程批次真实模型请求 **0/0**；旧累计96物理请求不变。未启动四格、240题或新的模型批。
- Codex owner工作树未被本次编辑；PR14/15、关闭的R10/R11没有改写/重开。未合并、未部署。
- 这不是质量收益；下一阶段另冻结单一通用接口候选，保留未见题/足够信息控制，计额外往返成本。

私有证据根：`~/.finance-runtime/resource-profile-contract-20261002/`；计划、RED、初次失败、
校正与最终GREEN、变异、doctor和map日志全部保留。产品说明见 `docs/runtime/model-tier-harness.md`。
