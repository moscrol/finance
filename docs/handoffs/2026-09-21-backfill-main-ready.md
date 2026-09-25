# 302132 当前main离线整合记录

## 背景与范围

归属盘点发现 `fix/backfill-acceptance-closeout-0920@1fd34dc7` 的代码修复仍未进入 main。旧来源已保留在 Gitea，原工作树不改。本轮基准固定为 `728f327160bbd2485cb635e7ef09d040d718d7b5`，新树 `/Users/a77/fwp-wt-backfill-main-ready-0921`。

旧合同与审查沿 `1fd34dc7:docs/handoffs/2026-09-14-302132-backfill-execution-design.md`、`1fd34dc7:docs/handoffs/2026-09-20-302132-backfill-acceptance-closeout.md` 及其证据追溯；不复制旧文档成新的完成事实。本轮仅验代码，不运行 `repair-backfill-302132` 生产命令，不读写真实生产库，不解除复盘会停抓。

## 实际动作

1. `git merge-tree --write-tree 728f3271 1fd34dc7` 无冲突，合并树对象 `18618fc200fc7b23815336903e20efe354c72c96`。从其取四个源码/测试文件，保留当前 main 的其余内容：CLI、回填模块、离线验收脚本及专用测试。
2. 得到代码提交 `400d02dd890af165095ceeea1c95e143ab555f5c`。保留 `spec.code == CODE` 目标绑定、巨大整数导致 `math.isfinite` 溢出时结构化拒绝等旧修复，不创建生产直写替代链。
3. 整合过程的局部104P只作迭代读数；提交后在独占干净候选运行全量 Python 和前端门禁。
4. 前端首次参数填错完整 SHA，入口拒绝执行，rc2原件保留；从 Git 解析真实 SHA 后使用新输出目录重跑通过。
5. Python pytest 完成后，外层脚本找不到自定义收据目录，且错误提示里的未加花括号变量触发 unbound variable，包装退出1。查源码确认 conftest 的收据目录固定在 `~/.finance-runtime/test-receipts`，不会响应外层 `FWP_TEST_RECEIPT_DIR`。没有修改旧输出或把包装退出码改成0。
6. 找到 `20260920T193037Z-400d02dd.json`，核准树、完整SHA、12017P和退出0；显式 `run_main_gate.sh --receipt <该收据>` 读回0，`check_test_receipt.py --expect-revision <完整SHA> --base-drift-max 0` 校验0。该原件与相关日志归档，不读可能被其他会话改写的 latest.json。
7. Registry在 `git archive 400d02dd` 的新finance-only目录运行五项，范围对应本仓CI不checkout姊妹仓的形状；全部退出0，不冒充跨仓一致性验收。
8. 代码已推送。后续提交只增加此交接、inflight和证据，不把400d02dd的全量收据移签给文档尖。

## 验证范围

| 叶子 | 固定代码400d02dd结果 | 证据与边界 |
|---|---|---|
| Python | 12017 passed / 85 skipped / 2 xfailed，1476.01秒 | 干净树；原始pytest收据exit_status=0；首轮外壳rc1独立保留 |
| Ruff | 全仓通过 | 原始python包装日志 |
| 前端 | 110 passed，lint/typecheck/build通过 | 首尾完整SHA相同、dirty=false、六命令exit0 |
| E2E | 34 passed / 2 skipped | 不含新增真实模型或生产回填验收 |
| Registry | 五项全部exit0 | finance-only归档；不是姊妹仓混合工作树 |
| 独立Spec/Quality | 本轮未取得 | 原枝审查是输入，不是新组合裁决 |
| 生产业务 | 未执行 | 无真实回填、原子发布、数据有效性签字 |

原件目录：`docs/verification/2026-09-21-backfill-main-ready/`。
外部完整运行目录：`/Users/a77/.finance-runtime/reviews/ownership-closeout-20260921/backfill-400d02dd/`。

## 取舍

| 方案 | 处理 | 原因 |
|---|---|---|
| 原枝旧绿直接签当前main | 否决 | 基座与组合不同，旧收据不证明兼容 |
| 整枝合入旧文档 | 否决 | 过期状态会再次被当成事实 |
| 当前main上只前向四文件并重新验证 | 采用 | 保留现有CLI增量，版本可冻结与复核 |
| 包装失败后重写退出码/覆盖日志 | 否决 | 会抹掉真实设施失败；只允许引用实际pytest原件并另记读回校验 |
| 顺手修全仓收据协议 | 本轮不做 | 改conftest与门禁契约会改变验收设施，需单独带测试与验收；当前有显式收据入口可准确核验 |

## 后续与禁止事项

先做新组合的独立合同与代码质量审查，再依据最新main形成合流候选并验收。生产执行另需冻结输入、目标库、备份、run_id和发布授权。分支名含main-ready只标推进目标，不代表独立审查或合入批准已完成。

本轮不合main，不切8792，不修改原枝，不删除工作树，不把代码门禁通过写成生产数据已修复。收据目录协议不一致已作为设施缺陷登记，不能据此称本次首轮包装脚本通过。
