# 机制表示研究试验：首片决策快照

## 背景

用户讨论：理解可能来自更好的表示和结构压缩，创造可以从压缩模型生成新可能性。对投研的启发不能直接变成“模型更简洁，所以预测更准”。此前建议以相同材料、相同预算比较逐条整理与机制/竞争解释/区分变量组织，并把事实、机制、预测增益和投资价值分开验证。用户随后说“你来推进”。

## 发现顺序

1. 默认工作树停在 `b4a35fa2`、detached 且有大量既有未提交改动。读取项目门、能力图谱与交接后，fetch Gitea 并从 `gitea/main@c29a64011da4` 建隔离树 `/Users/a77/fwp-wt-mechanism-pilot`，分支 `feat/mechanism-research-pilot`。不触碰原树，不切生产。
2. 读取现有 method_validation、research_validation、product_value 与评测工件合同，确认已有多套验证能力，但研究组织的选择题得分不符合收益/概率实验合同。
3. 原子领取 `R-20260916-04`。新增台账先登记 ledger-map，再写脚本。原件放 `~/.finance-runtime/mechanism-pilot/R-20260916-04/`，不写进生产用户台账。
4. 当前进程 `detect_providers()` 为 `[]`。没有尝试借用生产用户身份或读取 Keychain；仍可开发、测试和冻结离线量具。
5. 实现两组相同公共任务/输出字段，只改组织指令；6个明确合成案例、12格；冻结提示词/材料/预算/代码哈希，模型只接收问题/事实/选项，不收答案键。
6. 首轮测试抓出续跑未绑定 reasoning_effort、进行中无答卷被叫作 interrupted。已补配置绑定并改名 attempted_without_response。再补错误选择扣分与并发占位测试。
7. 最终定向180项通过、全仓Ruff通过。prepare成功，run明确因未配置模型退出2且0调用，report pending/12格not_run。没有方法效果结论。

## 方案比较

| 决策 | 被否方案 | 理由 |
|---|---|---|
| 独立合成诊断旁路 | 直接修改生产提示词/长期框架记忆 | 尚未验证增益，避免把理论偏好当事实 |
| 只复用 Repository.publish/digest 存储原语 | 把选择题计数写成 research_validation 收益/概率收据 | 指标、观察窗口和合法来源合同不同 |
| 同公共任务，只变组织方式 | 弱化基准，不让其找反证 | 那会把任务差异误认成表示差异 |
| 调用前占位、每格最多一次HTTP | 失败自动重试直到有答案 | 重抽会引入幸存样本和预算偏差；保留失败更可解释 |
| 原件不可覆盖、report只读重算 | 只保存汇总分数 | 需要完整分母、原始文本、配置及错误痕迹 |
| 先校验量具，再看合成模型表现 | 将作者出题且公开答案的案例称作独立留出集 | 作者偏差、简单选项和天花板效应尚未排除 |

## 验证

使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，在隔离树执行：

- `-m pytest -q intelligence/tests/test_mechanism_pilot.py intelligence/tests/test_research_validation_repository.py intelligence/tests/test_research_validation_contracts.py intelligence/tests/test_research_validation_scoring.py intelligence/tests/test_research_validation_service.py intelligence/tests/test_method_validation.py`：180P/0F。其中新增37项。收据 `~/.finance-runtime/test-receipts/20260916T140116Z-c29a6401.json` 属于带本轮未提交改动的定向测试，不是全量可合凭据。
- `-m ruff check .`：通过。
- `git diff --check`：通过。
- CLI prepare/run/report 真入口已跑：prepare冻结协议 `5b0f8449bec81c2dd4ac99f399b5730b3d950604348d450cf5b2332ac80dd19f`；run blocked/no_configured_model/0调用；report pending/12格未跑。

## 边界与接续

全体文件未提交、未推送、未合并、未部署，遵守实验默认不提交约定。未跑全量pytest/前端/E2E；无真实模型答卷、无真实材料独立评审、无前向研究或投资效果。量具没有观测实际served model和token用量。

下一步在授权模型已配置的进程里，使用同树同协议运行run，再只读report。不得重做prepare覆盖冻结协议，也不得将测试中的伪模型答案当真实研究结果。改代码或材料另开并登记尝试，不删旧失败。完整阶段判据见 `docs/workflows/mechanism-research-pilot.md`，实时状态见 `docs/handoffs/inflight/feat-mechanism-research-pilot.md`。

工具沉淀：本轮工具直接落 `intelligence/eval/`，没有仅存在/tmp的运行脚本；不可覆盖发布、预算预占、失败分母都是复用既有模式，未另造跨项目框架或重复方法清单。
