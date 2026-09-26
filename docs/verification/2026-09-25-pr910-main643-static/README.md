# #910 main643 静态检查原件

- 候选：`a8cea541422d006c1aa0c022db8a652a2792886e`；基座：`643a2888ea14079035bc8b080129e3e4145d5685`。
- 无冲突吸收 #930 的四个源文件，不手改产品逻辑。
- doctor、全仓 Ruff、registry 四项、ledger crosswalk、完整 PR diff-check 全部 exit 0；代码地图刷新完成。
- 固定 Python：`/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`；依赖 `66726d345bf37ce5`。
- 动态准入拒绝：2026-09-25 10:07:29 UTC 检测到外部 pytest PID 4484/18495。磁盘超过 20 GiB 要求，但有外部 pytest 就不启动；没有排除、终止或干预它们。
- 状态 `STATIC_PASS_DYNAMIC_NOT_STARTED`；本 SHA 无定向、全仓 Python、前端或浏览器新收据。无后台等待进程。

原根：`/Users/a77/.finance-runtime/reviews/pr910-911-main643-20260925-01/`。21 份原件逐字节入库，映射与 SHA-256 见 `manifest.json`，Git 完整性见 `sha256-manifest.txt`。

历史 `4e4d93a55` 的 74 passed 与全仓 16232 passed 仅见相邻 `2026-09-25-pr910-main648-engineering/`，不移签。静态绿不等于完整工程通过、独审、真实来源或金融质量。付费模型请求 0；PR 保持 WIP，未合 main、未做 L6、未部署 8792。
