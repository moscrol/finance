# 58b78542：历史参数纠错的工程验证，不是四题业务通过

被测提交：`58b785421195da707a74e1fe84fb59570f04b91f`。运行代码来自 `a05b3483`，后一提交仅更新工具饥饿遥测测试的诊断预期及对照断言。独立工作树 `~/fwp-wt-history-market-anatomy`，分支 `feat/history-market-anatomy`，WIP #783。

## 裁决

| 层次 | 本轮结果 | 不能外推 |
|---|---|---|
| 完整工程检查 | 四叶均退出0；测试前后同一SHA、`dirty_after=[]` | 不等于真模型自主纠错、正文正确或独立人员QC |
| 脚本化真实Episode | 参数失败→收到具体诊断→修正参数→实际临时DuckDB查询/RunStore原件；两条链通过 | 消费者是脚本模型，不能称为真实大模型研究验收 |
| 门禁变异 | 四个独立进程内变异均触发测试断言失败；产品文件哈希不变 | 不证明穷尽所有泄漏或模型失败形状 |
| 真实四题 | **本轮未重跑；最近一次fbd8f2a6整组仍失败** | 工程变绿不能覆盖旧原答、不能升级为merge-ready |
| 发布 | 未合并、未部署；未改生产行情库/画像/每日链 | 不宣称候选已在8792运行 |

前次完整业务拒收见 [fbd8f2a6裁决](../fbd8f2a6/acceptance.md)。本轮只修诊断到达与市场类型错误反馈，未修接力解释、异窗排名、启动特征/控制组和跨轮研究输出合同。

## 修复与被测边界

- `research_tool_registry.ToolDiagnostic`：冻结的程序反馈类型。finance_query 参数校验/超时/取消/超限/执行失败走此通道，在事实日期过滤后交付，并标记“非市场事实”。不产生E编号、不扩大授权日期。
- `finance_query.validation_diagnostic`：只渲染受支持的校验消息及schema字段角色；字段/数据集标识符限制格式，未知异常不原样回显。类型本身不是自动可信认证，构造者仍须经代码审查；错误状态、空evidence、模型自传diagnostic都不是放行依据。
- 混合结果的未知/早于授权/晚于截止事实与原prose仍过滤。授权终点晚于cutoff也不能提高截止；诊断不恢复被剔除内容。
- market类比缺精确代码、`000001.SH`配sector/stock、特征不匹配，分别提供可行动反馈。不根据代码/特征暗中修改`entity_kind`，兼容合法sector默认值，不更改计算公式。
- 新增测试 `tests/test_history_tool_diagnostics.py` / `tests/test_history_argument_repair.py`；遥测测试比较无sink/正常sink/失败sink的模型输出一致性，防记账改变主结果。测试库字节保持不变；没有因此宣称整个live进程有OS级网络隔离。

## 固定版本收据

- Python/Ruff：**11531 passed / 81 skipped / 2 xfailed / 17 warnings，494.49s**。
- 前端：lint、typecheck、8文件107测试、build均通过。
- 浏览器：34 passed / 2 skipped，约1.1分钟，隔离测试服务而非真人研究交付。
- 注册表：五项退出0；反向台账仍98条存量warning。
- pytest正式收据：`~/.finance-runtime/test-receipts/20260918T071557Z-58b78542.json`，八项校验通过，复制在 `python-receipt.json` / `receipt-check.txt`。
- 解释器：`~/finance-workspace-private/.venv-workbench/bin/python`（Python3.12.13）；清理launcher环境、umask022。本机依赖不是workflow固定容器认证。
- 运行根：`~/.finance-runtime/history-diagnostic-58b78542-checks/`，runner已结束；浏览器测试端口18891/18894已无监听。`ci-receipt.json`逐叶记命令、退出码和日志哈希。
- `manifest.json`记录归档文件来源/大小/SHA256；原运行日志没有覆写。

### 保留的正常回归失败

`a05b3483`首次四叶Python为 **2 failed / 11529 passed / 81 skipped / 2 xfailed**。两个失败位于 `intelligence/tests/test_tool_hunger.py`：期待旧的未分型错误文案，而新输出多了“工具诊断（非市场事实）[invalid_query]”。其他三叶通过。

`58b78542`更新预期并增强sink对照，不改产品运行代码；再完整跑四叶才得到上面的全绿。旧日志和收据留在 `previous-a05b3483/`，不是删测试、跳过检查或沿用旧绿。提交前808P/12S、随后49P仅为过程证据，不代签固定全量。

### 四个反向变异

命令：`<PY> scripts/review_probes/history_diagnostic_mutations.py --output <全新目录>`。

1. 吞掉typed诊断交付→字段角色提示断言失败。
2. 诊断一出现就绕事实门→无日期/越授权事实与prose泄漏断言失败。
3. 原始未知异常直接成为诊断→禁止正文泄漏断言失败。
4. 根据代码静默推断market→必须拒绝缺类型的断言失败。

原始失败日志在 `mutations/`。这些是故意改坏内存函数的收据，与正常全量失败分开；测试setup/import错误不计为抓住。脚本以源码哈希证明未改文件，测试仍使用临时数据库，不是“不读任何数据库”。

## 为下一小片保存的排查线索

`saved-task-contracts.json`只读提取旧fbd8四轮原件并保存源哈希：四轮均`comparison_analog`，required为direct_assessment/counterpoint/evidence_boundary；第四轮另有非required的volume_qualification与volume_step_trajectory（近5日）。这提示需审输出合同，但不是“公司矩阵已覆盖合同”的根因证明。

下一步先测接力成熟性/确认/缺数的实际模型投影与正文消费、同窗及各自启动时特征、跨轮原件读取。之后再冻结新版本、四叶、新隔离根原四题；保留所有旧失败，不重复运行挑成功。
