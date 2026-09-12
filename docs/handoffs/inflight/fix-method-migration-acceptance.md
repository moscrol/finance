# fix/method-migration-acceptance（在途）

## 状态：修复已提交，门禁未跑完

接替 `feat/method-closed-loop`——那条线已被 **#738（694584df）合入 main**（23 个提交，
至 `7f9d7ce1`），分支与工作树已清理。本分支是质检 `7e66c8e8` 剩余项的收尾分支，
基线 `c703e068`。

- `a2ecd8e9`：cherry-pick `7d193f1c` 台账补丁（恢复 R-20260831-02 真实历史原件），
  修复 registry 存量红（`audit_ledger_spec_crosswalk.py` exit 2 → 0）。
- `ced46b7b`：④ 验收从叮嘱改成会退出的 `verify_history()`（history / record 解析 /
  report 任一失败即非零，⑤ 不执行）；测试直接执行文档里抽出的验收代码，负例断言
  非零 + 哨兵未执行，正例补齐三组读数与共同可评估日期数。三种变异各抓红。

## 规矩

- **合并授权必须绑定本 PR 与具体提交**，不继承 #738 的「存量红放行」。
- 不执行迁移、不改生产配置。迁移另需授权，且执行前**重查待回检是否仍为 0**。
- 本线无其他写入者：合并会话 3474247f 已书面确认不代改 / 代合 / 清理本线。

## 下一步

跑全套门禁（Python 全树 / 前端 install·lint·typecheck·test·build / e2e / registry），
逐项留退出码与收据，然后开 PR 附证据申请合并。
