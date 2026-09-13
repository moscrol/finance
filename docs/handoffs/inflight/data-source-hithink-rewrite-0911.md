# hithink-rewrite-0911：同花顺重建 09-11 日线（二轮阻断已修，待三轮复审）

## 待复审，仍未换库（先读这节）

9d73f01a 修完 QC 复审二轮两项 P1，干净树全量收据 9,490 passed（对应本 SHA，可采信）。
生产库仍未动。下一步：QC 三轮复审 → 用户授权 → 正式换库（命令见 repair-plan.md；
一次原子交付主表修复+派生重算+排他锁内备份）。
禁令：勿凭隔离克隆成功绕过复审；勿扩大回填日期；302132 历史回填需单独授权。

## 二轮两项 P1 修复落点（9d73f01a）

1. 备份→换名竞态：`db.hold_swap_lock` 对 target inode 持 flock LOCK_EX|NB，与
   duckdb 写者锁同命名空间（本机实测双向互斥），覆盖「最终复查→备份→换名」
   全临界区；锁内攻击 rw 打开必失败；拿不到锁 rc=2 不换名。日更不进锁。
2. status 遗留污染：开工即删旧 status.json + run_id 绑定（父 env→子 status→父
   校验），错轮/遗留/伪造一律 rc=2；两个真子进程（daily-full-exec/修复）都写 run_id。

## 一轮五项落点（8ac5a788，QC 已过 G1/S1/S2/S3）

G1 闸门候选集（git common-dir）探针 rc=2；S1 白名单接 hithink 拼接 403/403；
S2 派生（technical+window）入 staging 原子交付、302132 置缺；S3 spec 三前提；
S4 备份函数（二轮已包进排他锁）。

## 关键口径（QC 修正后）

- pct_chg 转回 DECIMAL 后舍入（中间 DOUBLE）；volume 5,546/5,546；
  amount 5,545/5,546+1 白名单漂移（600176 −0.0001 亿）。
- 302132 钉值 63.42/64.35/−1.45/5.9863 亿/94,471 手；fact_market_daily 复盘会
  口径不重算，声明 +1 跌家/+5.99 亿。

## 证据指针

- 方案与落点表：`~/.finance-runtime/db-repair/hithink-20260911/repair-plan.md`
- 反向证据：`verify-after-fixes/`（verify-round2.json 二轮 + 一轮 static/端到端）
- QC 报告：`~/.finance-runtime/reviews/hithink-8ac5a788-qc/review.md`
- 决策留痕：docs/handoffs/2026-09-13-hithink-five-blockers-fix.md（含二轮）

## 已验证

- 定向 46 条（含二轮新增 5）；全量 9,490 passed 干净树收据；ruff 全仓过。
- 端到端克隆重验：cli_rc=0、fact 5,553、302132 两派生表 0 行、备份指纹一致。

## 未验证 / 已知边界

- 未换库；QC 三轮复审未做；并跑表补齐（拍板项 3）未做。
- flock 只约束 duckdb 写者；裸文件写者（cp/dd）不在威胁模型。
- G1 跨克隆形态靠 env 钉，真机未实测。

## 踩过的坑

- 「备份后再查一次」不是 TOCTOU 闭环；闭合窗口要排他锁，且 flock 与 duckdb
  锁同命名空间是先验实验证实后才敢用的（别假设，先实测）。
- 测锁占用夹具用 LOCK_SH（不挡我方只读探针），LOCK_EX 先挡死自己开工闸。
- 契约升级时测试里所有手写 status 的注入子进程要同步升级（inline JSON 会漏）。
- 全量收据必须对应 clean tree commit；「补一行」承诺先验派生窗口历史。
