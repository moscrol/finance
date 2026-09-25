# Workbench 记忆异常：HTTP 验收候选

## 当前结论

测试提交：`c367aa2a702e3a40bf826982c4e936a3f50b3f14`。只修改 `intelligence/tests/test_workbench_correction_http.py`，无运行时改动。

| 层次 | 状态 | 证据与边界 |
|---|---|---|
| 全仓 Ruff、提交静态检查 | PASS | `ruff.log.txt`；提交检查通过，不等于运行测试 |
| 新 HTTP 故障测试 | BLOCKED | 本轮没有启动 pytest；资源准入持续检测到其他任务的 pytest |
| 当前候选四叶门禁 | UNKNOWN | 未执行；旧 `698fd172d` 的四叶不移签 |
| 与本轮 fetch 主干的文本合并预检 | PASS | `main-preflight.json`；无冲突，不等于实际整合或语义验收 |
| 生产 health 可达 | PASS | 2026-09-25T09:28:04Z 发起，HTTP 200，status=healthy；未认证代码身份 |
| 生产 readiness | UNKNOWN | 2026-09-25T09:28:07Z 发起，15.013 秒超时，无 HTTP 状态 |
| 真实模型采用、金融质量 | UNKNOWN | 本轮零真实模型调用 |
| 合入、生产发布 | BLOCKED | 未 push、开 PR、合 main 或部署；尚待对应验收及授权 |

`admission-01.json`、`admission-02.jsonl`、`admission-03.jsonl` 保存 09:27:36Z 至 09:32:03Z 的五次资源观测，均未准入。当时磁盘空闲仍高于 12GiB 阈值，阻塞来自其他 pytest；未干预对方，也没有留下本任务的后台等待器。准入是时点采样，不是全机锁。

`health.json`、`readiness.json` 是只读 GET 的有限字段记录，不是完整原始 HTTP 响应。health 只保留到状态字段，不能用于断言生产 revision。没有读取真实用户原文，未归档提示词或答案。

## 已实现、待运行的用例

所有场景分别固定 `WORKBENCH_ADAPTIVE_RESEARCH=off/on`，避免继承会话环境。既有同用户命中、跨用户隔离、撤回三例保留；公用断言仍验证真实 Episode 身份、证据哈希、可选先验槽和非市场事实声明。

新增检查目标：

- corrections/judgments 台账损坏：分别使用坏 JSON 和非对象行；有效纠偏不能掩盖损坏的另一台账，读取必须显示 unavailable 而非 empty，且不改源文件。
- 读取异常：首请求明确 unavailable，不暴露异常私有标记；移除故障后下一空会话能够召回。
- 两个读取超时后第三请求 busy：用同步事件保持线程阻塞，provider 边界必须先于读取完成；释放后核对旧 Episode 未被迟到结果改写，并检查新请求恢复召回。测试使用独立线程池并等待结束，不把后台线程留到临时根清理后。
- 纠偏写入的权限错误与磁盘满：在实际 `Path.open` 追加边界注入错误，验证有界失败 trace、run 降级、研究仍到 provider 边界、没有假成功行；恢复后重试可写入，顺序重复不多写，再开空会话可读。

这些是待执行的断言，不是通过结果。顺序重复不证明并发去重；测试线程的释放与回收不证明能硬取消真实卡死的磁盘 IO。无回答模型替身仍只验证送达，不验证采纳或金融答案。

## 下一步

资源准入通过后，在独占干净检出运行该测试候选，先验 HTTP，再扩大至 P0/P1、API、记忆权限和引用约束相关回归。使用主树虚拟环境及新的临时用户/收据目录；先采样，再启动 pytest，不能并行两步。

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
cd /Users/a77/fwp-wt-architecture-audit-0924
"$PY" scripts/review_probes/gate_resources.py --path .
# 只有上一步 exit 0 才继续；隔离根和收据目录应使用本轮新的临时目录。
"$PY" -m pytest -q -p no:cacheprovider \
  intelligence/tests/test_workbench_correction_http.py \
  intelligence/tests/test_memory_opening_prefetch.py \
  intelligence/tests/test_workbench_correction_ingest.py
```

如在后继文档 HEAD 运行，收据只能签那个实际 HEAD；不得把文件相同当成旧 SHA 的执行证明。最终待合入候选仍需四叶门禁和用户确认。

本轮 fetch 主干 `64847b7a173bfb7191012638e8ec044ea31e0513` 比已整合 `9d5b9800a` 多两次提交，只改三份文档。本轮没有再 merge。主干新增的 #76 L6 记录为 `BLOCKED_JUDGE_UNAVAILABLE`，属于相邻 owner 的预算/配置决策，不在本轮启用新模型或改变判官。

决策与交接：`docs/handoffs/2026-09-25-workbench-memory-faults.md`。旧整合收据：`docs/verification/2026-09-25-architecture-main-integration/README.md`。
