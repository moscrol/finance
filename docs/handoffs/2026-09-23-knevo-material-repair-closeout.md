# Knevo 材料入口修复最终证据

## 结论与身份

入口修复已验证，完整语义交付仍未通过，PR #877 继续 WIP。本文接续阶段快照 `2026-09-23-knevo-material-entry-repair.md`，不覆盖旧失败原件。

| 证据层 | 固定身份 | 能证明什么 |
|---|---|---|
| 修复代码及隔离 live | `f1fd8aa1a16bea4f3dd4e2ba0e5fd92114aea2c6` | 干净启动、实际材料入口与同题公开交付 |
| 定向回归 | 同上 | 580 passed、4 skipped、0 failed，Ruff通过 |
| 完整工程候选 | `8aadc23d4873251ffb3b0ecf4f9355f111ba6253` | 完整Python、前端、registry检查的实际受测版本 |
| 本文及同次交接提交 | 上述候选之后的纯文档提交 | 留证与指针更新；未另跑全仓或live，不移签 |

工程测试树 `/Users/a77/fwp-wt-knevo-closure-0923`；前端独占树 `/Users/a77/.finance-runtime/knevo-absorption-20260923/frontend-checkout`。两者收据均为同一完整工程SHA、dirty=false、前后身份稳定。主检出树及其他agent工作未接管。

## 发现顺序与真实复验

入口修复后，以独立用户、用户根、Episode根、数据根启动隔离Workbench，模型 `continuous_glm / glm-5.3-flash`。health的源版本为f1fd、source_dirty=false；生产8792未切换。12题全部结束，隔离服务已停止，未自动重试或修改冻结题面。

所有12题均有私有Episode，原始问题仅存在末尾空白差异，材料范围均为material_only、授权工具为空、Episode工具请求为0；三包均完整保留answer_q1至answer_q8。材料权限合同与题型是两个维度：Q14为news_impact，但没有恢复工具能力。装配探针中的受测resolver/先验/预取/网络请求为0，不等于证明整轮所有IO都为0。

| 用例 | 主失败桶 | 公开交付与判定 |
|---|---|---|
| G1a / G1b / G2b | 判官协议失败，3题 | invalid tool call；有草稿不等于经过复核，公开稿仅复核不可用 |
| G1c | 来源核验拒绝 | 公开稿有限满足权限代理规则，但内部仍拒绝缺项/真实性陈述，整链不接纳 |
| G2a | 来源核验拒绝 | 保留20倍历史静态PE及日期，删句后贵不贵与当前/前瞻口径回答不完整 |
| G3c | 来源核验拒绝 | 有机制区分，但仍有弹性/粘性/波动等材料外判断，不接纳 |
| G3a / G3b | 无效出稿或缺必答项，2题 | 一claim多句反复被拒，completed只交出证据不足模板 |
| pack1 / pack2 / pack3 | 无效出稿或缺必答项，3题 | 八问已投递；一claim多句，pack1又含私有标识，最终invalid_repair_finish，未交付八问 |
| Q14 | 实质推断越界，1题 | 内部judge passed，但作者复核不接纳，见下文 |

合计 **9 completed / 3 failed，端到端接纳0/12**。失败桶互斥计数为协议3、来源拒绝3、无效出稿/漏答5、实质越界1。驱动的semantic_verdict=not_evaluated原样保留，作者阅读意见另列；来源拒绝是运行事实，不表示判官每条理由都正确。此为揭盲作者侧观察，不是独立审查、基准错误率或修复前后的因果质量对照。

### Q14判官通过仍不能签收

从冻结私有工件离线重建系统和用户提示，SHA256分别与当时prompt_assembled事件精确一致，消息三层规则在输入内，未调用模型。因此不能再归为指导未送达。

- c14以“群聊称必涨20%”支持“情绪很可能占主导”，还称订单小额；观点出现不证明因果权重或金额。
- c17以“没有金额及量产承诺”支持“规模很小”“淘汰概率不低”，证据只支持该句的一部分。
- c19“若后续无下文，则纯情绪且大概率回吐”被material_claim_checks和material_nonfactual_checks按条件推理放行；条件句并不提供反事实或概率依据。

