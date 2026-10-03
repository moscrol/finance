# 工具目录去重：小样本模型A/B启动预测

R-20261002-14；代码fd65a3f48；基于PR16，不是main。R13工程帽0已另结案，本批独立。
本文件在模型调用前冻结，结果必须另文件；私有plan.json/cases.json/driver.py另有SHA。

## 问题与预测

同一GLM模型、同题、同冻结数据及名义预算，只改变重复目录文本；A关闭、B开启。
不按强弱或题型藏工具；本次合同两臂都只授权原生只读finance_query，保留其完整schema和整个数据集菜单。
本轮不是通用工具发现/选择测试。native GLMAgentRuntime不等于完整8792入口，也不是正式四格。
已验证原生装配首请求B能少7929 UTF-8字节；无工具/变更菜单则不压缩。
预测同等完成质量、无新增轮数时输入token可下降；字节不是token，不预签时延或质量收益。

## 冻结样本与资源

模型只有glm-5.3-flash，显式override，真实响应身份严格准入；另一个模型未验证，不标定强弱。
两个实施者选取、未做模型调试的题，不是独立盲测：

1. control：给出2026-09-30日度原生FinanceQuery证据后，问全市场涨停家数、跌停家数与差额；无需补工具。
2. retrieval：不给预取，查询2026-09-29同三项统计。两题都要日期/来源，不要投资判断。

真实冻结DuckDB只读，先用原生FinanceQuery取真值，不手写SQL、不捏造工具。
控制题52/10/42；查询题57/11/46；查询题真值仅评测端保存，不交模型。
输入问题与query/evidence全量见私有cases.json；DB SHA71c03b7ea8d9c5d5effe41bdc2f089c52d7b846dce97bd6362c02dee1213c023。

固定顺序control-A、control-B、retrieval-B、retrieval-A，各一次；无选优、无关闭重开。
单题70秒、每次模型30秒、3工具步，最多4物理HTTP/题，总16；批墙钟600秒，启动间隔至少90秒。
保留原生有限重试且每次算物理帽；不得加试。身份不准入或driver异常即停止其余格，不修后重跑。
模型帽是上限不是目标，未执行格保持缺失，不填成功。旧累计物理请求96。

## 审计与判据

两臂均同步fsync并读回原始/实际请求收据；原生序列化body.messages/tools与收据相等才能发。
每物理HTTP先预留落盘，保存body、响应原文/usage/model或失败类型；不落key/Authorization。
保留全部outcome/events。身份用PR14现有只读checker自动核验，checker源码哈希也冻结，不把配置回填model。
私有driver四格断网预取/发包截获已做；帽4/16、错误模型和准入0/1/2自检，无真实网络。
两臂相同持久记录类别；观测总耗时包含审计开销，不当作生产性能。

按完整最终答案人工核对日期、涨停/跌停口径、三项数值、单位、来源引用及无无据扩写；
分别报告native状态、全文判断、物理请求、工具调用、恢复/失败、逐HTTP的usage与总耗时。
引用可解析/native completed都不能代替全文正确。任何逐题退步反驳本批无退步预测；
仅两题即使同质量省token也只记限定观察，不宣布通用PASS；不以两题证明强侧不退步。
无身份或缺格则inconclusive，保留已执行的坏结果，不因剩余格缺失掩去退步。
无统计显著性、无独立评审、无完整P/薄R、无真实用户、无合并部署；正式四格仍先于240。

Hashes：
{
  "id": "R-20261002-14",
  "product_commit": "fd65a3f48f2a4a8ed9cc80f59c40f1137f90814d",
  "model": "glm-5.3-flash",
  "max_physical": 16,
  "per_case_physical": 4,
  "batch_wall_seconds": 600,
  "per_case_deadline": 70,
  "per_llm_timeout": 30,
  "tool_steps": 3,
  "start_spacing_seconds": 90,
  "order": [
    "control-A",
    "control-B",
    "retrieval-B",
    "retrieval-A"
  ],
  "driver_sha256": "e646ca6cfcd7107debc0293aebc346e56c2dac3d48ccf7d19933371ddf780170",
  "cases_sha256": "d13d6f09e77b8dff9179b053f47cea9c1f8f26650f68765d5c43305c31ceaf98",
  "data_manifest_sha256": "d95e69a45617c727b093f7ab5f5160736e6522916333014dfa0af652493de1bb",
  "admission_sources": {
    "/Users/a77/fwp-wt-semantic-consistency-1001/scripts/check_model_admission.py": "690d6c50374458e8d1e6b340e620797bca2b6e7b148ca8835f2f50577e29c3db",
    "/Users/a77/fwp-wt-semantic-consistency-1001/intelligence/eval/model_admission.py": "8c25053df50f973a01a54babdc9c2fa2662a1b30db43ed05bedbb5fe7f7f9a21"
  },
  "classification": "small diagnostic pilot, not formal 2x2 or independent blind evaluation",
  "stop_on": "identity not admitted or driver exception; no restart; all failures retained",
  "scope": "GLM preservation_e2e; native core runtime only; no production factory changes"
}
