# #60 / PR #856 本地修复与质检收尾

结论：**HOLD，未合入、未装机、未热补、未更新远端 PR body。** 本轮修复仍在 PR 工作树中未提交；本地提交对象只用于冻结验证，不等于发布到 PR。全量 Python 仍有一项失败，不得以定向复跑通过放行。

## 固定身份

- PR 工作树：`/Users/a77/fwp-wt-eastmoney-circuit-breaker-0922`，分支 `fix/eastmoney-circuit-breaker-0922`。
- 远端 head 回读仍为 `ade0003c7ef6eb4f64a291ab495caab861fb0a7b`，PR open、未合。
- 冻结 base 与收尾 fetch 的 main 均为 `5f35da1723f74663a4803c4d1490c402a1d6db40`。
- 本地草稿快照 `105cac7631ad0bce741a647d03d31cfa40c71474`。
- 合并预览 `e44966f2fb344ab2ff08bb5ef6b91054c38344df`，tree `f32bc4fe8427f12741b3a5f9b21ac98733a11a8f`。通过 merge-tree / commit-tree 构造，未更新 PR/main 引用。
- 证据根 `E=/Users/a77/.finance-runtime/reviews/eastmoney-cb-deploy-20260922`；最终证据 `E/qc-final/`，JSON 索引 `summary.json`。
- 干净验证树 `E/qc-final/finance-workspace-private`，已锁 worktree 防误清。PR 工作树三份代码文件已与草稿快照逐字节比对一致。
- `E/qc-final/fixes.patch` 的 SHA256：`0f19091c0fe2915929e7a4ff08e68de1aa31ad8058d1fce3ce641a6506a0d1eb`。

## 按发现顺序

1. 旧 PR/base 收据不能覆盖当前 main；首次本地修复的定向收据也标记 dirty，只能用于迭代。
2. `_empty_reply_streak` 只在成功后清零，普通网络错误或非 JSON 内容夹在空回应之间时会累计到阈值，违背“连续”语义。修复这两条异常分支；保留原传输选路策略。
3. 增加按 host + endpoint path 聚合的传输尝试计数；去掉 query 参数，计入连接失败、不计熔断跳过。它不是抓包级 HTTP 计数，不包含 DNS 或自动重定向。
4. 同步结果返回计数，CLI 成功与失败均输出；失败重新抛出原异常。每次命令开始清尝试计数，不清熔断，避免取数前失败沿用旧计数。
5. 增加回归：三种非空回应错误、分页/端点聚合与返回副本、熔断后重复调用无新增请求、CLI 成功/拒绝/取数前失败。
6. `/tmp` 旧预览 `8d859cebf` 首次全量被工具 1800 秒超时终止，无完整收据；重跑得 14598P/2F/85S/2X。两红是 Codex 沙箱的 live-root read 断言，public TCP/loopback/Unix socket 均 denied。
7. 同一 `8d859cebf` 在用户目录 `E/sandbox-location-control` 上两项均通过，未改沙箱实现或放宽权限。保留 `/tmp` 红收据。该失败形状已见共享知识 `gate-covers-only-its-return-value.md`，不另造清单。
8. 在用户目录的新固定预览 `e44966f2` 上重跑完整门禁，结果见下。最后一项全量红未闭合，停止发布，不顺手改无关模块。

## 验证与收据

以下路径相对 `E/qc-final/`：

| 检查 | 结果 | 证据 |
|---|---|---|
| Ruff 全仓 | exit 0 | `python.log` |
| Python 全量 | **14604P / 1F / 85S / 2X，exit 1** | `python/gate-0KOblA65/pytest.json` |
| 定向 + 沙箱 | 107P | `targeted/20260923T052332Z-e44966f2-3ed6ea3f06e0.json` |
| 前端 + E2E | 六项 exit 0，身份稳定、树干净 | `frontend/frontend.json` |
| Registry | 五命令 exit 0，仅本仓；缺席外仓跳过 | `registry/` |
| 撤掉两条清零逻辑 | 预期 3F，实得 3F | `mutation-no-streak-reset.log` |
| 未变异熔断组 | 18P | `after-mutation/20260923T053310Z-e44966f2-48a24611bedc.json` |
| 全量失败所在文件复跑 | 12P，不替代全量红 | `harness-repro/20260923T060934Z-e44966f2-03a3527d7d3e.json` |

