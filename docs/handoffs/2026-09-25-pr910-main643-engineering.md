# #910：封存 main648 Python 结果，前向 main643

## 背景与顺序

1. 在 `main@64847b7a173bfb7191012638e8ec044ea31e0513` 上冻结干净受测 HEAD `4e4d93a55bfd919b1c42bcb60f079ae56741fc3f`。
2. `tests/test_pi_review_repair.py` 实测 74 passed，无失败、错误、跳过；沙箱内 spec/quality 的 C3 各 3 passed、C7 各 66 passed，内层只作作者回归。
3. 完整 `run_main_gate.sh` 完成：16232 passed、75 skipped、2 xfailed、0 failed/error/xpassed，collected=16309；严格完整范围、精确 revision、解释器、依赖与零基座漂移校验均通过。
4. frontend 前置资源准入检测到外部 pytest，初次监督退出。新脚本只准备续未执行叶子，同时完成 #911 的静态检查；它没有进入 #910 frontend 或 #911 pytest。
5. 发现 `main@643a2888ea14079035bc8b080129e3e4145d5685` 合入 #930：`llm_refine.py`、API 及对应测试改变模型推理档与预算。停止自有等待 PID 4406，先验证命令与无子进程，再发 SIGTERM，复核 PID 消失；不干预任何外部进程。
6. 旧结果逐字节封存至 `docs/verification/2026-09-25-pr910-main648-engineering/`，提交 `0a6444ba16c52f4020b1ff29fd628480637eff14`；Git 内清单 142/142、哈希核验通过。141 份原件中全仓 JUnit 大文件留外部原路径与哈希，其他 140 份入库。
7. 普通非快进合并最新 main，无冲突，不手改产品代码；新候选 `a8cea541422d006c1aa0c022db8a652a2792886e`，tree `dc778231d00af8d6332e94032049e8888f10ffbc`。
8. 新候选 doctor、Ruff、registry 四项、crosswalk、完整 PR diff-check 与代码地图刷新全部成功。10:07:29 UTC 准入仍被外部 pytest 4484/18495 拒绝，动态测试未启动，没有后台等待者。原件见 `docs/verification/2026-09-25-pr910-main643-static/`。

## 决策

| 选择 | 被否方案 | 理由 |
| --- | --- | --- |
| 旧结果封存后前向 #930 | 把运行时漂移当文档漂移 | 推理档同时影响请求体与时限表，必须重新绑定 |
| 停止等待中的自有进程 | 继续在旧 SHA 上堆完整测试 | 新结果仍不能回答最新组合是否通过 |
| 新候选静态与动态分开记 | 静态通过写成工程完成 | pytest、前端、浏览器均未执行 |
| 两候选分别记账 | 用 #910 全仓替代 #911 | 测试集合、源码和受测 SHA 不同 |

Gitea 的 WIP 会影响 `mergeable`，不能把 `mergeable=false` 直接写成代码冲突；本轮本机 merge-tree 与实际合并均无冲突。

## 下一步与边界

资源允许后在新的干净 HEAD 上重新冻结，先核对 main 是否有新的运行时变化，再跑完整沙箱套件、完整 Python、前端与浏览器。后续文档 HEAD 不自动继承任何精确 SHA 收据。固定 `/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，依赖 `66726d345bf37ce5`。

不恢复 `pr910-911-qc-20260925-01` 已撤销批，不修改共享 19899 路由、owner 分支或 8792。付费授权与请求仍为 0；独审、真实来源、自主子研究、反证修订、自然金融质量、L6、main 合入及部署均未新增授权或验证，保持 WIP。

本轮复用现有收据、资源准入、前端和 Git 归档校验器。批次脚本是绑定特定候选的执行记录，已随原件入库为 `.py.txt`，不另造通用门禁；证据不移签原则已有共享知识索引，不复制第二套方法论。
