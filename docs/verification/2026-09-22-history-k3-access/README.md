# #841 K3 启动阻塞与离线诊断

## 结论

固定 `fedce252330dce1065238f58e6c914417219ec53`，业务代码仍为 `f73d2133968d51d3c782d3e12ee9aa4d0618ef45`，两者非 docs 差异为空。本轮各启动一次新的 Spec/Quality K3 审查，均在凭证 bootstrap（模型请求前的初始化）失败，状态 `BLOCKED_BOOTSTRAP_NO_MODEL_DISPATCH`。没有独立终稿，不是 PASS 或 CHANGES_REQUIRED。

| 轴 | 实际耗时 | 退出 | 请求上限/时限 | 实际模型请求 | 终稿 |
| --- | --- | --- | --- | --- | --- |
| Spec | 1.338s | 70 | 24/600s | 0 | 无 |
| Quality | 1.466s | 70 | 24/600s | 0 | 无 |

候选为各自 detached worktree，首尾固定 fedce 且 clean，作者树同期也 clean。没有第三次审查、自动重试、回退模型或加购。旧 Codex 额度中断与本次本地启动失败分账，不由其中任何一项推断 K3 不可用。

## 发现顺序

1. sidecar 健康检查返回200，账号本地标志存在可用项；这些仅是本地状态，不证明 provider 能接受模型请求。
2. 原凭证解析器在普通宿主环境执行一次成功，收据 `access-preflight.json` 为 `CREDENTIAL_READY_NOT_MODEL_TESTED`。这是一次真实凭证刷新，不是全程无网络；令牌只在内存，未保存正文。Plus/有效期来自未做签名验证的 claims，不是供应商独立背书。
3. 两条审查复用既有 K3 runner，凭证扩展在 macOS controller 沙箱中调用 shell 解析器，均 exit70；内部 resolver exit1，stderr 哈希一致，事件流为空、provider admissions 为0。
4. 作者最初把失败归因为 HTTPS 被拦，判断错误，已撤回。原 controller 是 allow-default 加禁写策略，不能据此断言禁网。域名/IP 白名单实验未通过 sandbox 语法，另存 `failed-experiments/`，没有成功刷新凭证。普通 SQLite/SSL/DNS 离线检查未解释原故障；原终端结果未另存，不补造日志。
5. 将 PATH 中 python3 替为 `/usr/bin/true`，在原 controller 中执行原 shell 解析器，不执行其 Python 正文、不读账号、不联网，得到与两次原失败完全一致的 stderr SHA256：`36f2867300835bbadbc2f2497d1792b7c759ef223194f71b6ac13fd87afbfe58`。shell 在 here-document 建临时文件时就失败；默认和限定 TMPDIR 都失败。无 here-document 的空操作对照 exit0。见 `diagnostics/heredoc-result.json`。
6. 相同解析器 Python 正文改为由规定解释器直接执行，在 SQLite/HTTP 全部替身、禁止网络的 tools 沙箱中，成功、缺库、缺账号、缺 access token 四种夹具均符合预期。只证明这四种离线分支，不证明 Pi bootstrap 集成修复或真实凭证调用已通过。见 `diagnostics/direct-python-result.json`。
7. 后续读到 #843 收尾已有 here-document 与嵌套沙箱的同类记录；此前复用的是早期失败 runner，没有先核其最终验收状态。原 controller 内再启动 tools sandbox 的无网络 echo 对照 exit71，`sandbox_apply: Operation not permitted`。这也是当前启动方案的阻塞，单改解析器不够；不能盲目再复制该 runner。

初始 `diagnostic_runner.py` 在宿主对照成功，但放入沙箱时自身先写 diagnostics 文件失败，不能用于定位解析器；随后用 `diagnose_heredoc.py` 得到上述精确哈希复现。先前命令行 quoting 试验也不作为精确复现依据。原终端失败未伪造成日志，相关脚本仅为过程留痕。

## 原件与重建

`spec/quality/execution.json`、credential、stderr、preflight 和空 events 是原运行记录。`executed-inputs/` 中每项均与 execution 的输入哈希逐一相等。文件后缀 `.txt` 用于将日志/工装作为证据保存在 Git，不改变字节。

失败后曾修改 Spec 的 run.py、credential-bootstrap、controller 与 launch.py，拟改为外层刷新/环境变量传凭证，但未执行。现将草稿保存在 `unexecuted-drafts/`，恢复原输入。前三项以 Quality 同字节版本或仅轴路径替换重建，并与 Spec 的执行时哈希相等。launch.py 当时没有被执行记录哈希覆盖，虽由 Quality 副本重建，不称其已被原收据认证。细目见 `input-reconstruction.json`。原 execution 中 inputs_unchanged 只描述运行前后，不掩盖后来修改。

外部原件根：`~/.finance-runtime/reviews/react-trace-integration-20260921/history-k3-access-fedce/`。两次原失败输出、离线脚本、回归 stdout/JUnit、执行记录和收据在本包有副本；不提交账号库或凭证解析器本体。候选树、临时夹具与原目录保留。本包不改旧七包，hash 证明字节一致而非上游事实真实。

## 作者回归

- fedce 上统一定向599 passed、0 failed/error/skipped，pytest 22.60秒；JUnit599。不是新增599项，也不与前两轮599重复累计。
- 正式收据 `~/.finance-runtime/test-receipts/20260921T180311Z-fedce252.json`，精确 revision checker exit0；解释器为主树 `.venv-workbench/bin/python`，首尾 clean、依赖门禁未绕过，独立 basetemp、禁止字节码。
- 本包含 `focused.log.txt`、`focused.xml.txt`、收据及首尾执行记录。旧64b0的599、f73全量不移签到本次或文档归档提交。
- 定向执行期间最低采样31250341888 bytes；本轮未跑全量。磁盘共享且读数变化，不把空间变化归因本轮，不放宽原全量6GiB线。耗时不作性能结论。

## 未完成与禁止事项

独立审查仍 BLOCKED，自然金融仍 `not_passed`。金融自然探针0，225/25有效分母、自然数字引用和判官实际消费未验；实际 main tip 组合、#793/#794、#833/#845联合树未验。不合 main/#832、不部署8792、不关闭别的PR。

金融写手、语义判官与独立代码审查代理是不同角色。本轮 K3 指审查通道，不是切换生产写手；历史启动注释不能作为当前运行模型收据。未修改生产启动器、账号脚本、全局 Pi 设置或服务。

下一步先修已有审查执行设施的启动、隔离和终稿收口合同，并完成离线验收；再经明确授权，用新目录/准确SHA启动有界真实审查。不要删除外层沙箱后直接声称隔离等价，也不要只靠提示词保证达帽前收口。自然验收另需冻结题目、写手/判官、provider尝试硬上限、服务端墙钟和停止规则；probe 客户端超时不会取消服务端。

临时工装只归档，不推广为新产品能力或通用 runner；当前隔离与启动尚不合格。`run_check.py` 的历史 no-network/model 注释不代表整个本轮无认证网络。旧包及失败原件均保持各自历史结论。
