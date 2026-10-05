## 这个分支做什么

修 `scripts/check_test_receipt.py --require-full-scope`：位置参数 `target` 不是仓根也判收窄；表头「目标」行与判定行同源。PR https://github.com/moscrol/finance/pull/51 （未合，合入须用户确认）。

## 决策与被否方案

| 采用 | 未采用 | 理由 |
|---|---|---|
| 仓根 = 空 / `.` / 与 `tree` normpath 相同 | realpath 解析链接 | 收据常在别的树验，不该依赖本机文件系统；本机 0 例别名 |
| 认不出（缺 tree、别名、上级相对路径）判收窄 | 判「不知道」 | 拦截门朝安全方向错 |
| `.` 认作仓根（用户口径） | conftest 补记调用目录 | 不动写方；漏洞写进 PR |
| 旧格式 + 文件清单判 ✗ | 保持 ? | 位置参数已足以判定 |

## 当前状态

修复、测试、lessons_learned、本交接均已提交推送，无未提交改动。CI 看 PR。

## 已验证

- 先红后绿：最终测试文件打 `origin/main`（09f53a731）11F/28P，改后 39P；9 条仓根护栏新旧都绿，由变异钉住。
- 变异 16/16（spec 在 `~/.finance-runtime/reviews/receipt-full-scope-target-1005/`）。
- 复现收据 `20261004T172818Z-f7ca7f1c-…` 改判 ✗；全量门禁收据 `gate-2eUm3mTe` 仍 ✓。
- 调用方：开关只有本脚本与测试引用；`run_main_gate.sh` 走 `main_gate_receipt.py`。
- 终轮 ruff + 6 个收据门禁文件按最终 head 跑，读数见 PR 评论。

## 未验证 / 已知边界

- 子目录里显式 `pytest .` 会被认成仓根：唯一的 fail-open，根治要写方记 `config.invocation_params.dir`。
- `--require-target` 子串语义未动：全量收据过不了 `--require-target tests/x.py`。
- 全量 `pytest -q` 本机没跑，靠 CI python 叶子。

## 下一步

CI 绿 + 用户确认后合入，合入后删本文件。要堵 `.` 的洞另开单改写方。

## 踩过的坑

- `rg -- 'pat' -g '*.py' .`：`--` 后的 `-g` 成了路径，过滤失效；模式改用 `-e`。
- 首次 push 报 `remote rejected (failed)` 无原因，重推成功；推后 `ls-remote` 核 head。
- 沉淀：原则进 lessons_learned；收据语料盘点没做成脚本——一次性审计，结论已进 docstring。
