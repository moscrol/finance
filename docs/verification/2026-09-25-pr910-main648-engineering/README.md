# #910 main648 工程原件（部分完成，非独立审查）

- 受测 HEAD：`4e4d93a55bfd919b1c42bcb60f079ae56741fc3f`；基座：`64847b7a173bfb7191012638e8ec044ea31e0513`。
- 固定解释器：`/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`；Python 3.12.13，依赖指纹 `66726d345bf37ce5`。
- 完整作者套件 `tests/test_pi_review_repair.py`：74 passed，0 failed/error/skipped；定向收据校验通过。
- 全仓 Python：16232 passed，0 failed/error，75 skipped，2 xfailed，0 xpassed；collected=16309。`run_main_gate.sh` 与 `--require-full-scope` 收据校验均 exit 0。
- doctor、registry 四项、ledger crosswalk、完整 PR diff-check 均 exit 0；Ruff 包含在完整 Python 门禁内。
- 沙箱内层作者 C3：spec/quality 各 3 passed；C7：spec/quality 各 66 passed。内层原始 JUnit、工具执行日志、端口观察均保留。这是作者回归，不是两个独立审查人的 verdict，不与外层计数相加。
- 第一次完整 Python 结束后，frontend 启动前发现外部 pytest，监督退出。另一次只续未执行步骤的等待在 main 运行时代码漂移后主动停止，自有 PID 4406 已验证退出；没有干预外部进程。
- 前端及浏览器未启动。共用续跑记录中的 #911 静态检查明确属于另一候选，不能算入本 PR。

## 绑定与边界

收据只属于上述受测 HEAD。`main@643a2888ea14079035bc8b080129e3e4145d5685` 后续合入 #930，修改模型推理档的请求体与预算选择；不能把这里的绿灯移签给新基座或后续文档提交。也不把它升级为整套工程通过、自然金融质量、真实来源、自主子研究、反证修订、独立审查、L6、8792 live identity 或发布证据。

75 个 skip 和 2 个 xfail 的精确节点保存在 `raw/audited-results.json` 中；其中真实本地库、跨仓兼容、真实模型入口仍有未验证范围。付费模型请求 0，独审未执行，未合 main、未部署，PR 保持 WIP。

## 原件

原根：`/Users/a77/.finance-runtime/reviews/pr910-911-complete-20260925-01/`。

`manifest.json` 列出 141 份选定原件及 SHA-256：140 份逐字节入库；约全仓规模的 `910/full.xml` 只保留原路径、大小和 SHA-256，未写入 Git。完整 pytest stdout/stderr 与 JSON 收据已入库。临时沙箱配置是测试夹具，不是生产授权；其中脚本命令清单不表示每条都执行过。

`raw/910/summary.json` 是首次运行状态；`raw/remaining-01/summary.json` 是续跑状态；`raw/baseline-drift.json` 说明停止原因。日志不改字节，`.py/.log/.sb` 副本仅加 `.txt` 后缀。`sha256-manifest.txt` 覆盖本目录所有其他文件，提交后用 `scripts/check_evidence_archive.py` 从不可变 Git 提交复核。
