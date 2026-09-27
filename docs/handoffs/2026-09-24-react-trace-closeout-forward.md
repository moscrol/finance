# #81 本地前向候选与冲突验证

## 背景

用户要求将09-23会话的尾项列成TODO并依次推进。#832产品头27034ce44与main a54fed0d有两个冲突文件，#892保存旧独审原件。本轮只在新树`fwp-wt-react-trace-closeout-forward-0924`整合，不修改原作者树、旧原件、#832远端head或生产服务。

## 按发现顺序

1. Git对象层预演发现`historical_research/episode.py`与`test_history_model_projection.py`冲突。
2. 追溯101678e89：主线保留原件行坐标、可见分块的结构化数值、完整分母与next_offset。追溯d1b30e1a0：补查仍保持原窗口，reader先成功投影再登记成功；投影异常不得污染history_results。
3. 解决冲突：完整分母继续传scope_observations；保留main的next_offset说明和双方共有的保持窗口约束；保留分支的投影失败回归。分页参数化测试补验结构化total_matched/returned_count。
4. 首次新增断言以完整标题相等过滤，但真实标题附有查询标识，导致6F/374P。修正为匹配该标题前缀后380P；这是本轮测试写法错误，不记成产品故障。开发红收据20260924T125837Z-a54fed0d-75cff19bf119.json保留。
5. 合流提交f051f28d4，干净固定提交复跑380P；随后3629e19e2仅加入两项变异定义，复用既有run_extraction_mutations.py，在独占临时树撤保护并恢复。

## 方案比较

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 冲突全取分支版本 | 会丢主线结构化分母，模型正文存在却失去机器可核验的数量证据 | 否 |
| 冲突全取main版本 | 会丢掉失败分页不登记的回归与相应执行顺序 | 否 |
| 按双方原始意图合流并验证 | 两项合同兼容，不需要发明新行为；在分页实际出口验证 | 采用 |
| 只看正常路径通过 | 不能证明删除关键接线时测试会失败 | 否；增加两项正式变异定义 |
| 再开付费审查或直接升级#832 | 原独审仍缺证据，不能把通用推进当无限重试或冒名接管 | 否；保留本地候选与独审待办 |

## 收据

解释器均为主树`.venv-workbench/bin/python`。

- f051f28d4：全仓Ruff通过；7文件380P，收据`~/.finance-runtime/test-receipts/20260924T130052Z-f051f28d-b3d08fe306e9.json`，不是全仓Python。
- 3629e19e2：变异基线28P；删scope_observations为6F，恢复6P；提前登记成功为1F，恢复1P；最终完整投影模块28P。所有红均为AssertionError，零收集错误、超时或跳过。
- 变异证据根：`~/.finance-runtime/reviews/pi-closeout-execution-20260924/react-trace-3629e19/mutations/`，含results.json、逐项进程收据、JUnit、diff与指纹。成功临时树由现有runner移除，不涉及他人树。
- 定义：`scripts/review_probes/history_projection_forward_mutations.json`。复跑时显式`--definitions`并指定`--tests tests/test_history_model_projection.py`；不复制runner。

## 边界与下一步

本地工程验证不能替旧0304批次的Quality C3/C5独立动态证据签字。新组合尚无全仓Python、前端/E2E、真实自然金融验收，不宣称可以合并或部署。先按原工单补齐有界独审的准入与授权，再为实际候选排完整工程；未来main改变仍须重核组合。没有模型调用、push、PR更新、main合并、写生产或部署。

工具盘点：两项变异已进正式定义并复用现有runner；合并意图取舍需要语义判断，留本文而不造自动择边工具。旧报告措辞不拿来替当前原始收据。
