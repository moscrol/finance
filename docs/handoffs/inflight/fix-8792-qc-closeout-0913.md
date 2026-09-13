# fix/8792-qc-closeout-0913：8792 交付 QC 收口（S1/N1/E3/S2 已修，待合 main + E2 设计任务 + 复验）

## 这个分支做什么
按 QC-2026-09-13（判「部分通过」）的顺序收口：先修材料题路由与 L2 口径，再文档化
模型混合链并更正复验文档。基线 `5fb13a8c`（gitea/main）。

## 已完成（逐提交）
- `a38822df` S1+N1：`query_understanding` disclosure 闸改量完整原文 raw_text（原量拆分
  尾问，802 字变体仍被劫）；新增 `route_table.quick_fact_route_ok`（意图+短或无材料），
  turn_controller 与 answer_orchestrator 三调用点共用，192 字取值题两入口一致。
  回归锁：802 变体端到端、192 字两入口、材料+取值意图被闸（30 passed + 1 xfail）。
- `97eedb2a` E3：当日涨幅%统一日线口径。`duck_pct_chg_map` + L2QueryService 读出侧覆盖
  （旧缓存命中也纠正）；缺日线写 NULL 不冒充；write_to_duckdb 空值安全 +
  `pct_chg_canonical_missing` 进台账 message。**已重算闲鱼窗口 12 天（08-27→09-11）：
  1961+536 行 0 不符 0 反号 0 空值**。更早 52 天（ClickHouse 时代）修口径**不改重算**：DELETE 按日期+scan_type+阈值三元组作用（50 万阈值旧行删不掉），且综合分用实时市值（重跑会污染历史分）；正确路径是从 fact_stock_daily 直接回填 pct_change 列（12,717 行可匹配，2 行缺日线保留 NULL 并登记），待用户拍板。
- `480b3af7` S2：`mark_calendar` 每跑必写 `ops_pipeline_run_daily` 的 `step=calendar` 行
  （trading/closed/unknown），实测 09-11 写入正常。
- `f2831fd2` QC 报告 cherry-pick；`58dda6f5` RESULTS/README 按 QC 更正（E1/E2/E4/L2）。

## 运营覆盖层（主检出树未提交，勿提交别人的文件）
主检出树 `scripts/moneyflow/` 的闲鱼副本（untracked：process_l2_archive.py、
run_l2_from_share.py、baidu_share.py 等；modified：write_to_duckdb.py、run_l2_pipeline.sh、
moneyflow.py）已同步 E3/S2 同等改动——那是 L2 实际运营链（绑本机 cookie/state）。
本分支合 main 后，迁移收口需把覆盖层 rebase 到新基线（仓内版已含同名修复）。

## 关键决策
- E2（材料边界）**不做 ad-hoc 补丁**：根因三层（split 吞编号题组 / material-only 约束
  无契约投影 / 检索注入不抑制），只改合同会让裁判对注入失明。设计任务已写进
  RESULTS-2026-09-13.md「E2 设计任务」节，失败样本齐全。
- E3 覆盖放读出侧而非写入侧：磁盘缓存旧口径条目命中时同样被纠正，免清缓存。
- quick_fact 与五条词面共现路由分开入场：它按窄意图判，入场券看材料不看长度。

## 下一步（按序）
1. ~~合 main~~ **已合**：`e40f22b8`（合并树 CI 9549 passed / 0 failed）。
2. ~~部署~~ **已部署**：8792 服务已切换到 snapshot_path=`~/.finance-runtime/finance-workspace-e40f22b83717`，
   部署账本记录 switch、健康检查通过（source_revision=e40f22b83717、code_matches_repo=True、
   953 模块）；切换机制为 symlink `/Users/a77/finance-workspace-runtime`
   （readlink 证据：切换前 →finance-workspace-2ee664fae9c4，切换后 →finance-workspace-e40f22b83717），
   回滚锚 2ee664fa 保留。**部署账本 source_dirty=true**：原因是快照树里未跟踪的
   `.venv-workbench` 软链（部署脚本 `$REPO/.venv-workbench/bin/python` 需要它；服务本身用
   启动器里主树 venv 的绝对路径，不读它）。该软链未进入加载指纹，部署后已移除，
   快照当前 git-clean；账本记录的是部署时刻状态，不 retroactive 改写。
   **RAG 口径差异（非线上告警）**：部署脚本侧 check_rag_readiness.py 报「知识库路径不存在
   ~/.finance-runtime/knowledge-base-private」（探针时间 2026-09-13T10:35Z 复现）——该路径
   假设陈旧，真实知识库在 ~/knowledge-base-private（启动器 KB_RAG_PYTHON 所指），服务
   health 的 knowledge_wiki/relations/vector_index/rag_runtime 四布尔均 true。两探针口径
   未对齐，记为非阻断待核对项（探针路径修正另立小任务）。
