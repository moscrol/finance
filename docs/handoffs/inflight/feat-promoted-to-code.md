# feat/promoted-to-code

## 这个分支做什么
经验卡 `promoted_to_code` 退役注入；Alpha 人工步骤收成向导。不合 main。

## 决策与被否方案
- 选 `load_cards` 单点跳过 / 否 select 层再滤一层 / 唯一注入口，散滤会漂
- 选 `promotion=` 改档 / 否 `invalidated` / 这些卡是对的，不是假教训
- 13 张全标 / 否留下飞凯 candidate / 原则已在管线；个股数字不当事实引用
- 纠偏只归档 1/2/3/5 / 否 7 条全归档 / 4 澄清≠证伪、6 相对日期、7 结构化腔代码里还没有
- Alpha 只交向导 / 否现在翻 8792 `cf_access` / 缺 AUD 会 fail-closed 把自用挂掉

## 当前状态
已提交 `b61664d7`。用户 jsonl（gitignore）已改：13 卡 `promoted_to_code`；纠偏 1/2/3/5 两边 `memory_status` 归档。8792 **未**切本枝、**未**开 auth。实验台账/探针未提交。

## 未验证 / 已知边界
- 合入门红：`merge-tree gitea/main` 撞 `prediction-ledger.md` 头行（基座 `e4276e00` 不在主干）。产品 diff 正交，rebase 后再合。
- 定向测收据 dirty（41 条他人足迹），未在干净 worktree 复跑。
- 未对 8792 跑 live ask；未跑向导 / 未改启动器 / 未 kickstart。
- vault `.foresight` 那份卡未同步毕业（当前生产 env 不指那里）。

## 下一步
1. 你确认后：`bash scripts/hosted-alpha-wizard.sh` → 改启动器 source alpha.env → kickstart → runbook §3
2. 合入等你点头。勿强推、勿合 main。
3. 可选：把 4/6/7 三条纠偏固化进代码后再归档。

## 踩过的坑
- 8792 身份在 `FORESIGHT_USERS_DIR`，和仓内 `intelligence/users/` 不是同一份脑。标仓内卡不影响 8792 注入（那边本来就没卡文件）。
- 现成 cloudflared 是 `a77-exec` 服务别的主机名。不要 `tunnel create` 第二条。

## 已验证
定向 pytest **62P**（执行方写 50）；`graph_audit` 43/49；`bash -n` 向导；仓内 `load_cards(..., window=0)` = 0。检阅批注见日期快照。

## 工具沉淀盘点
向导进 `scripts/hosted-alpha-wizard.sh`（换项目也会有「边缘认证要真人点控制台」）。`promoted_to_code` 是本仓记忆生命周期，不进 TOOLKIT。