原始内部passed状态、公开正文和作者不接纳意见分别保存，未篡改判官记录。“可能”“若……则……”不构成支持性豁免。方法补入共享记忆 `contract-vs-delivery-mismatch.md`；这里只保留单次反例，不称已修复。

## 完整工程验证

证据根 `~/.finance-runtime/knevo-absorption-20260923/material-repair-closeout/`，最终索引 `current.json`。该索引只签8aadc，不签后续文档提交。

- Python：14664 passed、85 skipped、2 xfailed、0 failed/error，collected=14751。收据 `python/gate-oUzHLOOn/pytest.json`，依赖门禁未绕过，完整收集面无ignore/deselect/keyword/markexpr等缩窄。
- Ruff、main_gate收据回放及 `check_test_receipt.py --require-full-scope --expect-revision 8aadc23d4873251ffb3b0ecf4f9355f111ba6253` 均exit0；`python/gate-summary.json`明确标为事后验签，不是第二次pytest。
- 前端六步均exit0：冻结依赖安装、lint、typecheck、单元120 passed、build、E2E 34 passed/2 skipped；`frontend/frontend.json`含前后身份和日志哈希，已逐项核对。
- registry的parseability/check/backfill/generate-views/ledger crosswalk五项exit0；但同一bundle还含PR diff-check，因此bundle总exit1，不把它写成整包全绿。
- PR diff-check仍exit2：四份冻结原件文末空行。七份原文/题答文件SHA256全部匹配来源manifest，不改原件凑绿；干净工作树diff-check为0。
- 能力图谱审计exit0。附加共享记忆全库lint为exit1，38 errors/17 warnings（既有死链、元数据、镜像问题），本轮不扩大范围清理，原日志保留。

因此索引分别记录required engineering leaves通过、all_checks_passed=false、semantic acceptance blocked，三者不得合并成一个“全绿”。

## 原件与平台指针

- live根：`~/.finance-runtime/knevo-absorption-20260923/material-repair-f1fd8aa1a/`。
- `observations.json`逐题关联run、题面、工件哈希、私有frame、工具轨迹、内部状态、拒绝原因与作者意见；`evidence-manifest.json`封存179文件，已逐文件核对哈希。
- `q14-prompt-replay.json`证明规则输入送达；工程目录 `q14-judge-false-positive.json`保存c14/c17/c19的原始核验对象和源工件哈希。
- `source-hashes.json`记录七份冻结文件；`current.json`另外校验16份工程/观察索引文件。
- PR #877评论6251已发布并回读，记新live事实及当时全仓尚在运行的状态；最终工程结果随后另补，旧评论不改写历史。
- 取回main观察值 `2edbe4c46595cbea3eb3abe04fe84a7bd5afd55e`，共同基座仍bbd53487；相对8aadc的merge-tree无文本冲突，组合树 `a3cad04b66da08906a6def8e9963ba3e31293de2`未测试。不是合并许可，也不代表未来main无冲突。

## 决策与后续

| 采用 | 否决 | 理由 |
|---|---|---|
| 修入口后原题同正门复验 | 改题、混入reviewer答案或减少必答项 | 不能用缩小义务制造通过 |
| 独立归档并区分代码/live/文档SHA | 让旧绿或新文档代签当前运行 | 可复核证据必须绑定真正执行的版本 |
| 对Q14保留判官通过与作者否决 | 把passed或条件措辞当正确证明 | 支持类型合法不证明实际蕴含 |
| 保持原件格式红与WIP | 清原件空行、关判官、合入后再补 | 不改来源字节，不降低门禁 |

下一步先捕获判官无效工具返回的具体协议原因，未知字段不靠猜测放宽；再复现并修复一claim多句/私有标识导致的循环失败，保住八问义务；最后复验来源支持性、删句后的任务完整性与公开内容。Q18真实台账存在/空集/权限、身份及跨轮仍另验，代理题不代签。

工具沉淀复用knevo_regression.inspect_run、真实run_turn装配回归、Workbench probe及现有收据工具。一次性归档只做JSON和哈希整理，不另造评分器；新发现的条件式概率漏判需要语义判断，不能用关键词词表冒充通用修复或机械门禁。

不合main、不部署8792、不回补、不写画像，不改冻结28题。将来若获合并授权，固定届时PR head与main的组合版本，重新执行完整门禁；本轮工程绿不覆盖移动主干或语义失败。
