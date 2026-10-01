# 基准复核观测包装层签名兼容（R-20261001-15）

## 事前范围

用户要求继续推进已定位的CI回归。本单只做离线兼容修复，不新增模型调用、不改日期投影、判官提示词、模型/预算/默认off，不改R14已经冻结并完成的实验版本或结果。

旧de0c52e8d的test_run_agent_runtime_benchmark.py有34通过；R12后同文件4失败30通过。全量GitHub run36828527701（46a79837c）也有相同4失败。最小复现：_SemanticVerifierCapture.verify(**kwargs)掩盖delegate窄签名，adapter将新增context透传给旧三个关键字的替身，触发unexpected keyword argument。不能仅修改替身让其吃掉context，或捕获TypeError后删参数重试来掩盖错误。

## 单一修复预测

使观测包装层对签名检查透明：暴露实际delegate的verify签名，调用仍原样转发，记录同一SemanticEpisodeOutcome。旧接口通过adapter时不接收未声明的可选参数；支持context的新接口及实际判官必须收到原context，不能为兼容旧接口把所有context都删掉。

仅修改scripts/run_agent_runtime_benchmark.py的观测包装层与相关测试；日期生产实现46a79837c保持不变。保留provider_attempts、latest、结果类型校验及异常原样传播。不得更改打分、完成状态或公共答案来让测试通过。

## 验收与停止边界

- 新增测试先红后绿：窄签名、显式context、**kwargs、嵌套包装、真实判官接线、provider_attempts/latest、错误类型及内部TypeError不重试。
- 原34基准测试（含4失败）全过；与原689相关回归一起运行，按实际数报告，提交后同SHA干净树复跑。
- 静态门禁；同SHA全仓离线测试与GitHub CI分别记录。局部通过不能当全量通过；运行中/失败必须明示，不挪用旧版本读数。
- 不新增真实GLM实验，不合main、不部署。R14三对证据只归b96980cee；即使兼容修复通过，也不自动解决D方向矛盾、条件数字误标、旧AB或PR8门禁。

## 定向阶段记录（当时全量待完成）

- 修改实现前：新12契约用例+原34基准用例共9失败/37通过；其中5个新增用例暴露签名/旧接口/嵌套包装问题，原4个失败重现。不是把所有新增测试都声称先红。
- 仅在观测包装层使用带functools.wraps的转发闭包，通过属性返回可调用对象，使inspect.signature跟随真实delegate；不剔除参数、不捕获重试TypeError，不修改真实判官/日期规则。
- 修复后相关10文件 **735通过/4.77秒**（新增12+基准34+原689）；原4个失败恢复。新接口context对象与真实判官日期字段均有保留测试，旧接口/嵌套、provider_attempts/latest、坏返回值/不可调用对象及内部错误不重试均覆盖。
- Ruff、diff检查通过。提交后须按同SHA干净树再跑735项并启动全仓离线测试/CI。这里是定向结果，不是全量验收。

定向阶段R15暂记partially_confirmed：本地兼容回归已修复，全仓/CI未完成前不记confirmed，不合并部署。R12原失败和R14受验版本继续保留，不能用此局部结果覆盖。私有证据根 `~/.finance-runtime/review-wrapper-compat-20261001/`，含red/green日志和前后核验。新增真实GLM调用0，本系列真实模型请求仍19。



## 最终验证与结案

**R15 confirmed：包装层兼容回归在实现a6cb22676上完成验证。** 不是只凭定向735项通过：

| 验证层 | 受验版本 | 结果 |
|---|---|---|
| 提交后相关10文件 | a6cb22676，干净树 | 735通过，14.76秒 |
| Mac全仓 | detached a6cb22676，干净树 | 19141通过、75跳过、2预期失败、17警告；1050.60秒，exit0 |
| GitHub Python全仓 | 对应a6cb22676的PR测试树，见下 | 19049通过、167跳过、2预期失败、9警告；1250.71秒 |
| GitHub五检查 | 关联head a6cb22676 | registry-check/python/frontend/e2e/workbench-check全部success |

Mac全量收据 `20261001T081839Z-a6cb2267-a194eb7e4192.json`：collected=19218，dirty=false、dependency_gate_bypassed=false，ignore/ignore_glob/deselect为空，keyword/markexpr为空，maxfail=0、last_failed=false，失败/错误0。前后工作树干净。定向收据 `20261001T080057Z-a6cb2267-dc4a0872b38e.json`。Mac与CI的跳过数量不同，分别报告，不把跳过/预期失败算通过；两者总数均19218。

CI工作流 [36833617920](https://github.com/moscrol/finance/actions/runs/36833617920) 和registry工作流 [36833618029](https://github.com/moscrol/finance/actions/runs/36833618029) 均成功。精确版本说明：CI checkout实际是GitHub为PR自动生成的测试合并提交 `5b99e3f13349dd6fdc8f040aade0779036a8bcf5`，不是字面上的分支HEAD；已核验其父提交包含a6cb22676，且两者完整Git tree均为 `8bd107c1e93393c5193c6c943645bb5cb4458777`。因此是相同受验文件树，不把check关联head误当checkout SHA。此测试提交不代表已合入任何分支。

最终隔离核验：队列7385行、SHA `edd22d9cd4694bdb405091540d3270e883e5471edcd76fb65eb89d0faaa525a8` 未变；origin/main仍3a2718c6；生产healthy@2c394978、code_matches_repo=true；冻结库3879743488 bytes、0444、SHA `71c03b7ea8d9c5d5effe41bdc2f089c52d7b846dce97bd6362c02dee1213c023` 未变。

私有证据补齐：full-start/full-result/full.log/full-junit.xml、ci-runs/ci-check-runs/ci-python-success.log、ci-tree-equivalence.json、postcheck-final.json及更新后的stage.json。原红测试、R12失败、R14三对原件均保留。本次结案只更新文档，不更改a6cb22676实现。

新增模型调用0，本系列仍19请求；不合main、不部署、不改默认off。R12原版本仍记partially_confirmed，其4项兼容回归由R15后续修复解除，不反写原失败。R14三对的日期收益仍仅归b96980cee；D方向矛盾、条件数字误标、旧AB与PR8内容门禁未被本次CI成功解除。
