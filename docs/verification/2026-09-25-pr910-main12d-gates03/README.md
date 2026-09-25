# #910 main12d 固定候选：定向与前端通过，全仓未启动

受测/发布 HEAD `2da72eef44787c910b5affbce47eea1e837ee7ae`，基座 `12d91dc733e1a29ceb54668fb934513bd10da4e9`。普通 merge 吸收 #933 及先前文档，实际 tree `2883b2d568b9f697d1448b1dfd2cae1b4f88296e` 与预览相同，无冲突或手改产品实现。

## 实际结果

| 范围 | 结果 |
| --- | --- |
| doctor、Ruff、registry 四项、crosswalk、整个 PR diff-check | 全部 exit 0 |
| `tests/test_pi_review_repair.py` | 74 passed，0 failed/error/skipped/xfailed/xpassed，79.96 秒 |
| 定向收据与续跑重验 | 精确 SHA、基座、解释器、依赖和目标通过 |
| 作者沙箱内层 C3 / C7 | spec、quality 两轴分别 3P / 66P；不加进 74，不视作独审 |
| 前端 install / lint / typecheck / test / build / E2E | 六步 exit 0，123 单测通过，浏览器 34 通过 / 2 跳过 |
| 全仓 Python / 完整范围收据 | 未启动、无收据；聚合结论 INCOMPLETE |

浏览器两项跳过是同一绑定链路在 tablet/mobile 的设计性跳过，仅 desktop 执行一份。隔离服务使用 bootstrap 构造的市场库，不证明生产来源或自然金融质量。

## 中断与续跑

初段完成两边定向与 #911 前端后，在 #910 前端启动前遇到 `OSError: [Errno 48] Address already in use`。之后探针显示 20981/20984 无监听、连接被拒且可绑定；未证明失败瞬间的根因。原记录保留，续段重新核验已有收据，为 #910 使用独立端口 20991/20994，前端六步通过，没有重跑已完成套件。

续段随后完成 #911 全仓。2026-09-25 11:46:43 UTC 轮到本 PR 全仓时，外部 pytest PID 80907 拒绝准入；按零新增等待规则退出，未创建本 PR 的 python-full 过程文件。自有 PID 57164/63422 均已退出，未干预外部进程。

## 原件与身份

本归档三份前端原日志末尾有空行，协调分支归档格式检查非零；原字节保留，不冒称格式全绿。检查原文见 `docs/verification/2026-09-25-pr910-911-gates03-archive-format.json`，与受测源码 diff-check 分开。

145 份选定原件逐字节入本协调分支，见 `manifest.json`。`raw/audited-results.json` 按 PR 核收据、JUnit、前端六份日志哈希及必要步骤集合；本 PR 明确缺 `python-full`、`full-receipt-check`。原根 `~/.finance-runtime/reviews/pr910-911-complete-20260925-03/`。

固定 Python `/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，依赖指纹 `66726d345bf37ce5`。共享审计里的 #911 全仓 16266P 不属于本 PR；旧 d300 的 74P、旧 4e4d 的 16232P 也不移签。

收尾 main 已到 `e159c564440c69abe17f106ae721fd25348a1865`（#932 数值预检运行时变化），本批没有吸收它。漂移另记 `docs/verification/2026-09-25-pr910-911-gates03-main-drift.json`。归档只写协调分支，不改变受测 HEAD；新集成候选须另验。

保持 WIP，付费授权/模型请求 0；未独审、合 main、L6 或部署。此处不证明自主子研究、反证修订、真实来源、自然金融质量或 8792 身份。
