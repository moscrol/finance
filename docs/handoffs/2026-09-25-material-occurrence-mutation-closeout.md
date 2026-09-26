# 2026-09-25 材料重复句撤保护验证续轮

## 背景与范围

接用户继续推进，完成上一轮因资源条件未运行的两组变异验证。只处理本地候选；原#877八问方向、基期、库存性质和盈利前提失败不因本次离线验证翻案。未push、开PR、合main、部署或增加付费请求。

应用修复仍为3198df4964f3fc52fff7488b17763955ba15e4f2；本轮只修改变异定义的测试选择器，提交a99fc9c9090814dba897f93e2f1e25d48e904b9d。`git diff 3198df496 a99fc9c90 -- intelligence/services/material_claim_review.py intelligence/tests/test_e2_material_claim_review.py`为空。新收据绑定a99，不重签3198的历史收据。

## 发现顺序

1. load1=7.17、另一执行者pytest=1时准入首次变异。固定3198基线57P；第一组撤保护执行0项、pytest exit5，运行器拒收并保留complete=false。旧定义将完整node ID放进targets，而运行器按`pytest -k`名称表达式执行，因而全部取消选择。这是本轮定义错误，不是有效验红或产品缺陷。
2. 与已有episode_writer_mutations.json合同对照，将五处完整路径选择器改为测试函数名，不扩改共享运行器。提交a99，hooks通过，应用及测试代码未变。
3. load1=4.88、无其他pytest时，在新独立固定树运行a99两组变异。基线57P；撤销未消费索引检查5F、恢复5P；撤销一次匹配后的break为7F、恢复7P；最终57P。全部零收集错误、零跳过、零超时。两次源文件SHA256恢复一致，最终树干净，运行器清理自己的成功临时树。
4. a99干净候选重新执行相同21文件定向回归：736P/4S、collected740、0F/0E。四跳过是已有同类引号排除。正式收据校验exit0。

## 原始证据

根目录：`~/.finance-runtime/reviews/pi-closeout-execution-20260924/material-occurrence-0925/`。

- `mutations-3198.log`、`mutations-3198/results.json`：首次选择器错误原件，complete=false；不要覆盖或当成有效变异结果。
- `mutations-a99/results.json`：六次子运行、两组变异hash、固定revision及complete=true；同目录JUnit、进程记录、diff和完整日志。
- `regression-a99.log`、`regression-a99.xml`：736P/4S；`receipt-check-a99.log`：正式身份/环境指纹/目标核验通过。
- 定向收据：`~/.finance-runtime/test-receipts/20260924T164630Z-a99fc9c9-03e233816b71.json`。

## 决策与被否方案

| 选择 | 否决方案 | 原因 |
| --- | --- | --- |
| 修正本轮定义为运行器既有名称合同 | 改运行器接受新的node ID格式 | 既有定义已经采用名称；本轮错误不需要扩大共享行为 |
| 新提交重新验、原件保留 | 用exit5冒充撤保护红、覆盖第一次证据 | 变异必须真的执行且出现目标断言失败，非零退出不是充分条件 |
| 应用hash一致与新SHA验证分开记录 | 把3198的736P改签a99 | 提交身份不同，新提交有自己的回归与变异证据 |

## 仍开放

独审、新自然问答、全量Python、前端/E2E与registry整套准入未做。现有共享解释器httpx0.25.2与锁0.28.1不一致，未更改环境；收据只证受验环境一致，不证锁文件合规。边界声明及同文删句后的完整来源追踪未扩修。

工具盘点：复用已有变异运行器、回归与收据门禁；其零执行拒收已经挡住本次定义错误，不新增另一套运行器。后续独审应审应用3198与选择器a99，真实验收仍须另固定组合和授权。
