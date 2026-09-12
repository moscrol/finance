# 方法闭环 / 同步代码根两份汇报联合复核

审查时间：2026-09-12 19:06 左右；仅审查，不授权合并、部署或补数。
审查分支：`docs/review-method-sync-0912`，基线 `gitea/main@6382c13b`。

## 审查对象与变动

用户所贴对象：`feat/method-closed-loop@2f5c7a03`（PR #738）、
`fix/sync-code-root@abc9b182`（运行代码与 `aef500e2` 一致，最后一提交只改交接）。
审查期间两边分别增加 `779b6ee2`、`8e1ea623`，已另外冻结补验，不混用读数。
远程复查时 #738 仍指向 `2f5c7a03`，同步分支仍无远程 ref。

## 结论

- 两处文本冲突属实，建议的解法在源码层可行。不是合并放行凭证。
- **不能照旧汇报直接合 #738**：其远程尖仍有两个已复现缺陷；本地继任
  `779b6ee2` 已修且两个反例转绿，应推送后对新的 PR 尖验收。
- **同步分支暂不作为完整修复放行**：旁路关闭是真修复，但删除旧 all 后丢失了
  手动补跑路径「同步失败仍尝试 L2」的保证；#51 是欠账登记，不是修复。
- 合并与运行恢复分列。生成根 #50、L2 编排 #51、装机差异未闭环，不能宣称夜跑恢复。
- 顺序建议：方法修复尖更新 PR 并满足门禁后先合；同步分支随后解冲突、冻结集成尖再验。
  这是建议，不是用户已批准的顺序，也没有执行任何 merge/rebase。

## 发现（仍存在）

### P1：安全关旁路同时移除了手动路径的 L2 独立保证

位置：`skills/daily-full-review/scripts/nightly_full_review.sh:93-103,285-303`；
`skills/daily-full-review/SKILL.md:88-101`；`tests/test_pipeline_p0.py:676`。

隔离 shell 执行（全部 Python/外呼/L2 执行器用临时桩替代，未连接生产）：

- 旧 `all 2026-09-11`：同步桩 exit 17，随后仍有 `L2_ATTEMPT`，最后 exit 17。
- 新推荐 `S7 && finalize`：同步失败时 shell 不会启动 finalize。
- 新 finalize：数据守卫桩 exit 2，在调用 L2 前退出；合并候选与装机副本同样如此。

所以「finalize 与原 all 等价」只适用于同步成功的后半段，不适用于失败路径。
**不能恢复直写生产的旁路，也不能把 && 改成分号让生成无条件跑。** 应在外层编排分别
记录 sync/L2 结果，L2 独立尝试，生成仍要求条件全部满足，聚合退出码保留失败。

最新 `8e1ea623` 只更新文档/测试，脚本字节没改：旧测试被改为断言 `guard < l2`，
因此测试绿不是恢复不变量的证据。可以保留现状刻画，但还需要目标行为回归；不能靠
把坏行为钉成期望来结案。

新增 #51 提议把 L2 前移到 finalize 守卫之前，可修**定时或直接 finalize**，但仍救不了
`S7 && finalize` 在同步失败时根本不调用 finalize 的手动链。#51 验收须补手动组合入口。
#51 记的真实库缺日读数本轮未独立查库，不用于推导本条代码结论。

### P2：「不许嵌套调用 S7」的新增测试可以被直接调用绕过

位置：`tests/test_eval_launchd_wiring.py:247-252`，在两个同步尖中相同。

为过滤 heredoc 帮助文本，测试排除了所有 `/bin/zsh /Users` 开头的行，又只判断
`$(` 或 `exec`。在临时脚本的 `finalize)` 后插入真实可执行的一行：

```sh
/bin/zsh /Users/a77/.local/bin/nightly-full-review-s7.sh "$D"
```

直接调用 `test_nightly_closes_the_staging_bypassing_sync_phases` 仍通过。
**变异脚本没有执行**，不存在真实嵌套启动。当前源没有这条调用，问题在防回归强度。
推荐真实启动脚本、用假 S7 写调用标记来断言未启动，而非按行前缀猜注释/帮助文本。

### P2 / 上线阻断：装机行为仍不同，且暂停开关未必应该“补回”

比对 `abc9b182` 仓内源与 `~/.local/bin` 实物：

- 5 个公共脚本字节一致；S7 仅注释/空行差异。
- 6 份 plist 用 `plistlib` 解析后不仅 EnvironmentVariables 一致，所有解析字段均一致；
  未据此推断 launchd 当前内存配置或任务成功执行。
