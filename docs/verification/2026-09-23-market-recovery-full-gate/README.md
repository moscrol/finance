# 行情恢复组合：完整 Python 门禁与独审阻塞

结论：**完整 Python 门禁通过；总体 HOLD**。本轮没有改业务代码，没有合并、推送、部署、数据库 staging、换库或生产写入。独立审查没有交付正式结论，不能把作者测试通过替代独审签字。

## 固定身份

| 项目 | 值 |
|---|---|
| 主线，结束后再次 fetch 核对 | `5f35da1723f74663a4803c4d1490c402a1d6db40` |
| 被组合的修复枝提交 | `bb8e207e6f368d409427a5cc98daec54117b0423`，代码仍为 `4fa70046f` + `981c4d629` |
| 组合预览 revision | `d3abd6703368c668405e74a7e50beacd49b7581b` |
| 组合 tree | `fde4d4931d2735143daa9b42b0480c1a8c35290f` |
| 测试树 | `/Users/a77/fwp-wt-market-recovery-qc-preview-0923` |
| PR #861 远端头 | `2df76ae9f7147619c0f6b9ec1faddf57d7a5b53a` |
| PR #871 远端头 | `1d3324211118c15478e0995b484c463885dcf28c` |

两个远端头都已用 `merge-base --is-ancestor` 确认包含在组合内。`merge-tree --write-tree <main> <fix>` 无冲突，产出的 tree 与预览完全相同，见 `merge-tree.txt`、`composition.txt`、`remote-heads.txt`。只是本地临时组合，没有移动 main 或合并 PR。

本轮归档文档会产生另一个分支提交；下列收据**只认证上面的 d3abd670 预览，不认证后续文档提交或未来合并 tip**。

## 完整门禁

| 检查 | 结果 | 证据 |
|---|---|---|
| `bash scripts/run_main_gate.sh` | exit 0 | `main-gate.txt` |
| 全仓 pytest，未传测试目标或筛选项 | **14798 passed / 85 skipped / 2 xfailed / 0 failed / 0 error**，2664.35 秒 | `full-receipt.json` |
| 收据身份与完整范围 | exit 0；收集 14885，与结果总计相等；基座漂移 0 | `receipt-check.txt` |
| `ruff check .` | exit 0 | `ruff.txt` |
| 消费注册表 | exit 0，local 计划 20 步与实现对齐 | `registry-check.txt` |
| 技能注册表 | exit 0，本次三个仓库均在场 | `build-registry-check.txt` |
| frontmatter 解析 | exit 0：本仓 39 + 知识库 22 = 61 份 | `parseability.txt`、`registry-scope.json` |
| 前端 / E2E | 本补丁不适用；相对本轮 main 的 webapp diff 为空 | `frontend-diff.txt` |

85 skipped 与 2 xfailed 为 pytest 本次报告状态；没有新增筛选、跳过失败或修改断言。完整收集范围不等于所有 opt-in live 用例都执行了。跨仓注册表绿仅说明所记录检出根当时登记一致，不代表另外两个仓库有完整工程绿色收据。上轮仅本仓 39 份、跨仓跳过的历史结果仍保留在旧证据目录，未改写。

测试使用 `env -i` 白名单环境（HOME、PATH、KNOWLEDGE_WIKI、FWP_TEST_RECEIPT_DIR）与 `umask 022`。`KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki`，不继承 launcher 参数。解释器由 `test-environment.json` 解析为主树 `.venv-workbench/bin/python`，Python 3.12.13，依赖指纹 `3328bed61f3e21ea`。工作树首尾干净；未用 `--allow-dirty`、baseline 红集豁免或环境绕过开关。

原始门禁目录：`/Users/a77/.finance-runtime/reviews/market-recovery-qc-20260923/full-d3abd670/`，本轮唯一收据为 `gate-FBWWAmSG/pytest.json`，没有使用共享 latest 指针。

```bash
cd /Users/a77/fwp-wt-market-recovery-qc-preview-0923
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/check_test_receipt.py \
  /Users/a77/.finance-runtime/reviews/market-recovery-qc-20260923/full-d3abd670/gate-FBWWAmSG/pytest.json \
  --expect-revision d3abd6703368c668405e74a7e50beacd49b7581b \
  --base-drift-max 5 --require-full-scope
```

## 离线审计复验

在同一 d3abd670 代码上运行 `python -m scripts.audit_recovery_metadata`，只读旧封存原件，只写新的 JSON 产物；exit 0。完整参数沿用 `docs/handoffs/2026-09-22-market-recovery-field-contracts.md` 的复现命令，但 candidate/capture/comparison 全部使用绝对路径，输出放到上述新门禁目录。没有执行其构造 comparison 的步骤或覆盖旧原件。

新 `metadata-audit.json` SHA-256 为 `abfa67b21d908436451ea87909cc3c855592e86d10a5f1d85fe72ad4f10fdae8`，与先前封存审计逐字节一致。`metadata-audit-summary.json` 与 `metadata-audit-sha256.txt` 可复核：声明 5565 = 报价身份 5553 + 不可交易身份 12；名称差异 380；换手率差异 21；官方历史名册仍未核验，`production_ready/database_writes/publication_attempted` 仍全为 false，五项 remaining_gates 保留。

这里的 5553 是**封存候选**的计数，不是本轮生产库回读。本轮没有证明生产库已补齐，也没有把历史 09-22 21:47 换库抹掉。

## 独审没有完成

见 `independent/README.md`。独占检出、只读源码、工具无网络、现有 Plus K3 通道、请求前预占、无重试/切模型。首轮 360.91 秒触截止时间（exit 143），7 次请求但无探针、无正式报告；第二次会话尚未启动，前置通道探针就发生 45 秒超时。共 9 次请求预占（含两次预检），不是费用账单。

只有控制器的 `BLOCKED_REVIEW_DEADLINE` / `BLOCKED_PROVIDER_TIMEOUT`，**没有 Spec/Quality PASS**。execute/report 没有运行，独立探针 0，阳性对照未执行。空 stderr 和无 model_errors 不构成通过证据；初次 HTTP 200 也不能证明后续长载荷始终可用。本轮测试、审查及其已记录子进程均已退出。

## 剩余门与下一步

1. 独立 QC 必须从 explore 重新开始，不能从不存在的探针接着签 report；通道可用后再做有边界的尝试。
2. 用户确认 `docs/handoffs/2026-09-22-market-recovery-decision-page.md` 的五问、三合同、5553/5565 范围及 53 只除权/送转处置；不擅自把推荐项当裁决。
3. F2 仅认证显式 recovery_members 路径；恢复 CLI 参数、未知停牌、供应商全集、mootdx 部分 flush、F3 完整输入指纹/任意并发仍未认证。依合同补实现或测试后，须为新 revision 重跑适用门禁。
4. 合并、推送、部署和生产恢复仍需明确授权；没有实际 nightly、staging 或换库验收。
