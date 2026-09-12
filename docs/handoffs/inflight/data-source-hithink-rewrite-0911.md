# hithink-rewrite-0911：同花顺重建 09-11 日线（五项阻断已修，待复审）

## 待复审，仍未换库（先读这节）

8ac5a788 修完 QC 五项阻断，干净树全量收据 9,485 passed（`20260912T194535Z-8ac5a788`）。
生产库仍未动。下一步：QC 复审五项 → 用户授权 → 正式换库（命令见 repair-plan.md；
换库现在一次原子交付主表修复+派生重算+换名前备份，无换库后补跑）。
禁令：勿凭隔离克隆成功绕过复审；勿扩大回填日期；302132 历史回填需单独授权。

## 五项阻断修复落点（8ac5a788）

1. G1 闸门：`write_path` canonical 身份=包相对∪git common-dir 主树∪env 钉，
   与检出位置脱钩；探针 `--child --db 真库` rc=2、写入函数未到达。
2. S1 白名单接 `hithink`：修后克隆板块拼接恢复 403/403（修前 0），_today_values 3→5,550。
3. S2 派生收进 staging 子进程：technical+window 随换库原子交付；302132 历史缺口
   置缺并声明（window 跨缺口拼接值不可补入，technical 天然 0 行）。
4. S3 RepairSpec 钉新增票三前提（当日无事件/dump 有昨日 bar/逐字段预期）；
   合成现金事件探针现在拒跑。
5. S4 `db.backup_before_swap`：守卫后换名前备份，sha256+只读验证+恢复步骤收据；
   修复 CLI 强制开启。实测备份指纹==生产库当前 sha256。

## 关键口径（QC 修正后）

- pct_chg 转回 DECIMAL 后舍入（中间除法为 DOUBLE，非全链 DECIMAL）。
- 对账：pct 5,530/5,530；volume 5,546/5,546；amount 5,545/5,546+1 白名单漂移（600176 −0.0001 亿）。
- 302132 钉值：63.42/64.35/−1.45/5.9863 亿/94,471 手；fact_market_daily 复盘会口径不重算，声明 +1 跌家/+5.99 亿。

## 证据指针

- 方案与落点表：`~/.finance-runtime/db-repair/hithink-20260911/repair-plan.md`
- 反向证据：同目录 `verify-after-fixes/`（static 探针 + 隔离克隆端到端）
- QC 报告：`~/.finance-runtime/reviews/hithink-cd7f6fa9-20260913/review.md`
- 决策留痕：docs/handoffs/2026-09-13-hithink-five-blockers-fix.md

## 已验证

- 定向 41 条（含新增 14）；全量 9,485 passed 干净树收据可采信；ruff 全仓过。
- 隔离克隆端到端：fact 5,553、派生两表重算、302132 置缺、600176 avg=93.1062、备份指纹一致。

## 未验证 / 已知边界

- 未换库；QC 复审未做；并跑表补齐（拍板项 3）未做。
- G1 跨克隆形态（独立 clone 代码写主仓真库）靠 env 钉，真机未实测。

## 踩过的坑

- 全量收据必须对应 clean tree 的 commit，脏树的绿不算数。
- 「补一行」承诺先验派生窗口历史够不够，否则重算产出 0 行。
- 交接 ≤3K 字节 ≠ 关键内容能注入；以实跑 scripts/session_facts.sh 为准。
- 派生表随主表同库文件：换库后补跑=直写生产，收进 staging 子进程才原子。
