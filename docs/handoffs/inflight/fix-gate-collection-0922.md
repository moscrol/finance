# 全树门禁收集中断（分支 `fix/gate-collection-0922`，未合）

一句话：**门禁命令 `pytest -q` 在 main 上从 2026-08-20 起必停在 collection error、一条测试都不跑；
本分支修好收集面，并让收据能自证「跑的是多大一片」「来自哪棵树」。修后全树 12462 passed / 0 failed。**

- 树 `~/fwp-wt-financial-comparison-0922`（与 `fix/financial-comparison-0922` 同树切分支）
- base `f783f19c8`(=main)，可 FF；与 `fix/financial-comparison-0922` merge-tree **零冲突**
- 未 push / 未合 / 未部署。长文与证据：`~/.finance-runtime/reviews/gate-collection-20260922/`

## 四个提交

1. `999c1b1fb` 收集面：`a41e86dfc`（08-20「孤儿脚本移入 archive」）把活脚本 `check_kb_freshness.py`
   的验收测试一并扫走，它用 `sys.path.insert(自身目录)` 定位被测脚本，一挪即断；`norecursedirs` 不含
   archive → 全树收集 Interrupted。测试移回 `tests/`，判据扩一句「归档区不得含 pytest 收集物」
   （同类误判已复发三轮，前几轮只量活代码→归档模块的断链）。
2. `661811b8a` 收据记收集面：`target` 只记位置参数，`--ignore/-k/-m` 不入账 → 「全量绿」不可审计。
   新增 `scope` 段 + `collected`，counts 补 xfailed/xpassed 以便收执对账，
   `check_test_receipt --require-full-scope` 读它（默认只报不拦，验子集是正当用法）。
3. `e3e884560` 文档 + AGENTS.md 一条（收据要能自证收集面）。
4. `4cc731ebf` 指针按树隔离：`latest.json` 全机单文件，多树并跑谁后结束谁覆盖（实测撞上两次）；
   `session_facts.sh` 会据此劝你「不必重跑」，`run_main_gate.sh` 会把别人的数抄成门禁结果。
   改写 `latest-<树>.json`，三消费者改读它；顺手认掉没人认的 `FWP_TEST_RECEIPT_DIR`。

## 读数与验证

| 项 | 结果 |
|---|---|
| `pytest -q` 全树（无 --ignore）@`b450d1db9` 干净树 | **12473P / 85S / 2X / 0F**，26m58s，exit 0；不带参数跑校验器即挑中本树收据，十项全 ✓ |
| `ruff check .` | All checks passed |
| 撤保护 | 归档 2/2、scope 6/6、指针隔离 6/6 全红 |

## 口径纠正（合并时值得知道）

08-20 后收据库有 **187 张**「≥10000 passed / error=0 / exit=0 / target=仓根」的收据，回查其
**176 个 revision 全部带着那个坏文件** → 只可能是**收窄过**的读数，而收据当时记不出收窄，已无法回溯。

## 明确没做到

- Gitea 仍不跑 Actions，`workbench-check.yml` 依旧是一张纸，门禁还得人手跑。
- 同树 `fix/financial-comparison-0922` 的 13352P 是绕开坏文件得出的；合并后应重跑。
- #835 独立终审仍 `BLOCKED_PROVIDER_CAPACITY`；R6/R3 自然四题仍 0/4，本轮未动。
- **与 PR #814（per-run 不可变收据，WIP）在 `conftest.py`/`run_main_gate.sh` 文本冲突、语义互补**，
  整合配方（哪一侧为准、怎么合）写在证据目录 `README.md` 末节。