全量收据 `scope` 无 ignore/-k/-m/deselect/maxfail，collected=14692 与全部结果对平。`check_test_receipt.py --expect-revision e44966f2... --require-full-scope --base-drift-max 0` 通过身份/环境/覆盖校验，但明确显示一红；`run_main_gate.sh --receipt <该收据>` 再验仍 exit 1。**收据可采信不等于门禁通过。**

唯一全量失败：`intelligence/tests/test_harness_reference_loop.py::test_tool_hidden_for_too_small_window_is_the_same_machine`。定向整文件复跑 12P。该用例有真实时钟差值 `<0.05` 秒断言，但 runner 只保存末尾 15 行，原失败断言详情未留存，不能据此确定是时钟抖动。该测试及其 runtime 不在本轮差异中；这也不足以免除全量红灯。未修改它、未扩大容差、未反复全量重跑求绿。

变异仅在另一个 Python 进程内通过 AST 去掉两条赋值，未改磁盘或全量进程。对应收据虽然 disk dirty=false，仍只是变异证据，目录 README 已明确禁止作为发布收据。

## 决策与否决

| 选择 | 否决 | 理由 |
|---|---|---|
| 其他错误打断连续空回应 | 保留累计计数并继续称“连续” | 契约与现有注释要求连续，不应过早熔断 |
| 固定 revision + 干净隔离树验证 | 复用旧候选收据或共享脏主树 | 避免把其他 agent 的改动或旧代码读数带入本单 |
| 路径对照定位沙箱红 | 跳过测试、放宽权限 | 验证环境也是安全断言成立的条件 |
| 保留最后一项全量红 | 用 12P 定向复跑签全量绿 | 定向没有复现整仓顺序、负载与共享状态 |
| 单独合入、装机授权 | 到点自动热补、顺带装机 | 时间和代码可应用性都不是副作用授权 |

## 部署与已知边界

- 两份已安装 plist 与 S7 launcher 的磁盘回读仍指向 `finance-sync-adcda94b5e40`；本轮没有 reload/kickstart，没有生产库写入或真实东财探测。
- PR 中四处根指针仍指向旧 `finance-sync-01e25264f218`，它不含本轮修复。即使从新 main 启动 installer，复制旧指针仍不会部署新代码。
- 旧 Plan B 补丁只含 snapshot 文件，既无本轮 streak 修复也无 CLI 计数，已在本地 runbook 标为停用。旧运行根带热补/脏状态，不是干净回滚副本。
- `E/deploy-steps.md` 已改为明确的待授权草案：期望 head/base 来自已验收记录，不跟随 fetch 自动变更；装机源须合后 main 干净检出；真实备份、哈希比较、部署记录与实际根回读均为后续步骤。仅提取 shell 块做 zsh -n，通过，未执行模板。
- `E/pr-856-body-update.md` 是整体替换草稿，统一端点相关归因；未发布到 Gitea。`E/candidate.json` 保留旧观测但增加历史证据警告与新索引。
- local 夜跑仅一次 snapshot，失败转 fallback；独立 fund-flow CLI 不在该 local 路径。熔断仅进程级，计数不是整晚跨进程预算。
- “每 host 3 次”仅指持续空回应场景；正常分页和夹杂其他错误不能用该总数限额验收。
- 汇总计数不能独自证明时序。单测已确认熔断后再次调用无新增尝试；生产仍需分进程请求轨迹或等价传输观察，不能用日志行数冒充实际请求数。

## 下一步与不要做的

1. 对最后一项全量红保留完整失败输出做可复现分诊；不要直接调大时钟容差或删测试。
2. 将本轮草稿正式发布到明确 PR head，再对该 head/base 固定组合验收；本轮收据不能贴到未包含修复的 `ade0003c` 上。
3. 重新准备含完整修复的代码根并校准所有指针，必要时联合 #61 固定同一批次；最终完整门禁闭合后才申请合入与装机各自授权。
4. 不执行旧 Plan B，不从 QC 临时根/共享脏主树安装，不把本地 body 草稿当远端已更新。

工具沉淀：复用现有 merge-tree、门禁 runner、收据校验器和注册表检查；未新增通用工具。一次内存变异仅作本轮证据，现有沙箱路径教训已在共享知识中，不重复维护第二份方法清单。
