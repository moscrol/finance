# #868 沙箱作者测试准入修补

## 背景与授权

用户在合并部署准备度检查后要求「推进」「继续」，本轮只推进离线修补、回归与向原 owner 交付。没有新增付费模型请求，没有启动 L6、合入 main 或切换 8792；不修改 owner 工作树、封存审查原件、预算或判决。

工作树 `~/fwp-wt-pr868-delivery-validation-0924`，分支 `fix/pr868-delivery-validation-0924`，WIP #910，base=`feat/adaptive-research-loop`。从既有 f59301ea5 前向原 owner `89624eac7e76c325c14aeee090bc4610bf05f97c`，无冲突合并提交 `80a84801c965c18bf31260dc51cb7c20d8eab9d6`；实现与受测版本为 `ff62eeeb5cbb27f4198202278298f7296f89a89c`。未纳入 #911 新增的 HTTP 研究链测试。

最新审查原件根 `~/.finance-runtime/reviews/pr868-glm-qc-20260925-next` 已结束，`host-audit.json` 记本批 68 次、累计 281/291。候选 f2610293f、基座 03352758c；spec 原件 `CHANGES_REQUIRED`，明确 C3/C5/C7 缺行为证据；quality `PASS_WITH_LIMITS`，C1/C3/C6/C7 未验证。findings 为空不撤销 spec 的补验要求，跨批、跨轴汇总也不改写各轴结论。原件优先于此前未开跑的交接和宿主解释。本轮回归不是独立签字。

## 按发现顺序

1. 最新 main 的 conftest 通过 `workspace_env.python_path()` 找解释器；工具环境未传显式路径时会执行 `git rev-parse`。受保护候选的 `.git` 不可读，C7 在收集阶段失败。已有 `FWP_WORKBENCH_PYTHON` 绝对路径接口可绕开 Git 发现过程，不必绕过依赖检查。
2. 修改正式生成器，而非封存模板或已结束批次。生成的 `review.mjs` 先拒绝相对解释器路径，再传 `FWP_WORKBENCH_PYTHON=CONFIG.python`，不设置 `FWP_ALLOW_ANY_PYTHON`。
3. 将后续批已有的候选目录 metadata-only 规则和 `/usr/bin/security` 执行禁令纳入生成器。metadata 是目录存在性、类型等元数据，不是文件正文读取权限。预检实际验证 `.git` 正文、秘密与外部路径仍禁读，Keychain CLI 不可执行，网络限制仍在。
4. 真实 pytest 遍历需要候选树及祖先元数据。C7 又在 work 内创建临时 Git 仓库，Git 对工作目录祖先执行 stat；只放候选祖先不足，开发 dev-05 的 C7 两轴均因证据根祖先 `Operation not permitted` 失败。将 axis root 的祖先逐个 literal metadata 加入，保留原正文权限范围；不开放 Git common-dir，也不放宽整棵家目录。
5. `sandbox_preflight.mjs` 现在在真实工具沙箱中收集两个作者测试文件。PASS 收据明确写 `author-test collection (not execution)`，不把收集当执行。
6. 另加真实执行回归：C3 跑迟到判官、零子窗口预算、根预算耗尽三个现有作者测试；仅把诊断服务的随机端口映射到已许可 26001-26008，并观察真实返回字段，不伪造时钟、传输或判官返回。C7 跑整个 `tests/test_main_gate_receipt.py`，JUnit 必须非空且无失败/跳过，核到身份/范围、完整输出持久化、disposable basetemp 拒绝及坏收据拒收等具名检查。
7. 双轴撤掉解释器绑定，确认回到 `rev-parse` 失败；相对路径在执行前拒收；撤元数据权限或 Keychain 禁令，预检失败且不产生 PASS。原路径反馈、原预算硬停、交付后消失检查及真实 Pi CLI/本地假响应回归保留。

## 方案取舍

