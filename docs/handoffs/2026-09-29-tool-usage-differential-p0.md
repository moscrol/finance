# 在途交接 · feat/tool-usage-differential-p0-0929

日期：2026-09-29。独立工作树 `/Users/a77/fwp-wt-tool-usage-audit-0929`，基线 `gitea/main@2b66c3740`。认领 `R-20260827-14` 的 **P0 离线审计**；不认领 P1 在线遥测，也未改运行时、工具选择、生产数据库、部署或判官。

## 本次交付

- `scripts/audit_tool_usage_differential.py`：只读遍历 `$FORESIGHT_USERS_DIR/*/runs/*/continuous-episode.json`；`--since`/`--until` 按 run ID 日期过滤，不用 mtime；`--user` 精确目录名；JSON + Markdown 同名输出到 `intelligence/eval/measurements/`，拒绝覆盖已有输出。
- `tests/test_audit_tool_usage_differential.py`：至少覆盖 §9 四种失败形状：request 与 result 不能互换、报错仍算已请求、suspicious 不能混进实例差值、分母只算声明了工具的 run。再覆盖多 contributor、一工具已调用则实例不算差值、日期过滤和用户目录。
- 三份聚合报告：截至 08-27 的复盘、截至 09-29 的现有样本、08-25～08-26 的过滤对照。报告不含用户问题或答卷原文，只含计数与工具名。

## 复算读数与未闭合判据

| 样本 | 文件数 | 有 checks | 可算 run | 有差值 run | output 实例差值 | suspicious |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 工单原基线（08-27 当时） | 747 | 735 | 698 | 572 | 425 | 1193 |
| 本次截至 08-27（现有根） | **748** | **736** | **699** | **573** | **425** | **1198** |
| 本次全量（至 09-29） | 962 | 949 | 871 | 736 | 626 | 1850 |

08-27 集合多 **一份探针/评测目录的 run**：具名目录仍为原单 387，其他目录由 360→361。增量符合 checks +1、可算 +1、有差值 +1、suspicious +5、`kb_search` 被声明 +1 且被调用；output 实例差值及八个 output_id 细分与原单**逐项一致**。原 747 份 run 没留快照或完整清单，**不为凑 747 擅自删一个样本**；要完成「同一样本逐个相等」，需找到原样本清单/截点并独立对账。

另一硬限制：抽样检查 `continuous-episode.json`、同目录 `run.json`/`report.json` 均未找到代码 revision 字段（`kb_commit` 不是代码版本）。脚本输出 `code_revision_known_runs=0`、`revision_span=UNAVAILABLE`，明确缺口，不把当前 git 头或 KB commit 冒称跨历史 run 的代码版本。原工单的「revision 跨度必须列明」**目前不能签满**；若上游另有可信 run→revision 映射，应接入再验。

**禁止结论**：626/1850 并非线上用户质量或「模型路由差」的证明。声明表空 produces 会漏抓，预取/未声明工具可能填上 output 会高估；两个方向的偏差在输出中并列说明。

## 门禁与下一步

- 定向：3 passed；Ruff 对本单两文件通过；实根 `--since` 的分母由 699（截至 08-27）变为更小子集；报告写入不影响任何 run。全仓四叶与独立复核**未跑**。
- 请独立 reviewer：① 冻结真实 747 份的 manifest，复算相等；② 找到可靠 revision 元数据或裁决 retrospective revision 缺失只能披露为未知；③ 审查四条变异是否逐条红并对全仓收据自证，之后才考虑从 WIP 转可合并。P1 在线遥测不能并行开。
