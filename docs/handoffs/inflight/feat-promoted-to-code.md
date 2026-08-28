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
- 未对 8792 跑 live ask 确认注入字数为 0（生产 `FORESIGHT_USERS_DIR` 本来就没有 experience_cards.jsonl）
- 未跑向导、未改 `start-finance-workbench`、未 kickstart
- 未压 `ask_synthesis` 第二条 load 路径的 live 题（单测覆盖 `load_cards`）
- 图谱 `::load_cards` 被 agent-memory auto-sync 收进 `179f92c9`，无独立 commit message

## 下一步
1. 你确认后：`bash scripts/hosted-alpha-wizard.sh` → 改启动器 source alpha.env → kickstart → runbook §3
2. 合入等你点头。勿强推、勿合 main。
3. 可选：把 4/6/7 三条纠偏固化进代码后再归档。

## 踩过的坑
- 8792 身份在 `FORESIGHT_USERS_DIR`，和仓内 `intelligence/users/` 不是同一份脑。标仓内卡不影响 8792 注入（那边本来就没卡文件）。
- 现成 cloudflared 是 `a77-exec` 服务别的主机名。不要 `tunnel create` 第二条。

## 已验证
`pytest` 经验卡+召回+auth+quota 50 绿；`graph_audit` 43 行/49 条 OK；`bash -n` 向导；真实 jsonl `load_cards(..., window=0)` 返回 0。

## 工具沉淀盘点
向导进 `scripts/hosted-alpha-wizard.sh`（换项目也会有「边缘认证要真人点控制台」）。`promoted_to_code` 是本仓记忆生命周期，不进 TOOLKIT。
