# 资源profile工程整改在途

## 这个分支做什么
在feat/harness-opt-1001@19c上修第20号，不编辑Codex owner树，不夹带PR14/15。

## 决策与被否方案
| 选择 | 否掉 | 原因 |
|---|---|---|
| 共用Controller政策 | 按强弱分配解释权 | 资源不是语义权限；这里只撤新增差别，旧硬路由尚在 |
| 中性standard/expanded | 自动按模型名选档 | 只保留旧循环/KB资源；不扩Episode预算 |
| 局部分数比较 | 布尔分数PASS、净分抵消回退 | 缺全文、身份、成本、未见题证明 |
展开见 `../2026-10-02-resource-profile-contract.md` 与 verification同名-results报告。

## 当前状态
产品07a2879b7已提交；R-20261002-12本地工程限定confirmed。
PR16@da86：registry/frontend过，e2e 31P3F2S，Python仍运行。合入blocked。
19c/da86同一ASGI后端缺口已复现；详见verification同名-ci报告，不将红改绿。
下一通用界面候选未实现；模型批0请求，旧累计96，R10/R11不重开。

## 未验证 / 已知边界
共享venv httpx0.25.2不符lock0.28.1，不改共享环境；本地读数不能充干净全仓验收。
Workbench预算仍来自research tier，未做完整8792真实行为或正式模型×引擎四格。
code-map空，只按实际消费者判断。旧规则未都改成可修订假设。

## 下一步
查CI 36964386458的Python结果及后继HEAD检查；保留e2e红，不移签旧绿。
另树单因素设计：短目录+按需schema+可展开授权能力；同模型同题同数据可比预算。
计渐进展示额外往返，保留未见题及信息已够控制；四格先于240，不合并部署。

## 踩过的坑
新增Episode夹具误认能力地板且复用存活task_id，首次115P2F已保留；改夹具而非权限。
预测与结果分文件，不向启动预测追加结果；claim R12已用，不能重复claim。

## 已验证
25RED；最终相关383P；四项变异4/4捕获；全仓Ruff及提交hooks过。
证据根 `~/.finance-runtime/resource-profile-contract-20261002/`；不是模型质量收益。