| 方案 | 决定与理由 |
| --- | --- |
| 开放候选 `.git` / Git common-dir | 否。所需是解释器选择，现有显式接口即可，额外正文权限无必要。 |
| `FWP_ALLOW_ANY_PYTHON=1` 或删除 conftest | 否。隐藏解释器/依赖漂移，测试绿不再可信。 |
| 只传变量、不验证真实收集/执行 | 否。实际发现祖先 metadata 还会阻塞 pytest 和临时 Git 仓库。 |
| 精确目录 metadata + 正文禁读负控 | 采用。准入真实操作，保留受保护内容边界。 |
| 扩大本地网络端口范围 | 否。测试端口适配既有允许范围即可，不改生产 19899 路由。 |
| 作者回归代替 spec 补审 | 否。只能证明准入及作者所验行为，独立审查者仍须独立核验并交付。 |
| 新造测试/审查框架 | 否。复用现有生成器、真实工具接口、作者测试、JUnit 与收据校验器。 |

## 冻结验证

解释器 `/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，Python 3.12.13，httpx 0.28.1，依赖指纹 `66726d345bf37ce5`。共享 venv 未改，依赖门禁未绕过。运行时显式设置同路径 `FWP_WORKBENCH_PYTHON`。

四目标无切片回归：

```text
tests/test_pi_review_repair.py                         73 passed
tests/test_workspace.py                               25 passed
intelligence/tests/test_llm_timeout_diagnostic.py      35 passed
tests/test_main_gate_receipt.py                        66 passed
```

合计 **199P/0F/0E/0S，collected199，218.59 秒**，干净 ff62eeeb5。内层 C3 两轴各 3P、C7 两轴各 66P 是外层四个测试的执行内容，不再次加到 199 的分母。

- 正式收据 `~/.finance-runtime/test-receipts/20260924T175321Z-ff62eeeb-3697aad16274.json`；精确 revision、四个 `--require-target`、`--require-full-scope` 校验 exit0。这里 full-scope 只代表四目标未切片，不是全仓。
- 原始输出、进程退出与 JUnit：`~/.finance-runtime/reviews/pr868-sandbox-env-offline-20260925/frozen-ff62eeeb5/` 下 `regression.log`、`regression.process.json`、`pytest.xml`。命令/受测身份在 process JSON。进程完成 exit0，测试与监督进程均退出。
- C3 字段原件在该根 `pytest-tmp/test_real_author_checks_execut0/sandbox-inputs/spec/work/author-ports.json` 与 `execut1/.../quality/work/author-ports.json`；0.8 秒窗口下分别耗时约 0.802/0.806 秒，实际发送各 1 请求且收到 headers，`report_received=false`、`unavailable=true`，root 从 9.6 秒扣至约 8.798/8.794 秒。仅为本次观察，不作性能基准或完整语义判官质量结论。
- C7 原件在 `execut2/.../spec/work/author-checks.xml`、`execut3/.../quality/work/author-checks.xml`，各 66 项，无失败/跳过。
- Ruff 全仓、相对 owner 的 `git diff --check`、提交钩子通过。workspace doctor 为 offline ready、无依赖漂移；地图仍落后一个代码提交，不宣称当前架构已完整校验。doctor 没有 `--offline` 参数，实际命令是不带该参数的 `doctor`。
- 开发失败保留：dev-01 父目录不存在造成 setup errors；dev-02/03 发现元数据权限缺口；dev-04 为局部 8P；dev-05 为 8P/2F，收据 `20260924T173206Z-80a84801-634726cb71a5.json`；dev-06 为局部 4P、收据 `20260924T173447Z-80a84801-23936d70f3cf.json`。均为脏树诊断，不代冻结收据。

## 接续与边界

原 owner 审阅 #910 后采用；生成器默认仍是历史候选配置，不能直接启动。下一批要在新证据根重新绑定最终候选/基座、解释器、输入指纹与工程准入，先执行真实沙箱预检和相应作者检查，再按新授权运行独立补审。不要覆盖或续跑 1405/2105/next 封存批，不沿用剩余额度作隐含重试批准。

本轮未跑全仓 Python、前端或最终 #910+#911 组合门禁，不证明自然金融研究、真实模型纠错或 8792 TCP/浏览器行为。旧 57P、f261 工程绿、ff62 的 199P、后续文档 HEAD 各属自身范围，不移签。独审闭合后才接已授权的 #76/L6；main 合入和部署还需分别确认。

工具沉淀复用 `prepare_pi_review_repair.py` 与现有测试，不新造通用工具。可迁移点是“权限准入必须跑到真实操作”，在共享知识既有同名小节补充本次实例。`~/harness-reference/BUILD.md` 有他人改动，本轮未动该树；没有新增需推广的框架。
