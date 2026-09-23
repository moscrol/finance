# 行情恢复隔离验收续片

## 裁决

**HOLD，不可据此合入。** 新发现的桥接越界指纹漏洞已修，本轮定向回归与有限独审通过；新候选的完整 Python / 前端门禁因资源准入未满足而没有启动。没有 push、合并、部署、真实恢复 staging、生产换库或生产写入。

- 代码提交：`0d3f562cb728c512c58ef5c7287feb3f4d9aae5f`。
- 固定合流候选：`6b43ac82a05991f676d15bd27e4099449c67f62b`。
- 基座：`3bb81b9638f97b4773ce0f338df3a505b7c0162f`；17:51 UTC 封存时远端相同。
- 候选 tree：`94cfa97e84e6866e055f1b9eae66f744b953e645`。
- 保留 ref：`refs/verification/market-recovery-acceptance-20260923`；两棵 detached 检出位于原件根，合流用 `merge-tree`，未更新主干。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，3.12.13；依赖指纹 `3328bed61f3e21ea`。

上轮 `1de68567e740` 全量绿只签上轮候选；本轮代码、基座均变化，不移签。后续文档 tip 同样不是本次被测 revision。

## 修复与回归

原 `_day_fingerprints` 只覆盖代码、close、amount、pre_close，且 `coalesce(...,-1)` 混淆 NULL 与真实 -1；apply 只遍历写前日期，漏新出现的其他日期。新反例在原代码 **11F / 7P**，均为行为断言失败，无收集错误。

修复采用 DuckDB `hash(d)` 整行哈希的整数和，比较写前/写后日期键的并集。所有列和 NULL 语义被纳入；它是事务内误写探测，不是无碰撞证明、跨版本签名或 build 输入新鲜度保证。

| 分账 | 结果 | 可支持的结论 |
| --- | --- | --- |
| 脏树迭代 | 新定向45P，扩大396P | 修复迭代，不是净树准入 |
| 固定合流候选 | 396P，0F/0E；前后同revision且净树 | 14个明确文件的回归，不是全仓 |
| Ruff | 整仓exit0 | 静态检查通过 |
| 注册表 | parseability/registry/tables/views/ledger-crosswalk均exit0 | 五项现有检查通过 |
| 新F3独立探针 | 3P；阳性对照1F被检出 | 有限动态覆盖，报告PASS_WITH_LIMITS |
| 独审内作者测试 | 46P | 与396P重叠，不能增加独立分母 |
| 历史敏感度 | 同探针旧桥接模块1F/2P、0E | 新指纹能检出旧行为，不是新独审结论 |
| 完整门禁 | BLOCKED，0步骤启动 | 不存在新完整Python或前端收据 |

新增作者覆盖：真实CLI子进程选临时库、桥接成功/缺供应商/主源部分残留、钉为生产身份的临时库拒写；真实same-day发布门拒绝不完整夹具且未到导出；无效恢复输入在派生DML前拒绝；热度表实际插入后四表回滚；正常daily与完整恢复数值一致；真实build-then-stale写前拒绝；桥接部分插入/替换失败恢复所有列；一个受控双连接竞争；带非空批次的迟到fetch/取消。

DML 指 DELETE/INSERT/UPDATE 等修改数据的 SQL。临时库中的写入与换库测试不等于真实恢复或生产操作。

## 独审边界与勘误

原件 `independent/F3-report/delivery/report.json` 保留不改，逐条校正见原件 `operator-review-notes.md`，均在清单中。

- 独立探针未调用build：报告“建计划后行出现”不采信；只能签手工计划面对已有行的写前拒绝。真实build-then-stale由作者另测。
- 报告“main has advanced”来自复用输入模板，不是本轮实测；本轮封存时主干与基座一致。
- 动态越界例同时改turnover并插新日期，错误消息分别检查两个日期；不能声称独立逐列压测。
- literal True控制后的truthy 1拒绝只核行数，没有再次核全列。独立部分写入失败、双连接并发、完整输入新鲜度仍未验。
- 模型两阶段共4请求/4 HTTP200；无重试，价格未验证。68个已结束审查文件未发现凭证精确值落盘，不记录凭证值或哈希，也不是通用秘密扫描。

收据校验exit0只证明定向收据身份/解释器/依赖/净树/零漂移。操作员试用 `--require-full-scope` 做负例也exit0：该选项合同只检查 `-k/--ignore` 等收窄，不要求pytest目标为仓根。原误设控制日志保留，**396P仍是定向**，没有修改共享校验器或把该exit0当全仓证明。

## 仍缺什么

F1完整夜跑到成功发布/导出的隔离链；F2默认daily坏数据、其他字段和并发源变化的明确合同与验证；F3建计划后源数据改变的完整输入重验、任意并发；FinanceQuery真实DuckDB中断、阻塞connect/close的抢占及OS调度保证。既有独审和本轮作者回归不能互相补签。

完整门禁准入等待604.6秒、40次观测，空闲磁盘3.72至6.98GiB，始终低于8GiB下限，且有其他pytest。没有降低门槛、杀他人进程或删除他人/失败证据。控制器已结束，不会稍后自动开跑；下一次须新输出目录与授权范围核对。

## 封存格式

原件根：`/Users/a77/.finance-runtime/reviews/market-recovery-qc-20260923/acceptance-followup/`。

[manifest.json](manifest.json)登记118个原件；116个不超过150KB的文件以Base64 JSON封套归档，另2个大文件仅存原件路径/长度/SHA-256。每个封套的`data`解码后已逐字节核对原件；封套不是重写原报告。清单自身与本README不计116个封套。

旧冻结包字节不变。本候选相对基座的完整 `git diff --check` 仍exit2，源于旧归档空白；未裁剪原件、加豁免或宣称所有检查全绿。新封套避免新增同类空白问题，不消除旧非零。详细决策见[交接快照](../../handoffs/2026-09-23-market-recovery-acceptance.md)。
