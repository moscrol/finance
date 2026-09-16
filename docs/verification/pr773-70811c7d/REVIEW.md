# PR #773 独立质检：阻止合并

日期：2026-09-16。用户授权：质检，没有问题再合并；未授权刷新生产快照或重装夜跑。

## 审查对象与结论

- PR：`feat/l2-share-source-port-0916@70811c7d67da5db959b5af9b9d788dbc1fb8ebaa`。
- 主干：`c29a64011da4a82ea94dbd16797639aca66c0158`，包含 #772。
- 干净合并候选：`b6e09b66000f87f807b6191c0039c7859194118d`，树哈希 `40048d4fafb5485c12230fbe2d175e04258976af`。本地通过 merge-tree / commit-tree 构造，仅供测试，未推送到 main。
- 被测树：`~/.finance-runtime/reviews/pr773-qc/finance-workspace-private`。测试前后均无未提交改动。
- 结论：现有四片检查通过，但发现并离线复现 **1 个 P1、1 个 P2**。#773 不合并，不修改作者代码或运营覆盖层。
- CODE_ROOT 决策：静态调用链支持 L2 脚本与 Python 模块来自代码根，分享入口、缓存、库、输出按数据根解析，Cookie 按家目录解析。未发现需要恢复 DATA_ROOT 加载代码的理由；这里不把静态审查当作真实下载部署验收。

## F1 / P1：损坏或残缺日包会写成 complete，质量门放行，后续跳过补算

位置：`scripts/moneyflow/process_l2_archive.py:70`、`:147`、`:168`、`:241`；后续消费者 `scripts/moneyflow/run_l2_from_share.py:27`。

`extract_trades` 对 7z 非零退出只打印错误，随后把已存在文件作为正常结果交下游。缺票在 `rows_for_codes` 被计为 empty，但 `processed_count` 无条件等于候选数，`failed_count` 写死 0；quant 同样如此。只要 capital 榜剩下至少一行，现有 writer 与 `check_l2` 都会接受这些自报统计。`already_complete` 只看三步状态，之后直接跳过。

复现使用真实候选代码的解包控制流、CSV 解析、资金计算、DuckDB writer、质量门与下次运行判定。仅名单、网盘/解压外部资源和公司信息替换为确定性夹具；临时库使用真实 schema，无生产读写或外网调用：

- 候选 100 只，解压命令返回 2 并报告 CRC/Data Error，仅输出其中 1 只的 CSV。
- 实际 top100 写入 **1 行**，台账却为 `complete / input=100 / processed=100 / failed=0`。
- limitup、top100、quant 三步全部 complete，`check_l2(...) == []`。
- `already_complete(...) == True`，普通重跑不修复。真实 `run_date` 成功路径还会删掉本地缓存，这部分为源码判断，本探针没有调用清理。

证据：`partial-archive.log.txt`；复现：`probe_partial_archive.py <候选仓路径>`。

建议返修：解压失败在任何榜单写入前终止；按真实成功/缺失/失败分别计数，区分缺文件与确认无成交，尤其不能让已有当日成交额的 top100 缺票归为成功空结果。加入贯穿 writer、质量门和再次运行的回归，保证失败不能留下可被后续跳过的 complete。

## F2 / P2：README 推荐的相对 FINANCE_PYTHON 在 cd 后失效

位置：`scripts/moneyflow/run_l2_pipeline.sh:17`、`:144`、`:145`；文档示例 `scripts/moneyflow/README.md:24`。

README 使用 `FINANCE_PYTHON=.venv-workbench/bin/python`。脚本开始时该路径有效，日历探针与台账可执行；但随后 `cd "$moneyflow_dir"`，同一相对路径变为 moneyflow 子目录下的路径，执行日包入口立即报不存在并返回 127。

复现以假 CODE_ROOT/DATA_ROOT 和临时 HOME 运行真实 shell 入口，联网/落库子脚本全是安全桩：相对路径 **rc=127**，同一个解释器换绝对路径 **rc=0**。因此不是解释器缺依赖，也不是切到冻结快照本身有错。

证据：`relative-python.log.txt`；复现：`probe_relative_python.py <候选仓路径>`。

建议返修：在改变 cwd 前规范化含路径的解释器值，或者保持 cwd、用绝对脚本路径执行；对文档中的实际命令增加行为测试。不要只改静态字符串断言。

## 四片检查

解释器均为 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python 3.12.13，未绕解释器门禁。以下读数仅对上述合并候选成立：

| 叶子 | 结果 |
|---|---|
| Python | `ruff check .` 通过；`pytest -q` 11168 passed / 81 skipped / 2 xfailed / 0 failed，538.87 秒，exit 0 |
| 前端 | `pnpm lint`、`pnpm typecheck`、`pnpm test`（107 passed）、`pnpm build` 均通过；依赖按 frozen lockfile 离线安装 |
| E2E | `pnpm test:e2e` 34 passed / 2 skipped，约 1 分钟 |
| Registry | check-parseability、check、backfill-tables --check、generate-views --check、audit_ledger_spec_crosswalk 均 exit 0；缺外部仓按仓内 CI 语义跳过跨仓比较，反向台账 98 条仍为 warning 档 |

Python 收据：`pytest-receipt.json`（dirty=false、exit_status=0）；全文 `pytest.log.txt`。
E2E 端口使用 18791 / 18794，避免占用生产。首轮漏设 `RE06_E2E_URL`，测试仍访问 8794，造成 1 failed / 33 passed / 2 skipped；这是本审查环境错误，不归因 #773。补齐后全量重跑为 34/2，两个原始日志分别保留。

E2E 最终环境：`WORKBENCH_PYTHON` 指向上述解释器，`WORKBENCH_E2E_PORT=18791`、`RE06_E2E_PORT=18794`、`RE06_E2E_URL=http://127.0.0.1:18794`。

两个探针 exit 0 的含义是“成功复现缺陷”，不是产品通过。现有全量检查未覆盖这些反例，不能用绿测推翻具体失败证据。

## 复跑与边界

```bash
PY="$HOME/finance-workspace-private/.venv-workbench/bin/python"
TARGET="$HOME/.finance-runtime/reviews/pr773-qc/finance-workspace-private"
"$PY" docs/verification/pr773-70811c7d/probe_partial_archive.py "$TARGET"
"$PY" docs/verification/pr773-70811c7d/probe_relative_python.py "$TARGET"
```

- 只读审查生产源码，不访问百度 Cookie，不转存网盘文件，不下载真日包，不写生产 DuckDB，不刷新 runtime、不安装 launchd。
- 未证明线上已经发生损坏榜单；证明的是候选对明确故障的错误处理，并且现有门禁检不出。
- 两个脚本是固定缺陷的审查证据，不是新生产入口或通用框架。返修方应将“正确行为”迁入正式回归，并保留正常日包与绝对/相对解释器的正例。
- 可复用原则：完成数必须来自真正完成的工作，不能从计划候选数复制；质检若只信生产者自报统计，会与生产者一起误判。
