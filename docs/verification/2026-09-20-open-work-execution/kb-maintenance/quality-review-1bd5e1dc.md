# KB 维护链独立 Quality 审查

**Quality：REQUEST CHANGES。确认 1 项 P2，不能签发 PASS。**

范围为 `1254224be89e2c4974350b7f3e985dbedb5dc043` → `1bd5e1dc8d48f59461c79f35ea553e1cda71a6ec`。审查使用独立 detached 树 `/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/quality-1bd5e1dc/knowledge-base-private`；开始与探针运行前核对 exact HEAD、工作树 clean。金融依赖固定为 `gate-generation-final/finance-workspace-private@4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`，解释器为主金融仓 `.venv-workbench/bin/python`。不以会漂移的作者树作为审查对象。

## P2：activate 校验后失去根或锁身份，仍写 current 并返回成功

位置：[skills/lib/rag/generation.py:180](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/quality-1bd5e1dc/knowledge-base-private/skills/lib/rag/generation.py:180)，写入发生在同文件第 183 行。

`writer_lock` 进入时检查一次身份；`resolve_startup()` 完整验证 manifest、代码、源文件和双索引后，`activate()` 直接调用 `atomic_json(root / "current.json", pointer)`。这次写入前没有 `assert_writer(root)`，而 `atomic_json` 只检查路径规范性及软链，不检查原根 inode 或持有的锁 inode。因此，验证期间根目录被换位，或 `.writer.lock` 被另一个普通文件替换时，持有旧 inode 的进程仍可以写控制指针并宣称切换成功。

这是已实证的正确性问题，不是风格建议。规范 [docs/rag-guarded-maintenance.md:76](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/quality-1bd5e1dc/knowledge-base-private/docs/rag-guarded-maintenance.md:76) 明确要求：“未知锁目录 / 换链 / 锁 inode 被替换均报错。”它也违背本轮需求的“副作用前取锁”和“current 不冒充”。

已有定向证据：[activation-results.json](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/quality-1bd5e1dc-evidence/activation-results.json)，[原探针](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/quality-1bd5e1dc-evidence/probe_activation_identity.py)。探针只建立临时两页资料、hash 双索引，先走真实 prepare / approve / activate，再在第二次 activate 的真实 `resolve_startup` 返回点注入文件系统身份变化；未伪造校验结果、未调用远端。

| 已完成的故障注入 | 实际结果 |
|---|---|
| 原 root 重命名，同路径创建无批准代的新目录 | `activate_returned_success=true`；新根出现 `current.json`；立即 resolve 抛 `FileNotFoundError`，因为对应 generation 不存在。移走的原根中旧 current 字节保留。 |
| 原 `.writer.lock` 重命名，同路径创建新 inode | 替换锁可独立取得排他锁；原 activate 仍返回成功并重写 current。 |

建议在完整校验结束后、控制目录和控制文件写入之前重新断言 writer 身份，并统一约束正常成功路径的控制写入。将上述 root / lock 两个反例保留为回归。`approve` 与 prepare 最后写 validated 的同类位置应由作者一并核查；本报告没有为它们新增确认结论。

## 其他范围与限制

已阅读新增维护、身份、I/O、验证模块及 hook / ingest / writer / fetch / publish 入口，核对仓内 AGENTS 与维护文档。职责拆分、显式输入、双索引整体发布、失败保留和传输边界总体清晰；截至停止追加验证，除上述 P2 外未确认其他可执行修复项。不因新文件长度或自动工具已约束的格式提出问题。

父代理通知本轮发生平台中断，随后将任务收窄为只读文档收尾。本报告只整理中断前已完成并返回 exit 0 的上述机器结果与固定源码；收到收窄指令后未运行新探针、进程操作或文件系统故障注入。未完成的补充检查不记为通过。没有复跑全量，也不把作者 899 项收据或独立 Spec PASS 充作本审查的 Quality PASS。

审查未修改作者代码、生产索引、uchg、8792、launchd 或已安装 hook，未上传资产、调用付费模型或合并 main。修复后的候选须另核固定差异与已有测试收据；此报告只针对 `1bd5e1dc`。
