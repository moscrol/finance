# 2026-08-11 · hook 可靠性修缮与 fix/gate-rejection-taxonomy 合并

分支 `fix/gate-rejection-taxonomy` 已合入 main（merge commit `09c490d6`，27 个提交，**未推送**）。
本文件由 `docs/handoffs/inflight/fix-gate-rejection-taxonomy.md` 转档而来（合并即转日期快照）。

## 落地了什么

**主线**：`validate_episode_finish` 的 `RejectionKind`（FORMAT / SUBSTANCE / INTEGRITY）分类层，
INTEGRITY（伪造证据哈希）直接拒绝不重试，FORMAT/SUBSTANCE 保留原重试逻辑。

**环境可靠性**：注入收窄（189K→11K）、解释器门禁、路径门禁、依赖锁文件、在途交接机制。

**本轮三处 hook 修复**（`9d0b5f17` / `5ac9b9d5` / `611a4aa9`）：

1. **stale 门禁改按分支归属判定**。旧判据「代码路径前缀 + mtime」是拿文件系统事实推断
   版本控制事实——未提交改动在 git 里没有分支归属，主检出树多 agent 共用时必然误报。
   现为两级：一级用 `<base>..HEAD` 提交时间（自带归属），二级把脏文件与
   `git diff --name-only <base>...HEAD` 求交集后再比 mtime；基线解析不了时退回宽判据
   但在告警里声明「未做归属过滤」。
2. **注入改按小节重排**。原 `NR<=12` 恰好只覆盖到「已做」，把「未验证/边界」「下一步」
   「踩过的坑」全截在预算外——截断砍掉的正是风险面。现把「已验证」类回顾性小节挪到末尾，
   预算不够时先砍它。同时把 stale 告警调到正文之前（它是对那份文档的信任度限定，
   放在后面会被正文挤出预算）。
3. **标记增删推迟到判定之后**。旧写法开头就 `rm -f` 标记再做慢 git 查询，
   SessionEnd 1.5s 超时或 Ctrl+C 打断时会无声销毁上一轮的合法标记。

## 验证

- **全量测试（干净 detached worktree，非主检出树）**：4513 collected，
  **15 failed / 4494 passed / 4 skipped**，207.91s
- **零回归对照**：同条件在 main 上跑同一批 5 个文件 = 15 failed，
  与分支侧失败集合**逐条一致**（两侧各 15 条非空，对照有效）
- 那 15 条是 main 既有失败，环境耦合类：`test_subconscious`（agent-memory vault 路径）、
  `test_userspace`（`USERS_DIR` mock 不生效，实际解析到 `~/agent-memory/.foresight/`）、
  `test_codex_headless_runtime`（installed codex sandbox）、`test_acceptance_board`、
  `test_ceiling_pit_fixture`。**不在本次范围内，但值得单独收拾**。
- stale 门禁变异五况：旧报警/新静默 A/B、一级判据独立触发、降级声明、
  中断安全性 A/B（kill -9 中途：旧版标记被销毁、新版存活）、收敛闭环双向
- 注入回退三况：无 `##` 小节 / 陌生英文词表 / 真实文档，均不出空且保住标题行
- hook 耗时实测 107~143 ms，对 SessionEnd 的 1.5s 预算有 ~10 倍余量
- pre-commit 8 道门禁 × 6 次提交全过

## 未做 / 待定

- **main 未推送**（领先 `origin/main` 29 个提交）。推送需另行确认。
- 上面那 15 条既有失败未修。`test_userspace` 的失败信息指向一个真实的
  测试/代码契约问题（mock 的是 `userspace.USERS_DIR`，生产码从别处解析），不只是环境噪声。
- 注入预算实测 2069 字符 > BUDGET=2000：组装循环「先判超限、再追加声明」，
  声明本身不计预算，溢出约 3%。已知，未改。
- BUDGET=2000 是否上调未决：现在风险面进来了，代价是「已验证」段常被砍（省略 9~11 条）。
- 交接记录 164K 历史未动（红线：不删别人记录）。

## 踩过的坑（都属「静默失真」）

- **mtime ≠ 版本控制归属**：旧门禁这次**结论对、理由全错**——真实原因是分支又提交了 2 次，
  它却在看不相干的 moneyflow 脏文件，两者 mtime 只差 2 秒。**验门禁要查它引用的证据。**
- **门禁自噬**：一级判据上线后，写完交接去提交，这个提交本身就比文档 mtime 新 → 当场又报警。
  可迁移：**任何「产物必须跟上源」的门禁，都要把「更新产物」这个动作排除在「源变动」之外**。
- **macOS 的 `sort`/`uniq` 在 UTF-8 locale 下把不同中文行判为相等**（CJK collation 主权重相同）：
  6 个不同小节被 `uniq -c` 合成 1 个、计数报 5。中文文本统计一律 `LC_ALL=C`。
- **awk 未初始化变量作数组下标是空串不是 0**：`body[sec]` 写进 `body[""]`，
  END 读 `body["0"]` → 没有 `##` 小节的文档注入全空、退出码 0。要 `BEGIN{sec=0}`。
- **「先清空再重算」在可被中断的执行体里不是幂等，是有损**。
- **空对空的差分不算通过**：第一次跑失败集合差分时，变量未发生词分割导致 pytest
  `no tests ran`，两侧都是空文件，`diff` 报「一致」。对照必须先断言两侧非空。
- **`touch` 不产生 git 改动**：用它做「改了代码」的反向验证会得到假的「门禁被修哑」结论。
