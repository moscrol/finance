# feat/harness-opt-1001 在途交接（2026-10-02）

## 这个分支做什么
验证 19 个 harness 补丁，并修复真实 KB / run 重放发现的问题。工作树 `/tmp/harness-opt`；Python 用 `~/finance-workspace-private/.venv-workbench/bin/python`。

## 决策与被否方案
| 采用 | 否决 / 理由 |
|---|---|
| 数值保留指标，价格箭头只认绑定收盘价 | 裸数池会把跌停串成涨停、换手率拼成价格 |
| 日期/A股题材边界、极简当日盘面 | 不改题集，不拆公司后缀，不为一致率统一全部车道 |
| 两句未来条件交人工判断 | 证据数字存在不等于条件结论已有证据 |
| PR #10 固定提交只读审查 | 实验由另一 agent 管，不擅改分支或实验 |

完整决策与原文：`docs/handoffs/2026-10-02-harness-opt-local-followup.md`；首轮失败证据：`docs/handoffs/2026-10-02-harness-opt-local-validation.md`。

## 当前状态
续修代码已提交 `2d1fb9cf8`；原始补丁 `fb03e8e37` 与 GitHub 同名分支一致，tree 为用户指定值。未推送、未合 main。原有空文件 `30` 保留。

## 已验证
- 提交后 23 文件：1103 passed / 1 skipped（Linux 专属锁测试）；ruff 与提交钩子通过。
- 收据 `20261001T180325Z-2d1fb9cf-d14db84e0411.json`（`~/.finance-runtime/test-receipts/`），校验通过。
- 真实 KB 路由：anchor=16，一致率 0.622→0.822→0.889；clarify=0、LLM fallback=0。
- 966 runs / restored 955 / failed 11；本轮消除 7 处误报，恢复错误 2 家标注。相对 main 基线 disappeared=15 / appeared=0。
- 内容题集 selftest 通过；独立审查 7 条反例已入回归并通过。

## 未验证 / 已知边界
- 11 条旧存证为空/缺结构核验字段，未绕过。15 个释放数中 23家/42家两句仍含模型未来条件，严格人工门禁不能签全绿。
- 未跑全仓或模型答卷；共享 httpx 版本漂移未改。2×2 未确认收口。
- PR #10 新增段 `983590438...0eb1af362` 有 4 项：异常子分支错模型被准入、自报开关绕过产物门、克隆漏 WAL、ruff 失败被汇总成功。报告分规范/需求两轴，有离线复现。

## 下一步
先处理 PR #10 审查与两句条件口径；用户确认实验结束后，按任务书 §6 走 PR 合入和模型评测。A7、工具差分分支、Gitea 清枝、曝光凭据、预测台账仍只汇报待决定。推送前重查 Gitea 镜像方向。

## 踩过的坑
原始输出在 `tmp/local-agent-validation-1002/`；主要文件 `route_probe_verified.json`、`gate_verified*.jsonl/txt/log`、`followup-manual-evidence.json`。片段搜索会命中未绑定证据，须核对绑定哈希。不要把相关测试收据当全量绿。路由剩 5 个差异原样保留；茅台别名未补。
