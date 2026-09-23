# RE06 Timer Shipping Assets: Fixed Candidate Evidence

## 当前结论

- 候选 `b24c86f87aaef6244dc6a2c6cf80f74ae1918943`，固定基线 `ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb`，父候选 `f9ce5c6b296492b423400ad66d333784a4be13bc`。
- 作者树 `/Users/a77/fwp-wt-re06-timer-assets-0923`，分支 `fix/re06-timer-assets-0923`。仅更新已跟踪的前端发布包与 HTML 引用，业务源码未改。
- **四叶工程验收 PASS；独立 QC INCOMPLETE；不可合入。** C1-C10 均未取得最终独审签字，Quality 为 `not_evaluated`。
- 本轮没有 push、PR、合并、部署、生产写入/迁移、网关重启或 worktree 删除。

## 为什么换候选

旧 `f9ce5c6b2` 的源码使用 v2，已提交发布包却仍是 v1。重新构建使受版本管理的文件变脏，前端身份门正确拒收。先保存这次生成物，再仅恢复本轮生成的改动，旧作者树保持原 SHA 且干净；新建分支提交产物后重新跑完整验收，没有把旧收据移签。

这是 C7 的候选交付缺口，不代表实测旧包停表关闭了测量，也不代表动过生产。旧证据见 [acceptance-02](../2026-09-23-re06-timer-scope/acceptance-02/README.md)。

## 工程验收

| 叶子 | 新候选的完整结果 |
|---|---|
| Python | Ruff PASS；14760 collected，14673 passed / 0 failed / 0 error / 85 skipped / 2 xfailed；JUnit 与独立收据一致，收据校验 exit 0 |
| Frontend | frozen install、lint、typecheck、122 tests、build 全过 |
| E2E | 本叶重新 build 后执行；34 passed / 2 skipped |
| Registry | 五项检查全过 |

原件为 `~/.finance-runtime/reviews/re06-timer-scope-acceptance-20260923-03/`，归档见 [acceptance-03](acceptance-03/README.md)。候选前后 SHA 相同且干净；pytest 启动前负载 7.131、已有 pytest 1 个、空盘 25.358 GiB，运行期间最低空盘 15.941 GiB。完整 pytest 终端耗时 1654.98 秒，未触 3600 秒上限。没有复用 `latest.json`、旧部分进度或旧候选通过数。

## 独立 QC

| 运行 | 结果与边界 |
|---|---|
| 05 gateway | 2 请求，HTTP 200，真实 read/tool-result 往返 PASS，20.774 秒 |
| 05 timer explore | 23 请求，有静态探索终稿及内嵌自造探针；宿主用 Markdown 解析器逐字提取并验哈希，没有代写/修补；不是测试通过 |
| 05 e2 explore | 23 请求，有静态终稿但无探针代码/文件；原 `STAGE_COMPLETE` 只代表结构检查，后续文件门拒绝 execute |
| 05 consent explore | 10 请求，已写初版探针，但末次 HTTP 504、无终稿；事务同族独立分类未完成 |
| 05 timer execute | 3 请求，末次 HTTP 504、无终稿；仅目录/文件阅读，未运行 pytest 或必红对照 |
| 06 gateway | 新的 2 请求工具往返 PASS，202.519 秒；E2 补交会话已准备，但在再现 504 后未派发 |

本候选 63 请求，旧候选 01-04 共 10 请求，累计 73。仍是 K3/xhigh，SDK 自动重试 0，未换账号/模型。新运行将客户端请求等待由 120 秒设为 300 秒、阶段窗设为 1800 秒，工作/收尾请求上限不变；旧执行文件未改。两个 504 是实际模型请求的 HTTP 错误，`timed_out=false`，不是业务缺陷，也不能据此认定流量、配置或设备会话故障为根因。

原始探索终稿的 `complete:true` / `artifacts:[]` 原样保留。新增宿主文件门在真实派发入口拒绝 E2 execute、consent execute、timer report，均在凭据/模型请求前返回 75。移除该门的宿主变异会触发隔离 stub，验证已抓住；这不是 #75 要求的 `assert 1 == 2` pytest 阳性对照。

详见 [report.json](report.json)、[spec/CLAIMS.md](spec/CLAIMS.md)、[quality/STATUS.md](quality/STATUS.md)、[probes/README.md](probes/README.md)。

## 证据与下一步

每个子包 `manifest.json` 记录原字节数、SHA256、存储形式；压缩日志以 gzip + base64 分块 JSON 保存，可完整还原并校验。脚本以 `.py.txt` / `.mjs.txt` 保存，不作为通用运行时安装。没有归档数据库、浏览器缓存或真实凭据。

本轮不再追加重试，当前没有继续 QC 的授权。须另获用户授权，并取得新的实际载荷健康窗口，才继续独立 explore/execute/report、分开统计作者测试与审查者探针、执行必红对照，并完成事务同族分类。已落盘探针未经执行，不能把代码存在当作覆盖成立。新会话必须新建输出目录，保留本次全部失败与原稿。#76/P7、生产迁移/历史重算仍未执行；获授权前不 push/PR/合 main/部署。
