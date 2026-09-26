# PR #789 Standards 轴独立审查

固定 base：`4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`。
固定 head：`c8dbd387ff2ddf28546a5a668296c762e0dd951a`。
审查树：`/Users/a77/fwp-wt-open-work-spec`，开工 clean；另一冻结全量测试树未访问或修改。

Diff：`git diff 4ace5ec2e9b7735d90eb15bc2351fa193c1120b8...c8dbd387ff2ddf28546a5a668296c762e0dd951a`。
提交：`c8dbd387 / 3c3663d1 / 30ad71a8 / 7bae41a4 / cc3bc795 / 0b8a304b / 95678f5e / 6fb77055 / 95016d6b / 50848ea0`。

仅独立审查 Standards 轴，未读取本轮另一轴报告。代码地图查询返回 stale，未据此作当前实现结论；未在候选上重建地图。

## 规范与判定

- `AGENTS.md:15`：pytest/ruff 用指定 `.venv-workbench/bin/python`。本轮离线复验使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- `AGENTS.md:57`：任一叶子红或无结论均不可合并。新增 runner 在子命令失败、Git 身份失败、不完整运行时返回非零；通过返回值未遮住后续/前面的失败。
- `docs/workflows/acceptance-workflow.md:16–21`：指定解释器、`env -i` 测试壳与独立检出；收据须绑定被测 SHA。
- `docs/workflows/acceptance-workflow.md:61–72`：首尾 SHA 与期望完全一致、完整检查、无脏文件，Git 查询失败不可解释为干净；禁止覆盖旧目录；承认首尾采样不能发现期间改后恢复。
- `test-environment.json`：解释器固定 Python 3.12.13；其 `code_path_prefixes` / `data_path_exceptions` 明确供 Python pytest 收据使用。本新增前端入口按验收文档要求观察全树 Git 状态，不把它误判为违反 Python 收据的脏文件口径。
- `scripts/`、`tests/`、`docs/` 下未发现更近的 `AGENTS.md`。

未发现可复现的合同内硬违规。逐项考虑固定 smell baseline，未发现值得报告的 possible smell；没有把短 JSON 收据脚本的字典、局部辅助函数或命名偏好升级为重构阻断。

## 独立验证

复制固定 runner 与定向测试至本报告相邻 `standards-probes/`，并禁用字节码、pytest cache 与仓内 conftest：10 passed。没有运行前端构建、全量 Python、真实模型或生产服务。

复制源码 SHA256：`4fa9fd9a8e40507eb7a26e90f46928ac066551225cd6abb91d84370d3c427f32`，与候选及已存前端收据的 runner hash 相符。

`standards-probes/probe_boundaries.py` 使用真实临时 Git 仓和真实子进程验证：

| 边界 | 实际结果 |
| --- | --- |
| 子进程成功后 Git 身份不可读 | code 2，identity_after/dirty 未伪装为干净 |
| 初始 Unicode 未跟踪文件 | code 2，未执行子命令 |
| 输出路径经软链进入被测树 | 在创建输出前拒绝 |
| 空命令集 | code 1，complete=false |
| 缺子进程 cwd | code 1，子命令记 127 |

脚本生成 `standards-probes/boundary-results.json`；合成仓在脚本结束后删除，未触碰候选。

档案只抽核 `qc-followup/frontend-795/frontend.json`、`frontend-796/frontend.json`：两份记录各六个命令，12 份已入 Git 日志的长度和 SHA256 均与收据一致，首尾 revision 与各自 expected revision 一致，runner hash 与候选一致。它们证明各自历史身份，不冒充 c8dbd387 的当前全量结论；没有批量读取旧大日志或另一轴评审。

## 非阻断调用边界

`scripts/run_frontend_gate.py:37–40` 的 Git 调用没有显式 `env`，会继承宿主 Git 环境变量；`:155–162` 只为被测子进程创建清理后的环境。真实离线反例：两个内容一致、HEAD 不同的临时仓，在启动环境令 `GIT_DIR` 指向另一仓，传入另一仓 SHA，检查仍在目标树 cwd 执行，但收据为 code 0 / identity_stable=true / dirty=false。`boundary-results.json` 保存本轮实际两个 SHA。

这一反例主动违反 `acceptance-workflow.md:17` 的 `env -i` 前提，因此本轴不把它列为现行规范违例；它是直接调用入口时必须保留的运行条件。可选加固：让身份查询使用同一清理环境，或显式去除 Git 的目录/索引/工作树覆盖变量，并加入相应反例测试。不要仅凭本反例取消其他已证实的通过结论。

## 限制

子命令未设全链 deadline；现有验收规范没有要求本工具实现截止时间，本轮不据此阻断。macOS/指定 Python 3.12 是本次验证平台；没有宣称 Windows 已验证。输出写盘失败只会使进程非零或保留未完成收据，未发现因写盘失败产生新绿收据的路径。所有结论不包含合并或生产验收授权。
