# E2 材料能力整合：工程门禁通过，真实模型交付仍阻塞

## 固定对象与授权

- 工作树：`/Users/a77/fwp-wt-e2-material-closeout`，分支 `fix/e2-material-closeout`。
- 已测代码：`1e4cc6b66ea5b6493be3235b97cb076814ed5e59`。本文及 inflight 为后续文档提交，不冒充已经测过的新代码。
- 复用原作者 P5 `fc9a130b` 与 P6 `d17ebc27`，本分支 picks 为 `1a7eb3f9`、`67214705`。
- `50cd3a13` 补无编号材料补写准入与最后公开投影复核；`f7950553` 合入当时主干；`1e4cc6b6` 补真实运行器续轮义务与来源完整性拒绝保留。
- 本分支没有合入 main，没有部署到 8792。独立审查按用户决定关闭，未重试，不记作通过。合并与生产切换仍需用户确认。
- 19:45 左右重新读取 8792：healthy，`source_revision=a26cec4d470d89bb7f0003602963ee567711e8bd`、`source_dirty=false`、`code_matches_repo=true`。该切换来自其他工作线，不能沿用早先 `0758a423` 的现状描述。

## 发现顺序

1. 先整合 P5/P6，再将编号材料题回归扩为编号/无编号两类。无编号的同一错误计算被拒后不能获零工具重写；`50cd3a13` 改为以冻结的 `material_only` 范围判定，而非依赖 `qN`。
2. 在 `f7950553` 的隔离 Workbench 实际入口发简单材料题，模型的计算是 20%，但 `claims.text` 与 draft 句子不同。协议正确拒绝；轨迹却显示外层把拒绝后的空正文当成漏答再修。
3. 同一轨迹中，底层 `mandatory_satisfiability` 只豁免编号题，把无编号 `direct_answer` 降为 optional，并从模型修复指令删除。原测试的回调替身直接返回正确答案，未执行这层。
4. 新测试接入真实 `GLMAgentRuntime`，模型和判官保持离线替身。修复前：3F/12P，明确复现续轮义务消失、终止来源错误与伪造哈希错误被重授许可。
5. `1e4cc6b6` 统一 `material_input_output_ids`，由补写准入、可满足性层和题号解析共用；按现有 `REJECTION_KINDS` 保留不可重试的完整性原因。补充正文/绑定必须保留原分句、标签及标点的提示，不放宽校验器。
6. 固定该提交跑完整工程门禁与三次真实新会话。三次均零工具，2 次被拒，1 次机器标完成但仍有锚点支持问题；停止继续抽样，不靠重复直到成功代签验收。

## 决策与被否方案

| 方案 | 结果与理由 |
| --- | --- |
| 以已确定的材料范围建立统一必答集合 | 采用。编号是表达形式，不应决定能否从材料补写；上下层必须使用同一义务集合。 |
| 只修上层准入，保留下层编号判断 | 否决。真实续轮仍会移除义务；回调替身的绿色不能证明执行者收到要求。 |
| 根据空正文判断只是漏答 | 否决。来源校验会清空正文；必须保存结构化拒绝码，不解析自然语言猜原因。 |
| 放宽逐字锚点或把来源违规改成普通格式错误 | 否决。可能掩盖材料引用错误。当前只补清晰指令，保持原拒绝边界。 |
| 把零工具材料任务伪装成已有工具证据 | 否决。沿用显式 input-only 许可，预算仍为零工具。 |
| 取三次里唯一 completed 当作成功 | 否决。逐句锚点不完整，且同源判官有漏判；run 执行完成也不等于答案通过。 |
| 未经验证直接跑正式 T2→T3 或切生产 | 否决。产品门阶段限制仍在，简单题已暴露不稳定交付；没有合并/部署授权。 |

## 工程验证

对干净 `1e4cc6b6` 成立：

| 检查 | 结果 |
| --- | --- |
| Ruff 全仓 | 通过 |
| pytest 全仓 | 11200 passed / 0 failed / 83 skipped / 2 xfailed，445.57 秒 |
| 前端 lint / typecheck / build | 全部通过 |
| Vitest | 8 files / 107 passed |
| Playwright，桌面/平板/手机 | 34 passed / 2 skipped，约 1 分钟 |
| `scripts/build_registry.py --check` | 注册表与源一致 |

原始 pytest 收据：`/Users/a77/.finance-runtime/test-receipts/20260916T114811Z-1e4cc6b6.json`。
`exit_status=0`、`dirty=false`、`worktree_dirty_total=0`。`check_test_receipt.py --expect-revision 1e4cc6b66ea5b6493be3235b97cb076814ed5e59 --base-drift-max 5` exit 0，核对时基座漂移 2。

运行工件根：`/Users/a77/.finance-runtime/e2-material-closeout-f7950553/`。目录名来自初始候选，不是其中所有工件的 revision：

