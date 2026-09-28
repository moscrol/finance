# fix/pi-review-sandbox-anchor-0928 在途

## 这个分支做什么
修 `tests/test_pi_review_repair.py` 的位置依赖伪红：从嵌套在主检出下的 worktree 跑，10 条审查沙箱测试停在 `configure_sandbox()` 的 `assert 2 == 1`。PR #957；代码只改这一个测试文件。

## 决策与被否方案
- 选：按 `prepare()` 生成的 metadata 规则切开策略，只在其余部分数并改写 venv 锚点，再按新树重新生成该规则。
- 否「放宽成 `>= 1`」：会连树祖先条目一起改写（变异实测 `0 == 1`）；否「只换第一处」：靠规则顺序；否「先换锚点再换规则」：basetemp 落在主检出下时旧规则里同样有该祖先。
- 加与位置无关的回归测试（合成嵌套路径 + 换 `sys.prefix`）：门禁都在主仓外跑，只靠原 10 条抓不到回归。

## 当前状态
- 修复 ef9d5ec67 已推，PR #957 已开，未合（等用户确认）。
- 本交接提交后在 PR head 上从嵌套位置跑全量 python 叶，读数贴 PR 评论，不再改本分支。

## 已验证
同为 20d49970a：嵌套树 10 红（全是 `2 == 1`），主仓外树 10 绿；两处打印断言前的策略做 diff，只差规则 14（嵌套侧多出主检出的三级祖先）。ef9d5ec67：两处整文件各 75 passed、用例集一致；主仓外新旧夹具写出的 10 份 tools.sb 逐字节相同；`ruff check .` 通过。日志在 `~/.finance-runtime/reviews/pi-anchor-0928/`。

## 未验证 / 已知边界
- 前端 / e2e / registry 三叶没跑：本 PR 不碰 webapp、skills、e2e 路径。
- 原 10 条要 macOS + `/opt/homebrew/bin/pi`，别处会 skip，skip 不是准入证据；新回归测试不受此限。
- 只修了这一处位置依赖；`/tmp` 下 Codex 沙箱测试那类位置红是另一回事，不在本 PR。

## 下一步
1. 看 PR 评论里的全量读数，用户确认后合入。
2. 合入后可删本交接。

## 踩过的坑
- 会话 Seatbelt 沙箱挡 127.0.0.1:3300，也挡嵌套 `sandbox-exec`：fetch / push / PR 与这批测试都得在沙箱外跑。
- `prepare()` 两个 axis 都写，每个测试只配置其一；比较策略时只取 `config.json` 里 tree 指向本次树的那份。
