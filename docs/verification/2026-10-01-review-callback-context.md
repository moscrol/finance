# 日期上下文的回调调用方式一致性（R-20261001-16）

## 事前范围

用户要求连续推进现有阻塞。检查D原始判官输入已确认−17.24%没有漏传；该方向问题不能归咎于投影，也不能靠其他子主张导致整句删除来判检测成功。条件句“两日”与“未来连续两日”语义不同，不通过新增字面豁免凑绿；这两个问题单独保留。

本单修复一个已定位的独立接口漏项：R12添加的runtime_context在完整request回调和真实HTTP中存在，但_call_flexible的**kwargs/命名参数白名单未包含该字段，导致同一输入因注入方式不同而丢失上下文。真实R14 HTTP证据不受此漏项影响，不挪用本单测试证明D修好。

## 修改前预测与验收

只补回调分派的runtime_context字段：支持完整request、命名参数、**kwargs及已有位置别名方式的对应传递；只传已经投影的日期对象，不另传ResearchRunContext或任意原始私有字段。字段缺席保持缺席/可选默认；要求必需runtime_context而其缺席时明确报错，不能把整个request误当日期对象。旧回调不声明该字段时不能收到意外参数，内部TypeError不得吞掉重试。

先红后绿，覆盖实际verify到回调、缺席/跨请求、白名单、旧签名、内部错误、真实HTTP首请求不变。当前定向与全仓/CI按实际受验SHA另记，不能借R15全量给新代码背书。

本单不改judge提示词、日期投影值、机械数字规则、生产默认或模型预算。新增模型调用0，不合main、不部署。

## 阶段结果

9新增用例先7失败/2通过；补分派后9通过，相关11文件744通过/5.49秒。覆盖实际verify到request/命名/kwargs回调、跨请求缺席不复用、日期白名单、旧签名、必需字段缺席拒绝、已有必需位置别名及内部TypeError不重试。Ruff首次发现新测试分号风格问题，已修正，没有改变断言。

离线重新生成完整首HTTP JSON，与R13新组实际首请求逐项相等；本单不改变真实模型提示/请求。新HTTP调用0。全仓与CI须按提交后的受验SHA记录；当前partially_confirmed，仅定向通过，不挪用R15全量。证据根 `~/.finance-runtime/review-callback-context-20261001/`。


## 提交后同版本结果（已完成）

受验实现 `8dd20f49d4a49c0cd55d75054639a08678308f73`，提交后干净树744P/5.21s，收据 `20261001T090646Z-8dd20f49-6ab9ba68d681.json`。

独立detached Mac树全仓：**19150P / 75S / 2xfail / 17warnings，1055.41s，exit0**；19227收集、0 failed/error/xpass，前后clean，无ignore/deselect/k/mark筛选，依赖门未绕过。收据 `20261001T092424Z-8dd20f49-176ec8902cfc.json`，JUnit与日志同私有根。

队列7385行/hash不变、main仍3a2718c6、生产healthy@2c394978且code_matches_repo=true，冻结DB hash/大小/0444不变。新增模型0，不合main不部署。

8dd关联CI五检查全部成功：workbench run36840541076的python/frontend/e2e/workbench-check，加registry run36840541227。CI Python **19058P/167S/2xfail/9warnings，1512.86s**。

CI实际checkout为自动PR测试提交 `e6d1e61088d388581e525ca18d171352d80d72c3`，不是字面8dd；GitHub commit API核实父含8dd，完整tree均为 `36903e76668b4bef9786dcd94dfa2ae218233735`。证据 `ci-python.log` 与 `ci-tree-equivalence.json`。只是自动测试树，不是实际合并。本单据上述证据confirmed，后续文档提交不冒称新实现验收。