- nightly 三组实质差异确认：moneyflow 两调用读 DATA_ROOT；没有暂停分支；缺三处 skip 留痕。
- 相同数据守卫 exit 2 的隔离执行，仓内源写 method skip，装机副本不写，行为证据成立。

装机源码明确注释「源是闲鱼日包，不再打 ClickHouse，也不再认 l2-paused.flag」。这提示
暂停差异可能是 L2 迁移的有意决定，不宜一概叫“欠着没补”。应由 L2 在途负责人确认
暂停契约，不能直接跑安装脚本覆盖（安装器对 nightly 使用无条件 cp）。
三处 skip 留痕则是独立观测修复，不应不加区分地捆绑成“必须先动 L2 才能做”。

## 发现（旧尖存在，新尖已修）

### 指针不可访问被误判为不存在

`2f5c7a03:intelligence/services/method_validation/store.py:269` 用 `os.path.lexists`。
先真实 register/activate 临时协议，再对其父目录 chmod 0600（取消遍历权限）：

- 旧尖：active --print-dir rc=4，无错误文本，state=unset；夜跑会回退内置协议。
- `779b6ee2`：rc=3，state=unreadable，明确 PermissionError；拒绝静默回退。

该测试结束后已恢复临时目录权限，没有改用户目录。

### --user 不限制 supersede 的写入边界

`2f5c7a03:scripts/method_validation.py:556-560` 只拿用户参数查 active，实际直接按
study-dir 写封存标记。临时用户根内创建 victim 协议，再执行
`supersede --user operator --study-dir <victim>`：

- 旧尖：rc=0，victim 的 superseded.json 被创建。
- `779b6ee2`：rc=2，明确拒绝跨根，victim 无标记。

新尖两处修复已独立行为复验，不再算新尖未修缺陷。但截至远程核验，#738 仍是旧尖。

## 冲突复核

两次 `git merge-tree --write-tree` 均 rc=1，恰好两文件：
`docs/superpowers/specs/2026-09-01-workorders-INDEX.md`、nightly 脚本。

- 旧尖组合 INDEX 留 #49 / #50；最新组合须留 **#49 / #50 / #51**。
- 脚本顺序：CODE_ROOT → REVIEW_CHECKER 与缺失拒绝 → REVIEW_SYNC_PLAN → LOG_DIR/mkdir
  → METHOD 绑定 → phase → 非 finalize 拒绝 → 加锁。export 在检查之前也不破依赖。
- 临时合并脚本 zsh -n 通过；date/sync/all 均 rc=2、无锁残留；这只验证该脚本，
  **没跑整树合并候选的全量**。#738 的 active 绑定读取有日志写入，因在拒绝前，因此
  合并后只能承诺「生产写入与加锁前拒绝」，不能字面承诺「任何文件写入前」。

## 收据（不要跨 revision 复用）

| revision | 他人全量原始收据复核 | 本轮独立执行 |
|---|---|---|
| 2f5c7a03 | 干净树 9447P/0F、exit 0 | ruff exit 0；6 文件 249P；两个额外反例失败 |
| aef500e2 | 干净树 9412P/1F、exit 1 | 同代码 abc9b182：ruff exit 0；48P/1F |
| 779b6ee2 | 干净树 9449P/0F、exit 0 | ruff exit 0；方法验证/飞轮 77P；两个反例修复成立 |
| 8e1ea623 | 截至审查未见该尖整树全量收据 | ruff exit 0；接线/pipeline 49P；无运行脚本修复 |

原始收据：`~/.finance-runtime/test-receipts/` 下
`20260912T103007Z-2f5c7a03.json`、`20260912T104352Z-aef500e2.json`、
`20260912T105415Z-779b6ee2.json`。
旧同步全量完整失败栈：`/tmp/full-aef500e2.log`（不是只有 tail 的摘要）。
本轮隔离探针/完整日志：`/tmp/two-branch-audit-rhBrSA/` 下 `probe_*.py`、
`*-probes.log`、`*-targeted.log`、`inventory.log`、`merge-tree*.txt`。
探针是这次 review 的特定反例，不做通用工具收编；长期回归由两个拥有分支在源测试内承接。

本轮未运行 frontend/e2e/registry-check、未独立重跑整树全量；未调用真实同步、生成、L2、
模型网关；未补 09-11，未重建共享库，未运行迁移或装机更新。
