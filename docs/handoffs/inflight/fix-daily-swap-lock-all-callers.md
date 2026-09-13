# daily-swap 换库契约：四~六轮修补，待独立复审

## 状态（先读这节）

基于 `data-source/hithink-rewrite-0911` @ 601db6dd 叠五刀：`ed0dce4c`（四轮 P1）、
`7c89ca81`（五轮三项）、`941373b8`（六轮 P2）、`650c3d37`（六轮 P1）、本次口径修订。
**生产库未动、未合并。** 修的是公共 staging 编排的换库契约，不是 hithink 数据本身。

**下一步**：独立复审 → 用户确认合并与生产换库（门禁已全绿，见收据）。
禁令沿用上游：勿凭隔离克隆成功绕过复审；勿扩大回填日期；勿直接跑生产命令。

## 背景与理由（不在本页，别在这里找）

- 完整理由、实测表、被否方案、反向证伪明细：`docs/handoffs/2026-09-13-daily-swap-round6-fixes.md`
- 六轮独立审查报告：`docs/handoffs/2026-09-13-daily-swap-round6-qc.md`
- **换库威胁模型是单一口径，在 `market_feature_store/db.py` 顶部注释块**。下结论前
  先读它；任何「已修复」都只在它写明的条件下成立，别在别处再写第二份。

## 当前边界（说「已闭合」之前先读）

- **既有库**：`assert_same_target` 与 `os.replace` 之间的窗口**不闭合**（POSIX 无按
  inode 条件换名的原语）。只能说「把静默覆盖变成可检测的拒绝」。由
  `test_identity_check_and_replace_are_not_atomic` 钉住——它是可重复的反例，**不是
  措辞门禁**：把注释改回「已闭合」它照样绿，措辞是否越界仍由评审判断。
- **首次建库**：absent→present 已由 `os.link` 的 EEXIST 原子拒绝（六轮 P1）。**不能
  顺势扩大成「换库整条链已原子」**，也不含未测的断电持久性。
- **裸字节直写**（cp/dd 写进同一 inode）：身份不变，校验看不见，仍不在威胁模型内。
- **不要写「本仓所有写者都是协同方」**：`scripts/db_delta_pull.py::restore_baseline`
  保留着不取任何协调锁的 `os.replace` 恢复路径（只证明代码在，不声称在生产运行）。
- 锁窗内不重跑 `probe_no_active_writer`：持 SH 即证明无 duckdb 写者，重跑会被自己拦下。

## 收据（候选 a42cbc5c，干净树，`.venv-workbench/bin/python`）

- **全量 9,517 passed / 0 failed / 77 skipped / 1 xfailed，445s，exit 0**；`ruff check .`
  全过。对账 9,502P+1F（7c89ca81）+ 新增 14 条 = 9,517。五轮起一直红的
  `test_installed_codex_sandbox_*` 本轮绿——本机已知抖动，**绿不等于永久修好**。
- 定向三文件 57 → 62 → **71**。反向证伪：P2 四条真红、P1 两条不引用新符号的真红
  （`rc=0` 而非 2）。
- **未做数据端到端对账**（本刀不动数据）。跑全量前先看有没有别的树在跑。
- 合并预检：落后 main 35 / 领先 17，三个源文件 main 侧零漂移；唯一冲突是
  `.claude/lessons_learned.md` 双方都追加在末尾，保留两段即可。

四条可迁移教训已落 `.claude/lessons_learned.md`「换库与并发窗口」段。
