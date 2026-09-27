# #841 独立审查尝试与作者回归

## 裁决

- 独立 Spec / Quality：BLOCKED。两次新的只读 Codex 审查均未取得源码；不能签通过，也未证明代码有漏洞。没有重开旧 K3，没有自动重试。
- 作者结构性复核：未确认新的可利用越权问题；这不是独立签字，也不是完整安全审计。
- 定向回归：599 passed / 0 failed / 0 errors / 0 skipped，599 个唯一 JUnit 用例。不是全量门禁，不与前两次重叠读数加总。
- 自然金融质量：仍 not_passed。本阶段没有启动 Workbench 自然模型探针；代码审查代理调用不计作金融探针。
- 未合 main / #832，未部署 8792，未写生产；#793 / #794 与联合树不在本次验收范围内。

## 固定身份与收据

被测提交为 `64b0b48fa5c461f6a97911948a7585fec97c65ec`，工作树 `/Users/a77/fwp-wt-history-evidence-integration-0921`，分支 `feat/history-evidence-integration-0921`。执行前后 `git status --porcelain` 为空。相对先前全量被测提交 `f73d2133968d51d3c782d3e12ee9aa4d0618ef45` 仅有 docs 变化；本收据不能移签给未来提交或 main。

解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，依赖门禁未绕过。最终统一测试使用 `env -i PATH="$PATH" HOME="$HOME" PYTHONDONTWRITEBYTECODE=1`，树外唯一 basetemp，保留失败夹具。pytest 报告 12.87 秒；这是共享机器上的单次定向执行，不构成性能结论。

- `focused-receipt.json`：正式原收据 `20260921T161808Z-64b0b48f.json` 的逐字副本，完整测试文件列表在 `target`。
- `focused.xml.txt`：完整 JUnit 原件副本；解析器确认 tests=599、failures=0、errors=0、skipped=0。
- `receipt-check.log.txt`：对上述完整提交执行 `scripts/check_test_receipt.py --expect-revision ...`，exit 0。不含 main 漂移或实际 main 组合验收。
- `initial-559-receipt.json`、`initial-559.xml.txt`：首次继承外部环境的 559P 原件；随后改用清洁环境统一重跑，不隐去第一次记录。
- `seams-40-receipt.json`、`seams-40.xml.txt`：清洁环境追加的 40P 原件，随后纳入最终 599P。

原件目录为 `~/.finance-runtime/reviews/react-trace-integration-20260921/history-review-attempt-64b0/`；初次 XML 位于同级 `history-main-f73d21339/post-review-focused.xml`，补充 XML 为同级 `post-review-seams.xml`。本次 pytest 控制台输出由会话工具返回，未另存完整 stdout 日志；不得把人工摘要冒充原始日志。

## 独立审查阻塞

`independent-spec-review.txt` 与 `independent-security-review.txt` 为原样副本。两次审查工具均报告缺少 `/Users/a77/.local/bin/codex-code-mode-host`，备用本地读取也被权限拒绝；本代理随后 `test -e` 返回 1，确认该特定路径缺失。机器上另一个应用目录存在正在使用的同名宿主进程，不能把特定配置路径失效说成整台机器没有此工具；未修改共享工具配置，也未对其他会话进程采取动作。

本次独立审查没有读取到源码、没有核验被测 SHA、没有运行测试。作者读源码和回归不能补签它们的空白。

## 作者复核范围与边界

1. `HistorySession.read` 每次进入 `RunStore.read_history_artifact(..., conversation_id=...)`；缓存仅作展示，不授予读取权限。后者在同一 run 写锁内重新读取元数据并校验登记、可见性、可下载性、SHA 和大小，仅读一次内容。锁只协调遵循它的写入者，不防直接改盘。
2. `refresh()` 替换旧引用集合；测试压缓存有无、用户/会话/可见性变化、登记删除、内容损坏、等待锁时变化，以及拒绝后的状态纯净。
3. 行身份与内容 hash 跨页稳定，分块观察值只包含本卡实际可见数字；严格恢复拒绝缺失或错绑元数据。hash / provenance 只证明结构与一致性，不认证上游事实或原始归属。
4. 判官选集为绑定证据与正文可反解显式引用的并集；未绑定且未引用的卡不自动入选。研究限定和结构化数字能进入此视图，不等于真实判官已消费或正确理解。
5. 缺结束日期、错误 URL、工具异常仍回到同轮反馈，已成功证据保留。条件定义删除后孤立计数引用修复有离线覆盖。
6. `ASK_SEMANTIC_JUDGE=off` 的确定性检查不能算独立模型判官，回归覆盖收据及评测分母。
7. HTTP 公共产物下载是用户命名空间合同，不是模型工具的同会话合同；路由不调用历史授权 reader，也没有相同的 SHA/大小校验。认证中间件在 `cf_access` 模式重写客户端身份，`off` 模式允许本机自报 user。此次仅运行既有公开下载、internal 隐藏和路径穿越测试，没有验证部署配置或完整认证攻击面。不能把工具读取加固概括为整个 HTTP 下载链已同等加固。

## 下一步与不做项

先恢复可读源码的独立审查入口，对固定 revision 新建审查；不得覆盖本次阻塞原件。真实金融验收需先固定题目、模型、provider 尝试硬上限、墙钟时限与停止规则，再使用 `scripts/workbench_probe.py` 的会话消息入口，核对 225/25 与有效分母、自然数字引用和判官实际证据。当前没有选择新的自然调用预算，故未启动。

最终合入需另行授权，并冻结实际候选/main 组合验收。本次没有新运行时能力、没有通用工装或门禁变更；复用既有 pytest、收据与归档校验器，不新增第二套工具清单。旧五个证据包保持不变。
