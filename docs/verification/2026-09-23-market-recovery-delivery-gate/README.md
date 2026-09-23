# 行情恢复：限读交付门与分项独审

**总体 HOLD。** 本轮完成独立探针落盘、隔离执行和两份正式报告；F1 报告被上游 504 阻塞。没有修改行情业务代码，没有合并、推送、部署、数据库 staging、换库或生产写入。

## 身份

- 基座（远端复核一致）：`27ca084f9ffcb9d148b749944beca340e5f4fa6c`。
- 修复分支输入：`7466e3982dca9baf1f018bf5862f554b4e51432c`，包含收盘价保护 `3abb7a4d3`。
- `merge-tree` 无冲突；组合 revision：`4dd5e66601084962697c5d78e9f6bb58eefc14c8`；tree：`49f280d13c459794435f9d52ddf90e3d81870f62`。
- 验证引用：`refs/verification/market-recovery-delivery-20260923`。独占干净 candidate 检出保留供续审；未部署。
- 原始运行根：`/Users/a77/.finance-runtime/reviews/market-recovery-qc-20260923/delivery-gate-4dd5e66/`；候选为其 `candidate/`。

本目录封存产生的后续文档提交不在上述测试 revision 内。旧 d3 全仓和 45e752c 根目录收据均未移签。

## 分账结果

| 主张 | 最终独立探针 | 作者相关测试 | K3 正式报告 |
|---|---:|---:|---|
| F2 假覆盖、坏收盘价、冻结分母 | 9 passed | 75 passed | `F2R-report/delivery/`：PASS_WITH_LIMITS |
| F1 顺序、串行兜底、失败阻断 | 5 passed | 28 passed | 无报告；BLOCKED_PROVIDER_504 |
| F3 过期计划、literal True 覆盖授权 | 6 passed | 28 passed | `F3-report/delivery/`：PASS_WITH_LIMITS |

最终独立探针合计 **20 passed**，作者相关测试 **131 passed**。每次 execute 都单独运行必红 `assert 1 == 2`；共四次均检测为 1 failed，其中一次属于初版 F2。两份正式报告均将该对照标为 `probe_bug`，不是产品缺陷。阳性对照只证明装置能报告红色断言，不等于产品变异测试。

初版 `F2-execute/` 的 **7 failed** 原样保留：独立探针未指定列名，向初始化后 14 列表插入 9 个值，全部在建数阶段失败。初次作者测试 **1 collection error** 则由沙箱拒绝读取 `.git` 元数据引起。控制器仅补充实际初始化结构和错误原件；探针由 K3 第二次独立生成，没有作者代改。第二版沙箱只放行 `.git` 的元数据查询，不放行文件内容或生产数据。

## 报告采用边界

报告、SPEC、QUALITY 均按原件封存，控制方只收窄采用范围，不改 reviewer verdict：

- F2R 未单测负无穷，也未单测板块成员自身的坏 close；坏值探针实际放在板块外股票。四表比较是 `SELECT *` 的逻辑行值，不是物理文件字节。夹具只种目标日，不能采用报告中更宽的“跨日期保护已证明”表述。
- F3 比较的是 `stock_ts_code, close` 两列，不能采用“整行/字节不变”表述；缺 policy 用例没有断言其他日期。事务内检查位置有源码顺序证据，但单连接夹具不能证明并发安全。
- F3 报告指出指纹只覆盖部分列，是范围外静态观察，不是本轮可触发产品缺陷。完整输入指纹、部分写后回滚、真实构造计划、mootdx 部分 flush、任意并发仍未认证。
- F1 有独立探针和执行记录，没有正式 Spec/Quality 报告，不写成 PASS。
- 两份报告没有发现其已测范围内的产品缺陷，不可扩大成全部 F1/F2/F3 或生产恢复通过。

## 执行装置

沿用固定 K3/Plus 路由、流式工具请求、剥除 temperature、无自动重试/切模型。每会话最多 4 次预占请求、600 秒；并发最多 2。

`delivery-gate.mjs.txt` 实现一次性状态转换：仅 `read_packet` -> 仅 `submit_delivery` -> 封存退出。模型不能任意读文件或运行 shell。源码包按主张分开，不含作者结论；探针以真实候选函数和自建内存夹具为对象。执行阶段由确定性控制器在 macOS 沙箱跑原样探针、阳性对照和作者测试；报告阶段是新的隔离 K3 会话读取源码与收据，不宣称 K3 自己运行了 shell。交付门有 **5 项 Node 自测通过**。

本轮 **14 次预占请求**；响应钩子记到 **13 次 HTTP 200**，另一次的模型错误原件明确为 CloudFront **504**。F1 报告进程 exit 0，但没有交付。原始 `execution.json` 的简化归因是 `BLOCKED_NO_DELIVERY`，`summary.json` 按 `model_errors` 收窄为 `BLOCKED_PROVIDER_504`，没有篡改原件。不能用响应钩子漏记 504 或 exit 0 推导成功。

本轮所有进程已退出。`run-v2.py` 已在收尾封存，但最初运行时输入监听只覆盖 `run.py` 等基础文件，未覆盖该包装器；不将本轮称为完整执行器身份认证。此装置是固定候选的可复跑实验，不是已接入通用 reviewer worker 的新产品能力。

## 作者回归与门禁

`author-scoped-gate/`：干净组合运行 `bash scripts/run_main_gate.sh --pytest-args '-q -p no:cacheprovider tests/'`，**2676 passed / 62 skipped / 0 failed / 0 error**，收集 2738。Ruff 通过。收据复核 revision、解释器、Python 版本、依赖指纹、干净状态、收集/结果对账、`target=tests/`，基座漂移 0。

**这不是全仓 pytest。** `receipt-check.txt` 的“收集面未被收窄”仅指相对于声明的 `tests/` 没有再过滤，不覆盖 `intelligence/tests/` 等其他目录。不能与上述 131 个有重叠的作者测试相加。

`supplementary-checks/`：消费注册表、技能注册表、frontmatter 解析与交付门自测均 exit 0。当前相对基座没有前端改动；本轮未跑前端或 E2E。

## 复查与续跑

- 机器汇总是 `summary.json`，不是 reviewer verdict。正式原件在 `F2R-report/delivery/`、`F3-report/delivery/`。初版失败的 pytest 原始 stdout/XML/stderr 含尾空白，因此 `git diff --check` 对这三份原件报警；为保持哈希不做格式化，不宣称该检查全绿。
- `manifest.json` 校验封存的机器文件；`raw-manifest.json` 还记原始事件流、源码输入包和原始文件名的 SHA-256。大事件流留在原始运行根。
- `.py.txt` / `.mjs.txt` 是原始代码的逐字节存证，避免被仓库测试发现器或格式化器当成新增测试/产品代码。可复跑的原始 `.py` / `.mjs` 仍在运行根。归档日志按仓规改名 `.log.txt`，内容不变，映射见 `archive-renames.json`。
- 下一轮首先补 F1 的 report 阶段，复用已有独立探针与 execute 原件，不必再从 explore 读起。上游错误本轮未重试。
- 最终准入仍需最新 main 组合的全仓收据、报告措辞修正/缺口裁决，以及决策页五问、三合同、5553/5565 范围和 53 只除权/送转处置。任何生产恢复或合并仍需明确授权。
