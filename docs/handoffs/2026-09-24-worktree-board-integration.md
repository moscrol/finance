# #84 当前主线集成与发布边界

## 本轮目标与身份

用户要求「继续推进直到可以合并部署」。按推进到可合并、可发布处理，不将这句话扩成删除工作树、重开 K3、关闭 #812 或切换整个 8792 服务的授权。

`fix/worktree-board-hardening-0923` 已合入 `main@3bb81b9638f97b4773ce0f338df3a505b7c0162f`（合并提交 `83ac274ea`），再合入 #903 的验收文档（`98c3ffea9`）。唯一冲突是 INDEX #84 状态行，保留较新的固定候选验收事实，再由本轮状态替代入口。旧 `b26b8711a` 与其四叶收据均保留，不能给本轮集成 head 移签。

本轮可变的验收状态放在树外，避免验完后为补数字改变 head：

`~/.finance-runtime/reviews/worktree-board-hardening-20260924/integration-01/`

该目录的 `README.md` 是最新人工摘要，`result.json` 是逐叶身份/哈希核验结果；缺文件、complete=false、revision 与候选不符、dirty=true 或任何必需步骤非零均不得放行。不能把本段的目录指针当作通过结论。

## plist 兼容性

上一轮全扫描 335 行均未知，来源是一份 macOS 能解析而 Python Expat 拒绝的 LaunchAgent plist。原文件 XML 注释含 `--detach`，严格 XML 注释不允许双连字符；不是 ProgramArguments 中的裸 `&`。本轮先用原文件字节经 `/usr/bin/plutil -convert binary1 -o - -- -` 实测转换成功，再补共享采样器。

标准 XML/二进制 plist 仍优先用 plistlib，无额外进程；仅 macOS 且标准解析失败时用系统转换器，再用 plistlib 读取结构化结果。输入是已经采样的 bytes，不二次读路径、不写回、不做字符替换修补。调用有 timeout，非零退出、超时、不可用、损坏输出或非字典根均保留 unknown，不能解释为没有引用。两个入口继续共享此实现。

开发态定向测试 59P。撤 native fallback 的真实 macOS 反例 1F、撤 dirty 保护 1F、固定旧版九反例 9F；这些是反例证据，不是最终干净 head 四叶收据。首次真实测试夹具误用了 macOS 同样拒绝的裸 `&`，保留 58P/1F 原日志；之后改为复现原文件的注释差异，不放宽生产断言。实机 context 采样 errors=[]，原 plist SHA256 始终 `0e872c88c3599e75188bfb69aba7923d056aab5d47fe3b7571d8e2e6204e39e5`。

## 验收方法

- 只使用主树 `.venv-workbench/bin/python`；白名单环境不含 `GATE_KEEP_BASETEMP`。上一轮污染门禁默认清理测试的教训不重复。
- pytest 使用 `tmp_path_retention_policy=failed`，只让测试框架释放本轮成功的临时夹具，保留失败夹具、所有正式日志和旧证据。此设置不筛选测试；收据仍须通过 `--require-full-scope`，与 JUnit、进程退出码逐项对平。
- frontend 在同 SHA 独立树运行正式六步。Node 22.23.2 从 nodejs.org 下载并按官方 SHASUMS256 核验；只在本轮 PATH 使用，不替换主机 Node 26。
- 本轮仍有 3 GiB 运行期磁盘保护；不干预其他会话进程，不删除真实工作树，不靠清空旧红证据获得空间。
- 最终前端/Python/registry/看板、漂移门与预览树均须绑定本轮固定 head；最新 main 变化时重新判断适用性，不用旧计数顶替。

## 发布是什么

本单净代码变更仅为 `scripts/worktree_board.py`、`scripts/worktree_safety.py`、`scripts/cleanup_gate_trees.sh` 及对应测试。它是仓内 CLI 工具，不是常驻服务。`scripts/session_facts.sh` 从当前检出的 `$REPO/scripts/worktree_board.py --this` 读取事实，其注入格式未改。

因此发布单位是完整 Git 提交：看板和清理入口必须与同提交的共享模块一起使用，不能只复制一个脚本。可在固定检出上直接运行看板，`--this` 与 `--json` 是只读发布冒烟；清理入口只验证 `--help` 和测试内隔离 dry-run，不对真实树调用 `--apply`。

合并授权到位后，先核用户批准的 head/base 和四叶条件，再用有身份约束及记录的合并入口；合后核预览树与主线树一致，随后在新的完整检出验证 CLI。共享主检出存在别人的未提交代码与 ingest 产物，不能 pull、reset 或 rsync 覆盖它。不会为更新这些工具去重启 8792、修改 LaunchAgents、写 DuckDB 或改生产模型；整个 Workbench 服务的发布归其独立工单。

## 决策与后续

| 采用 | 未采用 | 原因 |
|---|---|---|
| 前向 main 并纳入 #903 后统一验证 | 拿旧 b26 四叶绕过基座漂移 | 新组合必须有自己的收据 |
| macOS 标准转换器只读降级 | 修改仓外 plist / 正则改 XML / 吞掉异常 | 原配置能被系统解析；保持结构化语义与失败阻塞 |
| 固定 head + 树外结果指针 | 测完为填数字再改源分支 | 收据必须与最终 PR head 一致 |
| 按 CLI 工具发布 | 为本单顺带切整套金融服务 | 运行与数据副作用范围不同，不借工具工单替服务发布放行 |

12 棵 ownership 树仍按原表保留。#64 的完整判据与逐树授权独立，K3 与 #812 历史结论不升级。最终是否可放行只读上述本轮验收目录与 PR 最新评论，不从历史快照中的 PASS 或 BLOCKED 字样推断。
