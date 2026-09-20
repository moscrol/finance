# Standards：生成根合流复审

固定目标 `f2342fda0d0ae9fb842cbcd0bdd6ee4cf5069bd1`；基线 `ec92b31b5300bbbb4abc64e41f96854f1438aea0`，比较 `git diff ec92b31b5300bbbb4abc64e41f96854f1438aea0...f2342fda0d0ae9fb842cbcd0bdd6ee4cf5069bd1`。起审树 `/Users/a77/fwp-wt-generation-alert-guard-0920` 干净。后续修补未获最终冻结号前，本报告不签完整通过。

## 原 S1：launcher 内的 P2 已闭合

`intelligence/workflows/generation_paths.py:73–77` 在告警启用时校验现有 writer 的 `notify_ops.ALERT_LOG`，没有另造日志路径；与实际追加端一致。`tests/test_generation_code_root.py:107` 的五场景覆盖文件软链、目录软链、HOME 落代码根、正常外置和关闭告警，断言快照字节不变，拒绝配置返回 2，正常质量失败仍返回 1。原运行反例已由根侧复跑；本轴不冒称独立跑过测试。

## 待修：1 项 P2，生成拒绝未约束外层后续动作

规范原句：`docs/agent-product-door.md:43`“写入位置落进代码根时拒绝生成”；`:47`“启动器在导入项目模块前核验代码面及嵌套脚本软链的真实归属”。

`skills/daily-full-review/scripts/nightly_full_review.sh:270–283` 已拿到 launcher 失败退出码，却先执行 `RECEIVE_SH`，再调用外层 `notify`：

- 日志预先软链进生成快照时，launcher 拒绝后 wrapper 的通知仍可写同一文件。Spec 轴真实 shell/launcher/notify 隔离反例已证实；原始证据在 `generation-spec-final/outer-alert-boundary.json`。
- 本仓 `skills/daily-full-review/scripts/receive_kb_ingest_queue.sh` 预先软链到数据树脚本时，源校验先拒绝，但 wrapper 的 `-f` 仍可通过，并在检查退出码前执行该脚本。该本仓入口不属于门页排除的外部 KB 接收器实现。运行实证另由 Spec 轴补齐。

应在生成失败后立即中止后续生成动作，并确保失败通知不再通过被拒绝的日志目标写入。保留正常外置告警与 L2 独立运行合同。

## 其余合流检查

`387028b8`、`cc47484e`、`ec92b31b`、`2fa28a4f` 均为目标祖先。计划解析使用 canonical `PLAN_CHOICES`；同花顺四步、无 key 的 skip、日期和 staging 继承保留。`requested_plan` 先于连接拒绝非法档位，`auto` 在获知交易日后解析；空壳板块判据、返回字段和显式 tables 作用域未丢。生成根仅覆盖生成子进程，L2/外层门/方法根不变。未见额外可行动 smell。

门页 41 行旧 `FINANCE_CODE_ROOT` 与新增生成根说明冲突，已向根代理指出；根代理正在独立提交修正，不能用未冻结修正回填 f234 的结论。本轮只读审查，未改代码/生产、未跑全量；保留原报告。
