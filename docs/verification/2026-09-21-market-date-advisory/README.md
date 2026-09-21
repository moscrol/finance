# 日期差异策略的作者验证

## 身份与范围

受测提交：`c57ec6542e5b33b2d7d2dccadf742e8a33e23b5d`，工作树 `~/fwp-wt-market-date-advisory-0921`，分支 `fix/market-date-advisory-0921`，基座 `79b11d4268a3`。运行逻辑最后变更06de3dfc，c57仅更新local_only旧日期断言。

本目录由后续文档提交封存，测试收据不移签给文档tip或后来main。结论是 **作者工程验证通过**，不是独立Spec/Quality、自然模型答案、生产部署或数据恢复通过。

外置原件：`~/.finance-runtime/reviews/market-date-advisory-20260921/`。manifest.json记录197份文本原件的来源路径、字节数、SHA256，合计5739356字节；`.py.txt`/`.log.txt`仅扩展名变化，字节未改。临时DB、缓存和临时目录不入库，不删除原件。sha256-manifest.txt覆盖本目录提交文件，复用scripts/check_evidence_archive.py从Git对象核验，而非只验工作盘。

敏感信息检查：仓库 `scripts/smoke_workbench_self_use.py::SecretScanner` 首次扫描200个文本文件，6文件/12组文件-模式命中；加入扫描说明后，最终201文件、7文件/15组命中。新增命中来自说明中引用的测试样例。逐项核为测试夹具、Python模块/属性名、JUnit类名；没有发现实际凭据。排除依据见 `scan-review.md`，不是零命中或通用安全认证。两个猜测的扫描脚本路径不存在，一条补充shell扫描引号错误；这些均不算成功扫描。

## 最终读数

| 范围 | 结果 | 原件 |
|---|---|---|
| Python完整 | 12551P/85S/2X，17 warnings，exit0 | raw/final-c57ec654/python/1.log.txt、junit.xml、run.json |
| Ruff | exit0 | raw/final-c57ec654/python/0.log.txt |
| 精确收据 | 同SHA/树/解释器/依赖/退出码/非零计数一致 | raw/final-c57ec654/python/pytest-receipt.json |
| 前端 | install/lint/typecheck/test/build/E2E六步0；110P；浏览器34P/2S | raw/final-c57ec654/frontend/gate/frontend.json及六步日志 |
| Registry | finance单仓parse/check/tables/views、ledger五步0 | raw/final-c57ec654/registry/run.json |
| 变异 | 11/11被实际断言捕获，各正常臂先过，无setup/collection错误 | raw/final-c57ec654/mutations/result.json及每项两臂log/xml |
| 作者对账 | stdout唯一收据路径、JUnit12638元素、首尾净树、日志哈希一致 | raw/final-c57ec654/author-qc.json |

解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python3.12.13。最终精确收据名`20260921T134045Z-c57ec654.json`，SHA256`cfd641011dd40b4aafdb561555b02ddeb68524df83fdb66f246e15205cc89c33`。

候选资源等待13:06:34Z起，13:28:11Z无其他pytest且11129614336字节可用时准入；测试13:40:49Z收尾。252次运行采样最低10927255552字节。没有停止他人的测试，准入检查不是系统级预留。

11项变异：日期准入硬门、参照日封顶、隐藏异日题材、NULL补0、忽略明确来源、未知补齐、旧窗口自证、日期差异FAIL、统一总览日期、WARN升级partial、预取丢日期。进程内替换单函数，不写候选源码，不外呼或读生产库。

## 历史红灯与勘误

- raw/python与raw/fixed-5d425ff2/python：发现遗漏后中止，pytest=-15，complete=false；缺收据的AssertionError不是测试通过。
- raw/fixed-06de3dfc/python：作者误停，源码未动；原停止理由错误，见同目录上一层stop-reason-erratum.json。原文件保留，不倒改历史。
- raw/final-06de3dfc/python：完整12550P/1F，失败ID为test_e2_local_freeze的stale臂，旧拒证据断言与新策略冲突。c57只修测试，后续重新完整跑绿，不将局部49P拼进全量。
- related系列及local-policy-followup是旧版本/脏树相关回归；不替最终候选签字。
- 口头计数“10项变异/36项全过”以最终机器读数勘误为11/11与34P/2S。

## 复核入口

```sh
python3 scripts/check_evidence_archive.py docs/verification/2026-09-21-market-date-advisory --revision HEAD
```

该命令只验封存完整性，不代表重新运行测试或独立审核。复跑工具/测试时用项目venv、新的同SHA独占检出和外置目录；不要直接执行本包内带固定旧输出目录的脚本原件。

未验：新自然模型通过Workbench conversations的公开稿/引用/逐来源时点；新的独立Spec/Quality；后来main组合；真实补采/夜跑业务效果。完整决策见`docs/handoffs/2026-09-21-market-date-advisory.md`。