- `python-gate-1e4cc6b6.log`：本候选 Ruff 与完整 pytest 日志。
- `e2e-1e4cc6b6.log`：本候选浏览器门禁。
- `live-summary-1e4cc6b6.jsonl`：从三份 Episode 原件结构化抽出的摘要。
- `sidecar-1e4cc6b6.log`：隔离服务启动与请求日志。

注意：本次设置了 `FWP_TEST_RECEIPT_DIR`，包装脚本读该变量，conftest 写方却固定默认目录，所以包装脚本最后返回找不到收据。未伪造或搬写收据；定位默认目录原件后，用 `run_main_gate.sh --receipt <原件>` 与上述校验器均 exit 0。另一个同 SHA 的 `20260916T114436Z` 是测试内自检产生的零计数收据，不得取代 11200P 原件。后续不设该目录变量，并固定具体文件而非共享 `latest.json`。

提交前定向七文件为 303P，含真实 runtime 拒绝/补写路径；它是 dirty 开发收据 `20260916T113922Z-f7950553.json`，不替代最终全仓收据。首轮浏览器失败由只设 `RE06_E2E_PORT`、未设 spec 使用的 `RE06_E2E_URL` 引起，修正运行参数后通过；没有修改产品代码绕测试。

## 真实模型探针

入口：`scripts/workbench_probe.py` → `POST /api/conversations` → 新会话消息 → 真实 Workbench/Episode，不是 CLI ask，也不是离线 parser probe。

隔离端口 8826；用户 `probe-e2-closeout-0916`；users/episode store 均在上述工件根，未写生产用户目录。启动核对 revision 与代码身份，取生产启动器的模型配置但没有修改它。三次实际写手均为 `zhipu / glm-5.3-flash`；configure 中候补为 `openai / gpt-5.6-sol`，未触发候补。

固定原题：

> 只依据材料：甲收入100万元，新增订单20万元，订单占收入比例是多少？

| 新会话 | run | 真实结果 |
| --- | --- | --- |
| `conv_25883fe122d6435baeecdf4aa96d38d4` | `run_20260916_194129_086452` | 首轮非单一 JSON 经格式修复后，仍将分号分句合成 claim，被 `material_source_violation` 拒绝；内部 partial、公开缺口稿，无外层 repair reentry。 |
| `conv_f8cb3e3062a746b4b231700fe6a47a00` | `run_20260916_194237_878006` | basis_mismatch 经格式修复，公开答案 20%；Episode completed、judge passed、`correlated_judge=true`。计算/结论句 quote 仅为“订单占收入比例是多少？”，未给计算输入锚点，不能按 D6 的逐句片段支持要求签收。 |
| `conv_0ee0e64bca1449c6b80d0d9b3cf4eeea` | `run_20260916_194319_719846` | 首轮句子绑定漂移被拒，内部 partial、公开缺口稿，无外层 repair reentry。 |

每份原件位于 `users/probe-e2-closeout-0916/runs/<run>/continuous-episode.json`，相邻有 answer/report/run/stream/trace 文件。探针打印的默认 `~/.local/share/...` 工件提示不适用于这个隔离实例。

早期失败保留：`f7950553` / `conv_67f4c8e17f384bcab83667eaa5968be7` / `run_20260916_192825_689848`，见 `live-unnumbered.log`。不把跨提交单题差异当改善幅度。样本量只有 3，不能估计通用成功率，也不是正式 P7。

两个被拒案例的 `judge_status=unavailable` / pending 标记发生于没有可供审核的合法稿，不足以推出判官服务发生超时。唯一机器完成例也不能证明独立语义核验。隔离 8826 已停止，浏览器临时服务已自动退出。

## 下一片与禁止事项

1. 先收口写手终止协议的句子绑定稳定性：保持 exact quote 和句子覆盖约束，用实际失败工件构造反例；不能通过模糊匹配、删校验或改验收题来消红。
2. 将“计算结果锚点只绑问句、同一输出别的句子才有输入”作为语义核验反例。区分模型输出格式、来源身份、事实蕴含三类问题；同源判官的 passed 不是独立支持证明。
3. 本片的作者测试不重新打开可选独立审查。后续代码变动须再跑固定版本门禁和同版本有界真实样本。
4. 正式 P7 仍需新会话原始 T2→T3、逐轴继承五格及来源限制，不能重复贴禁令、复用失败残桩或用 CLI 假冒会话。当前未解除产品门的阶段限制，未运行正式对照。
5. 不擅自合 main、不动 8792。主干期间新进 #768/#769 是交接/配置记录文档；合并前仍需重新 fetch、核对冲突与候选门禁，不能把本收据当将来合流收据。

工具沉淀：没有新建一次性探针，复用 sidecar/workbench_probe 与既有收据校验器；新增检查落实在项目回归中。可迁移模式写回 `agent-memory/10_knowledge/contract-vs-delivery-mismatch.md`，材料能力状态更新既有图谱行，没有另造能力清单。
