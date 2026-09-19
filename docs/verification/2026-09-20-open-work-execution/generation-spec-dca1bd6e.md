# dca1bd6e · Generation Spec 最终独立复验

**结论：本 Spec 轴通过。此前直接 launcher 告警遗漏与完整 nightly 的两类 P2 均已关闭；原探针未改输入或断言全部转绿，未发现新增的规格阻断。** 这份结论限定为下面的源码与临时夹具证据，不替代父任务的全量/合并门或生产部署验收。

## 固定对象与审查范围

- revision：`dca1bd6e73f443ca09d08ef0a6c8b9b2bb0018a9`。
- 干净冻结树：`/Users/a77/.finance-runtime/open-work-execution-20260920/gate-generation/finance-workspace-private`。开始、每组输出、完整入口结束及最终核对均对应此 revision；`git status --porcelain=v1` 为空。
- 本轮审阅 `f2342fda...dca1bd6e`：共同 notify writer、nightly 失败顺序、对应回归、质量夹具修正、入仓探针及门页。此前合流语义审阅见保留的 `generation-spec-final.md`；本修复没有改动共享计划解析或 hithink 接线。
- 使用 code-review 的 Spec 轴。未改候选/生产、未运行模型、生产 DB/L2/KB 接收或全量。全部执行使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，清洁环境与禁止字节码写入；桌面通知为临时无操作 stub。

## 原失败闭环

| 规格与旧失败 | 修正证据 | 本轮原样复验 |
|---|---|---|
| #50 §4.3“代码根下零新增文件”；387 的直接 daily 告警写入 CODE | `intelligence/workflows/generation_paths.py:73–76` 使用实际 ALERT_LOG 作启动预检，已有 cc47484e 修复保留 | 原软链反例 exit 2、root-invalid、无日志/代码变化；合法外置对照仍 exit 1 并写真实业务失败日志 |
| f234 的生成拒绝后 outer notify 写 CODE，L2 提前失败也写 CODE | `scripts/notify_ops.py:35–39` 在 `mkdir/open` 前解析最终 ALERT_LOG，逐一排除非空 FINANCE_CODE_ROOT、FINANCE_GENERATION_CODE_ROOT；`:40–42` 才允许写入 | 两个根实际分开设置；完整入口的生成拒绝和 L2 提前失败均零代码文件变化、零错误位置日志，原退出码分别保持 2/1 |
| R3“副作用前验证……拒绝外逃软链；嵌套脚本遵守相同规则”；f234 launcher 拒绝 receiver 以后父 shell 仍执行 | nightly `:275–280` 紧接 launcher 返回码处理失败并返回，只作 stdout/desktop 提示；receiver 移到 `:284–287` 的成功路径 | 同一预置 receiver→数据树脚本软链返回 2、launcher 未 import、`receiver_executed=false`，原 marker 不再出现 |

共同 writer 把限制放在实际落盘前，因此 L2 尚未进入 launcher 时也受保护；修复没有把 L2 移到同步守卫之后。安全外置告警仍写入，没有靠关闭全部告警通过反例。

## 独立执行结果

1. **原七项边界探针：7 passed / 0 failed，进程 exit 0。** 仍从旧冻结树 `/Users/a77/fwp-wt-generation-root-guards-validation/scripts/probe_generation_code_root.py` 执行，`--repo` 改为新冻结树。所有七项都是 exit 2；没有错误代码执行哨兵或代码树文件变化。日志/JSON：`generation-spec-dca1bd6e/original-probe.{log,json}`。
2. **原直接告警探针：坏配置和合法对照均符合原判据，进程 exit 0。** 仍导入旧 `generation-spec/probe_alert_boundary.py`，只给 REPO/OUT 换目标目录；文件未修改。JSON：`generation-spec-dca1bd6e/alert-boundary.json`，总日志 `alert-probe.log`，两例 stdout/stderr 同目录。
3. **原完整入口四例：4 passed / 0 failed，进程 exit 0。** 原文件 `generation-spec-final/probe_final_entry_boundaries.py` 未改，只传新 `--repo/--output-dir`。结果逐项如下。

| 原用例 | 退出码 | 生成根/操作根变化 | receiver marker | 日志落盘 |
|---|---:|---|---|---|
| safe_external_alert | 1 | 均空 | 无 | 安全外置日志正常有内容 |
| generation_rejected_alert | 2 | 均空 | 无 | 无错误位置日志 |
| l2_failed_alert | 1 | 均空 | 无 | 无错误位置日志 |
| receive_escape | 2 | 均空 | 无 | 无后续回退日志 |

结果 `generation-spec-dca1bd6e/entry-probe/entry-boundaries.json` 明确记录开始/结束同一 dca1bd6e、`target_status=""`。各例 stdout/stderr 同目录；总日志 `generation-spec-dca1bd6e/entry-probe.log`。本轮三个分母分别报告，不混入父任务的 pytest 读数。

复跑完整入口原探针的命令：

```bash
env -i PATH="$PATH" HOME="$HOME" PYTHONDONTWRITEBYTECODE=1 \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  /Users/a77/.finance-runtime/open-work-execution-20260920/generation-spec-final/probe_final_entry_boundaries.py \
  --repo /Users/a77/.finance-runtime/open-work-execution-20260920/gate-generation/finance-workspace-private \
  --output-dir /Users/a77/.finance-runtime/open-work-execution-20260920/generation-spec-dca1bd6e/entry-probe
```

复跑须另选新输出目录保存新证据。新入仓 `scripts/review_probes/check_generation_finalize_boundaries.py` 与原文件的 diff 仅有说明文字、开始时“干净检出/新外置输出目录”约束、结束时 clean 判据；四例配置和 passed 表达式完全未改。本轮为保持原判据，执行的仍是原仓外文件，不把代码比对称为又一次入仓版执行。

## 测试修正和结论边界

- `tests/test_review_plan_alignment.py` 为当前 quoteless_sectors 查询补了真实需要的 sector/price/pct_chg/amount 列和正常值，并新增把三项行情值清 NULL 后仍拒绝的断言；不是删除空壳检查或 mock 成恒绿。
- 新 shell 回归同时要求成功时 receiver 能运行、失败时 receiver 和落盘告警不运行；新 notify 回归覆盖两种代码根与文件链接/父目录链接/HOME 内置/合法外置配置。以上为源码审阅，作者 88P 由父任务记账，不冒充本轮独立 pytest。
- 旧 `generation-spec.md`、`generation-spec-final.md` 及其全部失败证据保留原样。独立原始结果、脚本与报告 SHA-256 写入 `generation-spec-dca1bd6e/manifest.json`。
- 本结论不认证运行期恶意换软链、任意新增 writer、真实模型回合、业务矩阵 SQL、真实知识库接收或生产同日/跨日/L2 门；原来明确的静态校验边界保留。未完成或正在运行的全量结果不得由本报告补成通过。
