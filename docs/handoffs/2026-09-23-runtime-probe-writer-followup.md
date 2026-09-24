# Runtime 探针量具修复与 K3 写手尝试

## 结论与身份

用户本轮明确说“k3可以用啊，你可以用它当写手”。已实际调用 K3 两次，但两次均在执行工具前失败，没有 K3 写手代码产物。随后 Codex 在新副本修复量具，宿主验证通过；不冒称 K3 完成，不把局部通过替代历史全局独审 BLOCKED。

只读被测 revision：`760248ecebc79fbe4f2686ddd42255c1a00ec862`。产品源码未改，原 K3 探针三文件哈希未变，候选树前后均干净。当前工具分支 `test/runtime-probe-repair-0923` 继承文档提交 `1ef5bc3ec`，产品基座 `ffd1b7f15`；这不是对后来 main 的全量验收。

## K3 写手执行记录

| 场次 | 结果 | 边界 |
| --- | --- | --- |
| runtime-probe-k3-writer-20260923-01 | 1 次请求，124.769 秒，Request timed out | 0 工具、无报告/代码，原场保留 |
| runtime-probe-k3-writer-20260923-02 | 手动补试 1 次请求，126.488 秒，上游 CloudFront HTTP 504 | 单请求等待上限已由 120 调至 300 秒，仍收到上游超时；0 工具、无报告/代码 |

两场固定 `mirasim-kimi/kimi-k3`，无自动重试、无模型回退、无购买、无生产写入。第二场 thinking 改为 medium，任务与只写本场 work 的权限不变。每场启动前零模型预检通过。两场均已退出；不得把 runner exit 0 当作写手成功。调用是否计费未知，不依据返回 usage=0 声称免费。

本地网关 `/health` HTTP 200 只说明网关活着，不说明模型服务可用。没有修改网关、重启服务或把超时误记为额度不足。原件根均在 `~/.finance-runtime/reviews/` 下上述具名目录。

## 宿主修复范围

工具：`scripts/review_probes/runtime_identity_effects/`；说明与一条复跑命令在其 README。

- 未派发应用调用直接断言 payload 的 error/detail 和 unknown effects 空集，避免对 mappingproxy 直接 JSON 编码。
- 合法身份但属主不匹配仍精确要求 RestoreUnavailable；上下文内部 episode_id 不一致单独要求 ValueError。每个拒绝场景对持久化事件、检查点及预算快照逐字节比对，排除锁 inode。不用宽异常元组把任何错误都当通过。
- shadow 模块先注册 sys.modules，再执行 dataclass 定义；失败回收。异常类型取被测模块自己的类，不让真实/影子异常类不同造成假红。
- identity/budget 独立开关，预算测试确实调用 shadow 的 restore_root_budget。守卫替换必须精确匹配一次，真实模块和候选源码不变。
- 每阶段新子进程、隔离用户根、无缓存写入，原始输出/JUnit/命令/哈希保留。验收按精确具名失败、失败原因、分母与退出码综合判定；收集/导入错误、超时、无关红、漏跑、跳过和变异存活都拒绝。
- 具名探针用 `*_checks.py`，不被全仓 pytest 默认收集。只有显式 runner 才运行这组变异。

## 实际验证

最终仓内版本再次在 macOS sandbox 下执行，禁止网络及输出根之外的写入：

| 阶段 | 实测 |
| --- | --- |
| 基线 | 16 passed |
| 身份保护撤除 | 7 个指定 DID NOT RAISE 失败，4 个正常对照 passed，0 error |
| 预算保护撤除 | 2 个指定 DID NOT RAISE 失败，3 个对照 passed，0 error |
| 还原后基线 | 16 passed |
| runner 自测 | 13 passed，含假红/存活/分母/跳过/输出保护/候选身份/显式选择 |
| 目标 Ruff | 通过 |

身份 7 红覆盖 user、conversation、run、assistant message、episode mismatch、绑定双向不对称；预算 2 红覆盖未对账余额禁止恢复和恢复后持久化清单继续禁花。7+2 是具名失败数，不是 9 种独立产品变异；实际只有两种撤保护。

宿主首轮 15P/1F 因泄漏检查对嵌套 mappingproxy 编码失败，量具明确拒绝该轮，随后改用 `EpisodeEvent.to_dict()`，原首红保留。runner 自测第一次在收集前因宿主命令漏设沙箱 TMPDIR 失败，补设允许的临时根后 12P；增加默认收集隔离自测后最终 13P。没有改产品来迁就探针。

## 证据与可迁移工具

`docs/verification/2026-09-23-runtime-probe-repair/` 封存 9 个选定原件及 MANIFEST：两个 K3 执行记录、宿主完整四阶段收据/输出、13 项自测 JUnit、宿主首轮基线红。日志改后缀 `.log.txt` 只为避开 Git 全局日志忽略规则，内容未改。原始 pytest 日志包含尾部空白，`git diff --check` 会报告这些归档行；保留字节，不以格式化改写证据，源码/文档另行检查。

完整本机场景：`~/.finance-runtime/reviews/runtime-probe-host-repair-20260923/runs/` 下 first、repaired、portable、unit-final；前两轮与移入仓后的 portable 分开，不覆盖旧记录。

这次把“测试失败必须是指定安全断言，不能只看 exit=1”做成可执行工具和自测。没有扩展共享 harness-reference：该仓此前检测为脏且有在途提交，本轮不动它。工具只签这组量具，不增设第二份能力清单。

## 决策与剩余

不无限重试 K3，因为已取得两次真实失败且没有代码产物；不伪造作者，宿主继续做已定位的小片修复。保留原 K3 报告及历史 BLOCKED。新场次可在通道恢复后让 K3接着编写单项动态验证，而不是重新通读八项全栈合同。

未覆盖：保存失败围栏、写锁争用、重入、inbox 排空、完整公开投影/交付、各入口异常合同、真实计费、跨机锁和完整跨进程恢复驱动。未跑当前工具分支全仓/前端门禁，没有合并或部署授权转移。本轮不推送、不合 main、不部署、不删原件。
