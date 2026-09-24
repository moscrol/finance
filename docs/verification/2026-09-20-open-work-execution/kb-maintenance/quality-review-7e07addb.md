# KB 维护链最终 Quality 静态复核

**Quality 静态审查 PASS。此前唯一 P2 已从固定源码及对应作者回归得到关闭依据；本次增量未发现剩余可行动问题。**

本轮严格只读审查 `1bd5e1dc8d48f59461c79f35ea553e1cda71a6ec` → `7e07addb466385085e21ccaf3d06bf23c6e4b0a1`，共五文件、133 行新增 / 4 行删除。开始时作者树 `/Users/a77/kb-wt-guarded-maintenance-0920` 的 HEAD 为目标 SHA、状态 clean；结论依据指定 SHA 的 `git diff` / `git show`，不依赖之后可能变化的工作树内容。本轮只写本报告。

## 原 P2 关闭依据

[generation.py:185](/Users/a77/kb-wt-guarded-maintenance-0920/skills/lib/rag/generation.py:185) 在真实 `resolve_startup()` 完整验证完成后、`atomic_json(current.json)` 之前调用 `assert_writer(root)`。后者同时核对原 root 的设备号 / inode、持有的锁文件描述符与当前锁路径的 inode。此前独立探针的两个确定性变化点——验证返回后替换 root 或 `.writer.lock`——因此均会在 current 写入前抛出身份错误。

对应正式回归 [test_guarded_maintenance.py:370](/Users/a77/kb-wt-guarded-maintenance-0920/skills/lib/rag/tests/test_guarded_maintenance.py:370) 保留真实 prepare / approve、真实验证函数及实际目录 / 锁重命名；只在返回边界注入变化，不伪造校验结果。测试要求明确的 `identity changed` 错误、旧 current 字节不变、替换根只剩预置的 `unknown-owner`。这覆盖了原 P2 的触发条件和错误副作用，并增加切换至已批准下一代的场景。

作者保留的 [首红日志](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/success-control-boundaries-red.log) 为 **8 failed / 2 passed**，包含 `activate-root` 与 `activate-lock`；[首修日志](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/success-control-boundaries-green.log) 为 **1 failed / 77 passed**，剩余失败是 approve 根换位后错误类型不符。最终源码增加 approve 验证后立即检查，未放宽断言；[最终定向日志](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/success-control-final-focused.log) 为 **80 passed**。

## 其余增量

- approve 在完整验证后、读取批准摘要后 / 创建目录前分别检查身份，避免失权后向新根写批准记录。
- prepare 在消费者子进程返回后、seal 完成后以及验证收据写入前检查身份；失权后的异常分支仍禁止补写失败收据。
- publisher 在加锁后的 manifest 验证完成后、远端元数据返回后检查身份，再创建尝试目录或回读目录。新增回归核对不再发起下载、完整包保留、旧 current 不变，以及已失权时保留原 `running / remote_may_exist=true` 收据而不冒充成功。
- request 的最终写入前检查其独立请求锁。修改沿用已有检查函数，未引入新的公共抽象或扩大生产副作用。

新增十二个参数化回归覆盖四类控制写入与两处 publisher 边界的 root / lock 替换。源码变更小，职责与错误处理保持清晰；未发现需要新增修复的复杂度或维护性问题。

## 收据和结论边界

已只读查阅作者的 [全量日志](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/full-7e07addb4.log)：**911 passed**；[strict-vocab](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/strict-vocab-7e07addb4.log)：**0 错误 / 2 告警**；[文件体积门](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/file-sizes-7e07addb4.log)：通过；[quality-gate](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/quality-gate-7e07addb4.log)：`passed=true`、`no_regression_with_debt`。这些是引用的作者收据；历史质量债务仍在，不能表述为知识库质量良好。

本次为**独立静态复核 + 引用作者回归**。没有运行测试、新独立探针或故障注入；原独立动态探针没有在 `7e07addb` 重跑，不能称其已独立动态通过。[旧版 Quality 报告](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/quality-review-1bd5e1dc.md)、原失败证据及平台中断限制原样保留。本结论不替代合并授权、生产迁移或真实远端上传验收。
