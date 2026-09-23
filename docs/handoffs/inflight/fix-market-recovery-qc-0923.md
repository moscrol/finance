# 行情恢复 QC 续验

## 这个分支做什么
修复#871/#861与查询截止，整体HOLD；本轮新增代码，不再沿用旧完整绿。

## 决策与被否方案
| 选了什么 | 否了什么 / 理由 |
| --- | --- |
| 整行hash与日期并集 | 不追加字符串字段/NULL哨兵，防漏列和新增日期 |
| 资源准入不足即BLOCKED | 不降门槛、不杀他人任务、不删失败证据 |
| 原报告旁注、新原件可逆封套 | 不修改reviewer字节或裁旧空白凑绿 |
展开：`docs/handoffs/2026-09-23-market-recovery-acceptance.md`。

## 当前状态
代码已提交0d3f562cb；固定合流6b43ac82a059，base3bb81b9638f9，tree94cfa97e84e。新候选396P/Ruff/注册表五项过；完整门禁等待604.6秒资源不足，Python与前端均未启动。独审F3为PASS_WITH_LIMITS，旧1de全量绿不移签。未push/合入/部署/生产恢复或换库。证据入口`docs/verification/2026-09-23-market-recovery-acceptance/README.md`，118原件/116封套。旧归档未动，完整差异空白仍exit2。

## 未验证 / 已知边界
F1完整夜跑至成功发布；F2默认daily坏数据/其他字段/并发源变化；F3完整build输入新鲜度、任意并发；FQ真实DuckDB中断与阻塞IO抢占。旧独审不重签；新F3仅apply侧3探针，手工计划不能称真实build。main业务决策已存在，不等于本会话生产授权。

## 下一步
协调磁盘及并发后新目录重跑完整门禁；先核最终候选/基座，勿改此轮收据。原件根`~/.finance-runtime/reviews/market-recovery-qc-20260923/acceptance-followup/`；两detached树/ref保留。控制器已退出，不会自动重试。补合同边界与旧归档格式裁决后再谈合入。

## 踩过的坑
`--require-full-scope`只拒-k/ignore等过滤，不要求仓根目标；396P始终定向。独审旧模板main漂移句与手工build过述均另附勘误。worktree不隔离资源，原件不可为格式绿裁剪。

## 已验证
旧代码新反例11F/7P；新候选14文件396P。作者实际CLI临时库/写前DML观察/部分写入四表回滚/真实build变旧/一组双连接竞争/非空迟到fetch通过。GLM4请求全200，独立3P、作者46P另账、阳性对照1F检出；原探针旧桥模块1F/2P不增独立分母。68审查文件凭证精确值扫描0；封套解码与原件逐字节一致。
