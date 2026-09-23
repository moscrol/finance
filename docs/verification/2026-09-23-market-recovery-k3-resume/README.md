# K3 行情恢复独审续跑证据

## 结论

**整体 HOLD。K3 已能执行真实工具往返，但本轮没有完成独立 QC。**

用户纠正了「一次 45 秒预检超时便停止」的判断。本轮验证流式工具请求，并重新启动两次独立探索；不能再把阻塞笼统写成「K3 不可用」。本文和 `summary.json` 是执行方的证据汇总，不是审查者出具的 Spec / Quality 报告。

固定候选 `45e752cfaf30929d15acbd0bcab0a667aef0e12e`，基座 `bbd53487f4cefdae97eae90f7322394d36e65462`，tree `3ea686889344ebbaaddeee2b3866bce9bd9a3733`。本轮重新执行 `git merge-tree --write-tree` 得到同一 tree；结束时远程 main 无漂移。没有执行分支合并。

## 分账

| 环节 | 模型请求 | 已完成工具操作 | 实际结果 |
|---|---:|---:|---|
| 流式通道探针 | 2 | 1 次本地摘要函数，不是产品探针 | 首轮 HTTP 200，2.940 秒首包、16.224 秒工具调用结束；工具回传后约 120.170 秒收到 HTTP 504 |
| explore 01 | 4 | 5 | 前 3 轮 HTTP 200；第 4 轮 CloudFront 504；172.263 秒退出，Pi exit 0 但模型错误明确存在 |
| explore 01b | 7 | 11 | 7 次 HTTP 200，最后一轮流尚未完成；600.419 秒触会话上限，exit 143 |

合计 13 次预占请求，11 次 HTTP 200、2 次 504；**HTTP 200 包括被中止的流，不等于 11 次完整成功回答**。固定 `mirasim-kimi/kimi-k3`，未换模型/账户，无自动重试，无 400/429，无共享网关重启。第二次探索是一次明确有界的重新开始，不是 SDK 自动重试。

正式独立探针 0，阳性对照未执行，作者测试本轮未跑。两次探索均无 `EXPLORE.md`、`probe_*.py` 或报告，因此 execute / report 没有启动；`inputs/prompt-session-02.md` 只是未执行的准备文件。F1/F2/F3 均为 `not_verified`，不代表发现新产品缺陷，也不代表无发现。

## 文件

- `summary.json`：控制方归因与计数，明确不是 reviewer verdict。
- `transport/`：流式工具探针、结果、请求预占及无密钥凭据引导源码。
- `session-01/`、`session-01b/`：运行身份、请求预占、HTTP 成功响应记录、沙箱预检及事件审计流。
- `events-audit.jsonl` 保留工具调用/结果、助手最终消息元数据，去掉思考流和逐 token 更新；原始事件 SHA-256 在各 `execution.json` 和 `summary.json` 内。
- `inputs/`：固定 runner、提示、工具沙箱与来源 diff。`run.py.txt` 是运行源码快照，不是新增产品模块。`.log` 原件以 `.txt` 镜像归档，内容未改变。
- `manifest.json`：上述 30 个机器证据文件的 SHA-256 和字节数，不含本 README 及 manifest 自身。封存器逐一核验原始执行收据所列文件，并验证复制一致。

原始目录：`~/.finance-runtime/reviews/market-recovery-qc-20260923/independent-45e752c/`。通道探针历史目录是相邻 `independent-d3abd670/stream-tools-preflight-TVG2mG/`，**它只测通道，没有审旧候选**。审查进程均已退出；本轮独占 candidate worktree 已移除，验证引用 `refs/verification/market-recovery-close-20260923` 保留身份。旧 d3 检出与证据未动。

## 边界与下一步

本轮未改产品源码、未合并/推送/部署、未做数据库 staging/换库/生产写入，也未重跑全仓测试。此前 2639P/62S 仍仅是新候选根目录 tests/ 回归；旧 d3 的全仓收据不能移签。

下轮需先解决审查交付节奏：按 F2/F1/F3 拆最小工作单元，把「先写探针再扩读」落实成可执行的工具预算或阶段门，不能仅重复本轮未被遵守的提示。随后重启独立 explore / execute / report，保留阳性对照与作者测试分账；仍需新候选全仓门禁，以及业务合同与恢复范围确认。