3. ~~E3 旧窗口~~ **已关闭**：`fix/l2-pct-chg-backfill-0913`（`734e6613`）新增
   `--repair-pct-chg`，生产 52/52 天已回填：0 不符 0 反号，唯一 NULL=688797@06-24
   （两表各 1 行，日线本身无涨幅，已登记）；备份在 ~/.finance-runtime/db-repair/l2-pct-chg-20260913/。
   **该分支待用户确认后合 main**。
4. E2 设计任务：拆分吞题 + material-only 契约投影 + 检索抑制 + 逐题交付（Q8 备忘录）。
5. E2 修复后 T2/T3 重跑（全新会话）→ 正式 PK（未见新题、冻结双方原答）。
6. 运营覆盖层收口：主检出树闲鱼副本与仓内版已同内容（E3/S2/repair 之外无差异需核），
   迁移到仓内版运行是独立任务。

## 不要做
- 不要把 fix 树文件提交进主检出树；主树他人的暂存（如某 SKILL.md 删除）不要碰。
  本 session 两次误暂存主树文件均已 git reset 退回，且 e40f22b8 提交内容不含这些文件；
  但**主检出树仍是多 agent 共享脏树（HEAD=b4a35fa2 detached、大量在途改动），不能拿它
  当 clean verification tree，后续 CI/部署结论一律以专用 worktree 为准**。
- 不要收窄写手链为单链 K3（08-16 重试风暴）。
- 不要在 E2 修复前宣布「材料题就绪」。

## 雷区（本session 12+ 次踩中）
**harness 每次 bash 调用都重置 cwd 到主检出树。** 每条命令必须 `cd <树> &&` 前缀——
包括 git add/commit（实测把主树 overlay 文件暂存进别人索引，靠 git reset 退回）、
pytest（主树跑出「全绿」假象）、read 相对路径。读数收据 rev 以 conftest 头部
「树: … @ <rev>」行为准，收据文件名里的 rev 未必可靠。

## 等价 CI 收据（全部可机审）
- 收口分支：`~/.finance-runtime/test-receipts/20260913T082354Z-f59ab082.json`——
  9542 passed / 0 failed / 77 skipped（rev f59ab082，dirty=守卫测试适配随后已提交
  `44feee2d`）；QC 复核自跑：`20260913T085357Z-2188a711.json`（dirty=false，同数）。
- 合并树：`~/.finance-runtime/test-receipts/20260913T094228Z-e40f22b8.json`——
  **9549 passed / 0 failed / 77 skipped**，rev e40f22b83717…，dirty=false，exit 0；
  ruff 同一调用内先跑，输出 All checks passed（exit 0）。
- 回填分支：`~/.finance-runtime/test-receipts/20260913T101411Z-ecc404da.json`——
  **9550 passed / 0 failed / 77 skipped**，rev ecc404da9d65…（=734e6613+docs 提交），
  dirty=false，exit 0。
- 三份收据同一解释器（.venv-workbench/bin/python 3.12.13）、同一依赖指纹 3328bed61f3e21ea。
- 主检出树同刻全量的 4 个失败是混合树自有工件（.claude/worktrees 残留引用 ×2、
  conversation_orchestrator、config 模块名撞车的预存在隔离缺陷），与本分支无关。
- 提交线：`a38822df`(S1+N1) → `97eedb2a`(E3) → `480b3af7`(S2) → `f2831fd2`(QC 报告)
  → `58dda6f5`(文档更正) → `f59ab082`(交接) → `44feee2d`(守卫测试适配)。
