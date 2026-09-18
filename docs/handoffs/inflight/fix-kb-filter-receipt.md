# KB 过滤回执消费

## 这个分支做什么
阻止请求等级/时点被兼容回退丢掉，核验真实回执，并保护证据范围与暖 worker 代码身份。详见 `docs/handoffs/2026-09-18-kb-filter-receipt.md`。

## 决策与被否方案
- 请求 filters ≠ 已执行；核验封套+逐条元数据后才填 applied_filters。
- 旧列表仅用于无过滤；不支持约束就拒交付，不删参数重试。
- 过滤片段禁止本地扩读/stale恢复，避免未验证文字继承等级。
- 新回执结果不缓存；模型/索引仍常驻。代码内容指纹换进程，查询中变化弃结果；否了只看路径/mtime。

## 当前状态
实现已提交 `698555e2`，base `0a1cb8c4`，树 `/Users/a77/fwp-wt-kb-filter-receipt`。代码干净；后续仅交接/验证文档。未推、未合、未部署。
配套 KB 树 `/Users/a77/kb-wt-retrieval-reliability`，代码 `b62c58cb5`、导航修复 `1f614b694`。两仓不能分开冒称线上已通。

## 已验证
- 干净 `698555e2` 全量11481P/73S/2xfail/0F，Ruff通过；181定向已含其中。
- 前端四步通过（107P）；E2E34P/2S；registry四检查与原pre-commit通过。
- 三项真实KB CLI/worker跨仓测试：临时wiki/hash索引；过滤/空回执/暖进程后续污染隔离。
- warm worker同mtime+size代码升级2项先红后绿，中途变化弃响应/后续新进程通过。
- 原始收据在 `docs/verification/2026-09-18-kb-filter-receipt/`；全量收据dirty=false，七条件核验通过。测试绑定实现提交，不是后续文档头。

## 未验证 / 已知边界
生产BGE/双索引迁移与实际消费未验；没有真实模型答案质量或延迟提升结论。过滤仍走CLI，不是暖worker。未给所有问句自动加as_of。代码指纹不覆盖第三方依赖/环境；发布仍需不可变检出+重启。KB历史冲突仍隔离、全文过期/覆盖缺口未修。

## 下一步
1. 等用户确认合并；基线变化先复验整合候选四叶。
2. 先部署KB hook保护，再受控刷新双索引，核对元数据/字段非空/覆盖/隔离，后切消费者。
3. 正文冲突单独语义恢复，补真实题集标注后再比检索模式。

## 踩过的坑
全量首轮唯一红在干净base同红：展示测试经FINANCE_WS读真实库，已仅将该测试绑临时根。E2E改端口须同步RE06_E2E_URL。跨仓必显式KB_RECEIPT_CODE_ROOT，未设是skip；KB_ACCESS_LOG_PATH指临时文件。多树共享hook，Git命令临时hooksPath须保留对应仓pre-commit；不碰生产post-*与共享脏文件。
