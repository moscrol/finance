# 历史工件当前授权续修验收（2026-09-21）

固定代码 `7249378a5bdb9b01cc62ec3bca13af3149bd48df`，父文档提交 `bbd948a6a400c90871657c0719b1cfb48107470e`，前次代码 `f90fd3dc3ba10a9a00f7264f92d3ec959b2ba682`。仍属 WIP #841，基于 #832，不改 #809/#829 原头，不合 main、不部署8792、不写生产。旧 `2026-09-21-history-evidence-integration/` 证据保持不变。

**本包只认证固定 SHA 的作者工程检查。当前 main 批次门被基座漂移阻断；独立审查和自然金融质量均未通过。**

## 修复与边界

- `HistorySession.read` 不把缓存命中当授权，也不信缓存元组；每次解析受限 ref，经 RunStore 验当前用户、会话、登记、可见性、可下载及字节完整性，成功才更新缓存。
- `RunStore.read_history_artifact` 新增可选 keyword-only `conversation_id`。锁前校验目录，复用每 run 的 `_run_state_lock`，锁内重载元数据、重验权限，校验并仅读一次字节。省略参数保留旧用户范围合同。
- 会话范围未知 run/用户或会话不匹配仍 `ValueError`；登记工件不可用仍 `FileNotFoundError`。`refresh` 重建替换索引，不只追加。
- 合成反例通过私有 `_write_run` 改归属；证明缓存陈旧授权风险，**没有证明普通用户可经公开接口实施线上越权**。锁只协调遵守同一文件锁的 writer，不防绕过接口直接改盘；hash 只证一致性，不认证原始用户归属。

## 固定版本读数

| 检查 | 结果 | 原件 |
|---|---|---|
| Python 全量 | 12659 passed / 87 skipped / 2 xfailed / 17 warnings；0失败/错误，809.93秒 | `python-full.log.txt`、`python-full-execution.json`、`receipt-exact-receipt.json` |
| JUnit 结构核对 | 12748 项；相对 f90 新增24项、无删除，89项skip/xfail名称/类型/理由完全一致 | `junit-comparison.json`；完整XML由外部哈希绑定 |
| 精确 SHA 收据检查 | exit 0；解释器、依赖、净树、revision一致 | `receipt-exact.log.txt`及execution |
| main 批次漂移检查 | **exit 1**；6次合并超过5次上限，不放宽门槛 | `receipt-drift.log.txt`及execution |
| 定向历史回归 | 315 passed | `focused.log.txt`、execution、receipt |
| 前端六步 | 安装/lint/typecheck/110项单测/build/E2E34通过2跳过，六步exit0 | `frontend/` |
| Ruff / 注册表 / 台账crosswalk | 六命令exit0；crosswalk仍98条反向回指warning | 各命令log与execution |
| 七撤保护 | 全部被行为断言捕获；分别2/1/3/1/4/1/2失败，无收集/导入错误 | `mutations/summary.json`及逐项XML/log |

全量执行 `13:37:08.168418Z` 至 `13:50:48.940014Z`，首尾固定724且clean；收据源 `~/.finance-runtime/test-receipts/20260921T135039Z-7249378a.json`，定向源 `20260921T133438Z-7249378a.json`。1800秒超时、独占basetemp、失败临时夹具保留，磁盘样本在execution中。磁盘变化原因未分解，不把进度中的估计当测量结论。

漂移核对针对 `gitea/main@028a251a1b2ca98245326a6b59376f4f7f8e5e81`，共同祖先 `f2c3e9e1a24f42ae9b1d5a8cb9e501ababd1330a`；多13个提交，其中6个merge。精确SHA检查通过与当前批次检查失败是两个不同结论，不能删掉后一项来宣称整体可合。后续docs tip不继承724收据身份。

## 离线真实原件回放

`replay.log.txt`是JSON：原件SHA256 `98b3746f5cc71027c3a5756ada1057f433a84acb98b65f3106b8c5c95e42d933`，225行/9页/每页25，累计905次卡恢复（包含各页重复元数据，不是905个独立样本）。初次投影与授权reader同源卡相等、重叠页hash相等、特征等于源、原件未改，自然模型调用0。真实JSON复制进临时RunStore，故不认证原始用户归属，也不证明模型自然引用和金融判断质量。

## 保留的失败与工具盘点

- `dirty-scope-v2`：1F/98P，测试错误地要求visibility撤销用ValueError；保留既有FileNotFoundError合同，修测试。
- `dirty-consumers`：1F/144P，真实消费者抓到未知run错误类型退化；修实现而非放宽消费者。`dirty-combined`与`precommit-targeted`315P属于bbd上的dirty诊断，不移签724。
- `precommit-session-binding-red.log.txt`：临时撤session绑定2F/10P/13deselected；后来已恢复。正式七变异在内存改保护，不动源码；失败必须是断言/DID NOT RAISE，不以收集失败计数。
- 封存脚本第一版遗漏`AssertionError: assert`消息前缀而中断，发生在创建仓内归档之前。检查XML后补入实际断言前缀，同时保留退出码1、failure非空、无error要求；没有改原XML或放宽生产门。这次工具失败只留执行转录说明（本节），没有独立原始日志文件，不能冒称已保存日志。
- `scripts/*.py.txt`保留此次执行器、变异器、XML封存器和回放器的源码快照及docstring。它们硬绑定本版本、路径和数据，是证据工装，不是新支持的通用CLI；不提升进运行时scripts，不为归档再扩大产品改动。正式保护已进入两个测试文件。前端/receipt/Git归档检查复用现有仓内工具。
- Memory图谱审计前后exit0：92行、257→258断言，206→207条在途/未校验，新增存储符号仍按分支标PENDING；路径存在不等于行为验收。

## 不得外推

独立Spec/Quality未在724执行，旧K3超时不代签，也没有新预算。自然金融仍`not_passed`；225/25与候选12.6/16.5自然引用、判官消费、#793板块排序/同窗候选范围/改判条件、#794按需展开/版本/预算/取消/可发现性仍待。#833联合树和后来main组合未验。不存在合入或生产放行授权。

## 归档完整性

`sha256-manifest.txt`列仓内全部文件（排除自身），提交后执行：

```bash
.venv-workbench/bin/python scripts/check_evidence_archive.py \
  docs/verification/2026-09-21-history-authority-followup --revision <archive-commit>
```

该工具核Git文件集合及blob字节，不只核磁盘。`EXTERNAL-SHA256SUMS`绑定两版完整JUnit和真实原件；未提交缓存/临时目录/二进制/生产数据。全文运行根为 `~/.finance-runtime/reviews/react-trace-integration-20260921/history-authority/`。旧包不改写，后续交接见 `docs/handoffs/2026-09-21-history-authority-followup.md`。
