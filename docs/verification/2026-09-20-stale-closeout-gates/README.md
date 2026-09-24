# #805 / #806 本地完整门禁证据

证据对应两个不同的候选提交，不是一个合流版本，也不是本文件所在文档分支的全量签字。作者侧复验，不冒称独立评审。背景、被否方案和权限边界见 `docs/handoffs/2026-09-20-stale-closeout-gates.md`。

| 候选 | 完整 SHA | Python 全量 | 前端 / E2E | 判定 |
|---|---|---|---|---|
| #805 生成降级 | 4aa805400690d3d1b9f9a02eae765a85810d0db8 | 11913P / 85S / 2X | 110P；34P / 2S | 本地门禁通过，未合 |
| #806 宽基首轮 | 5d46e626abf4eec3f2f384747e3152959b3e2f90 | 1F / 11917P / 87S / 2X | 110P；34P / 2S | PATH 漏 uvx，失败保留 |
| #806 补齐 PATH 后 | 同一完整 SHA | 11918P / 87S / 2X | 同 SHA 的 110P；34P / 2S | 本地门禁通过，未合 |

P=passed，F=failed，S=skipped，X=xfailed。两树本地图有无不同，条件性结构探针的执行集合也不同，不直接以通过数之差推断代码覆盖增减。生成降级的 85S/2X 与本轮基底历史读数一致；宽基有图时三条空图探针跳过、结构探针执行。E2E 两个 skip 是绑定测试只跑 desktop、不在 tablet/mobile 重复。

## 采信条件

- Python：`python-registry.json` 中 complete、identity_stable 均 true，首尾 HEAD 完整等于目标、全树 status 为空；所有 checks 的 exit_code 都为 0 才通过。
- 前端：`frontend.json` 中 complete、identity_stable 为 true、dirty 为 false、exit_code 为 0；六步均执行，原始日志 SHA-256 与收据匹配。
- pytest 原生收据另由 `scripts/check_test_receipt.py --expect-revision <完整SHA> --base-drift-max 0` 校验。身份可采信不等于测试通过，失败收据仍应原样保留，不能只看身份检查的 exit 0。
- 知识库与研究站均为固定、干净的邻仓检出，版本和白名单见 `environment.json`。四项 registry 和 ledger-crosswalk 逐项运行，不因 pytest 红而跳过。
- data-quality-check 仅在其 workflow 指定路径变化时适用；两张候选均未改那些路径，本轮不声明运行了该叶子。

## 原件导航

- `generation-degrade-python/`：#805 全仓 Ruff、pytest、四项 registry、ledger-crosswalk、目标身份和 pytest 原生收据。
- `broad-index-python/`：#806 首轮完整失败原件，不覆盖、不算通过。
- `broad-index-python-corrected/`：#806 补齐工具路径后的完整通过原件，全部七项 rc0，首尾身份稳定。
- `codemap-missing-tool/` 与 `codemap-tool-present/`：同 SHA/同单项，仅 PATH 不同，1F 与 1P。
- `code-map-daily-full-{clean,inherited}.json`：遗漏工具的环境为 ready/empty hits，工具可达时为 ready/20 hits。
- `*-frontend/`：两组各六步原始日志及 frontend.json，端口隔离，不借 8792。
- `generation-receipt-check.txt`、`broad-receipt-check.txt`：两个最终成功运行的严格身份校验输出，base-drift=0。
- `merge-main-*.txt`、`merge-candidates.txt`：三次 merge-tree 的树对象输出，均 exit 0；没有创建或合入合流提交。
- `stack-check.txt`：2/2，两个分支不是堆叠依赖。
- `pr-state-before.json`：发布验收评论前只读查询，两个 PR 仍 open / merged=false，base 为 728f3271。
- `python-runner.py.txt`、`receipt-redirect.py.txt`：现有执行脚本逐字节副本，不是新生产入口。前端 runner 属于每个被测提交，收据已有哈希。

源目录：`~/.finance-runtime/reviews/stale-work-closeout-20260920/acceptance-20260920/`。SHA256SUMS 对本目录的封存文本逐字节绑定；不提交 graph.db、测试数据库、浏览器二进制、依赖或缓存。原始日志包含 ANSI/警告/结尾空行，不能为消除 whitespace 提示而改写。

## 不成立的推论

没有合 main、部署、删除旧树、触碰生产 L2/索引/launchd、生产采集或回填。没有新增模型会话或独立/付费外审。#770 材料合同、同数重算、两参数表格接口及旧前端尾项未在本轮解决。两份分支绿不可拼接为合流绿；合入后必须绑定实际提交重验。
