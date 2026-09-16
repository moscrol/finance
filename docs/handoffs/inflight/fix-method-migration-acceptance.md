# fix/method-migration-acceptance（在途）

## 状态：**已合入 main（fc2f9e9e，PR #741 @ f680a2e6）**。本线关闭。

接替 `feat/method-closed-loop`——已由 **#738（694584df）合入 main**（至 `7f9d7ce1`），
分支与工作树已清理。本分支是质检 `7e66c8e8` / `d4025c97` 剩余项的收尾，基线 `c703e068`。

- `a2ecd8e9`：cherry-pick `7d193f1c` 台账补丁（恢复 R-20260831-02 真实历史原件），
  registry 存量红 exit 2 → 0。
- `ced46b7b`：④ 验收从叮嘱改成会退出的 `verify_history()`（history / record 解析 /
  report 任一失败即非零，⑤ 不执行）；测试直接执行文档里抽出的验收代码。
- 最新提交：正例断言升级为「整行含值」（2.0000% / 4.0000% / 6.0000%，共同日期 1；
  值来自固定夹具）——质检 d4025c97 的「留名称、删数值」变异已确认变红。
  迁移方案里的失效测试名引用同步更正。

## 门禁（最终尖 f680a2e6，已全部跑完）

python 整树 9462P/0F/77S，收据 `~/.finance-runtime/test-receipts/20260912T151910Z-f680a2e6.json`；
ruff、前端四叶、e2e 15/15、registry 五项均 exit 0（后两项见下）。
逐项日志 `/tmp/migration-gates-f680a2e6/`（本机临时目录，重启即失；权威凭证是收据文件）。

registry 注意：`build_registry.py` 按「**当前仓父目录 + 固定仓名**」定位仓库，
所以放在 `/Users/a77` 下的同级 worktree（`fwp-wt-*`）里跑时，`ws` 扫的都是主目录
`/Users/a77/finance-workspace-private` 的**工作树**（不是任意位置的树——放在 `/tmp`
就会因兄弟仓缺席而假绿）。主目录现被另一会话停在 detached 且带未提交的 skill 删除，
活树跑 check / backfill --check 必红；沙箱（干净副本）里本分支与 main 均全绿。
**主目录恢复干净前不要刷新注册表**，也不要为求绿去碰他人的改动。

e2e 注意：fresh worktree 没有自己的 venv，`pnpm test:e2e` 必须带
`WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，
否则落到宿主 python3.14 报 `No module named uvicorn`。

## 规矩

- **合并授权必须绑定 PR #741 与具体提交**，不继承 #738 的「存量红放行」。
- 不执行迁移、不改生产配置。迁移另需授权，执行前**重查待回检是否仍为 0**。
- 本线无其他写入者：合并会话 3474247f 已书面确认不代改 / 代合 / 清理本线。

## 收尾

已合并。迁移与生产切换是独立授权事项：执行前重查待回检是否仍为 0，验实际夜跑代码根 /
用户根 / 环境变量覆盖，验收以真实 history 原件 + 夜跑实际选择 + capture 结果为准。
