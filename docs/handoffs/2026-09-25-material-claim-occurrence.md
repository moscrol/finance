# 2026-09-25 同题重复句来源身份修补

## 背景与边界

用户要求继续依次推进Pi尾项队列。主检出detached b4a35fa2c存在他人改动，不接管；#877作者树7a89e2510保持干净、原件不动。原八问 `run_20260924_015153_765303` 仍是author not_passed，首稿多句共用claim，续稿仍有方向、基期、库存性质及盈利前提错误。本轮只离线排查，不调用付费模型，不改原题或评分口径。

远端main复核从ea42到03352758cf9b31e3f5d179b517be48cb89588679，固定该基座另建 `fix/material-claim-occurrence-0925`。不是#877全部变更的前向整合，也不重签#71/#73/#81历史收据。

## 发现顺序

1. 阅读冻结writer-summary、inspection、author-observation及材料绑定/判官代码。已有严格逐句要求与语义判官，不把增加提示词当成修复证据。
2. `material_claim_rows`先按题过滤，再对每个claim遍历所有同文句子。同题两次出现各绑自己的材料时被展开成四条，三次成九条；本句无依据的拒绝因而落到另一出现位置。
3. 新增8项回归，原实现7个有效断言失败、1通过，没有收集错误。公开投影删除前句但保留后句的对照已通过，必须保留。
4. 每个question binding记录已消费句索引，一条claim只认领第一个未消费同文位置。保留现有跨题归属；非question的边界声明旧合同不在本轮扩修范围。
5. 修后8P。首轮较大回归误列Knevo枝独有 `test_material_prompt_contract.py`，exit4/no-tests原件保留；改用本树21个真实文件后736P/4S。
6. 代码提交3198df4964f3fc52fff7488b17763955ba15e4f2，全hook通过；固定干净代码再跑736P/4S、collected740，定向收据校验exit0。
7. 两条撤保护定义入库，复用现有runner；资源复核load1=9.08/8.24/8.57/9.31，高于上限8，未启动变异测试，没有后台等待器。

**冻结八问续稿同题重复组实际为0**，本缺陷是同一路径的独立发现，不是该次自然失败的根因修复。不能签语义、生成可靠性或原八问接纳。

## 方案对比

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 题号+未消费句位置 | 已有逐句有序合同足以定位，保留不同出现的来源和拒句索引 | 采用 |
| 按文字去重 | 会删除用户实际交付的重复句与其来源差别 | 否决 |
| 新增持久化claim ID | 当前问题只在复核投影，额外迁移协议/存储无必要 | 否决 |
| 单一前进迭代器 | 前句被公开投影删除时会耗尽后续匹配 | 否决，保留对照 |
| 顺便更改边界声明归属与删句来源重映射 | 没有相同的逐题有序合同，需单独建模验证 | 不扩修 |
| 用修补与离线替身签八问通过 | 冻结稿没有本形状，且替身不证明语义 | 否决 |

## 证据

根目录：`~/.finance-runtime/reviews/pi-closeout-execution-20260924/material-occurrence-0925/`。

- `before.log/xml`：原实现7F/1P；`after.log/xml`：修后8P，均是未提交阶段证据，不冒充代码SHA。
- `regression-uncommitted.log/xml`：误列不存在文件，exit4/no-tests；`regression-uncommitted-02.log/xml`：736P/4S。
- `regression-fixed.log/xml`：固定3198的736P/4S、740收集；4跳过为已有同类嵌套引号排除，零本轮跳过。
- 固定收据：`~/.finance-runtime/test-receipts/20260924T161513Z-3198df49-efe4dcd1eb34.json`；`receipt-check.log`确认revision/解释器/当前依赖指纹/干净身份及目标一致，exit0。21文件定向，不是全仓。
- `code-commit.log`：提交hook全部通过；全仓Ruff与diff-check exit0。
- `workspace-doctor.json`：exit1/blocked，httpx实际0.25.2、锁要求0.28.1，缺模块0。未改共享解释器。环境指纹一致不等于符合锁文件。

## 未完成与下一步

资源准入后运行两组固定revision撤保护：移除索引不可复用检查、移除一次匹配后的break，必须真实断言红/恢复绿。命令：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/review_probes/run_extraction_mutations.py --revision 3198df4964f3fc52fff7488b17763955ba15e4f2 --definitions scripts/review_probes/material_claim_occurrence_mutations.json --tests intelligence/tests/test_e2_material_claim_review.py --output <new-output-directory>
```

未做完整Python/前端/E2E/registry门禁、独审或自然模型复验；不得合并/部署。#877原方向/本句基期/事实支持、8项RAG不一致继续开放。若后续合流#877则是新代码对象，必须重新验证，不借本次定向收据签组合。

工具盘点：回归与两变异定义已入仓，复用现有runner，没有新建临时应用工具。跨领域原则补入agent-memory `state-transition-identity-must-survive-dedup`；harness-reference仍有他人改动且底旧，不覆盖。知识图只增加在途源码指针，不新增已验收能力。
