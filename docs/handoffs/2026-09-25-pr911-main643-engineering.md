# #911：封存 main648 静态结果，前向 main643

## 背景与顺序

1. 冻结 `main@64847b7a173bfb7191012638e8ec044ea31e0513` 上的干净 HEAD `a52a3a9759a1d1d33fc5e19c86e35576394dd546`。本批串行先 #910 后 #911，未借用 #910 收据。
2. #910 完成作者 74 项及全仓 16232 项后，在 frontend 前因外部 pytest 被拒绝启动。另一次只续未执行叶子的脚本先实际运行 #911 的 doctor、Ruff、registry 四项、crosswalk、完整 PR diff-check，全部 exit 0；本候选 pytest、前端和浏览器仍未开始。
3. 等待期间发现 main 合入 #930，修改模型推理档的请求体和预算选择，不再是纯文档漂移。自有等待监督 PID 4406 已核实停止，无外部进程被干预。
4. 封存 `docs/verification/2026-09-25-pr911-main648-engineering/` 的 26 份原件，提交 `0767f60a8263d59091ae7688d7c58d3d02d4b48a`；Git 清单 28/28、哈希通过。共有审计文件带 #910 的不同 SHA，不能当成本 PR 测试证据。
5. 普通非快进合并 `main@643a2888ea14079035bc8b080129e3e4145d5685`，无冲突、不手改产品逻辑；新候选 `eb59c4a2fb4dbe77a349bd8545b942aa4df8db14`，tree `0f6574d527efcc627bbfbe81b1569a0c15a9ba40`。
6. 新候选 doctor、Ruff、registry 四项、crosswalk、完整 PR diff-check 与代码地图刷新全过。10:07:40 UTC 准入因外部 pytest 4484/18495 拒绝，动态测试未启动，也没有后台等待。原件见 `docs/verification/2026-09-25-pr911-main643-static/`。

## 决策

| 选择 | 被否方案 | 理由 |
| --- | --- | --- |
| 运行时漂移后重新冻结候选 | 旧 56 项或另一 PR 全仓移签 | 组合及测试分母不同 |
| 保留历史结果和父链 | rebase、覆盖原日志 | 能追溯每个结论实际成立的版本 |
| 静态绿、动态缺失分开 | 资源拒绝写成通过或失败 | 拒绝意味着未执行，不是产品结果 |

Gitea WIP 状态可以使 `mergeable=false`，不能据此声称代码冲突；本机预览与合并均无冲突。

## 下一步与边界

资源释放后，在新的干净 HEAD 上重新冻结，复核 main 运行时漂移，跑 `intelligence/tests/conformance/test_research_chain.py`、`intelligence/tests/test_workbench_research_chain.py`，然后完整 Python、前端及浏览器。后续文档提交不自动继承精确 SHA 收据。固定 `/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，依赖 `66726d345bf37ce5`。

研究链模型、数据与判官是脚本化离线测试，不能据此证明自然金融质量、真实来源、自主子研究、反证修订或 live identity。付费授权/请求为 0；独审、L6、main 合入及部署仍未授权或执行。保持 WIP，不恢复旧撤销批、不修改 owner 分支/19899 路由/8792。

本轮复用现有门禁与归档校验器，特定候选的执行脚本以 `.py.txt` 归档，不建立第二套通用工具或能力清单。
