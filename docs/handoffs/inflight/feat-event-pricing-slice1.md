# feat/event-pricing-slice1

树 `/Users/a77/fwp-wt-event-pricing`，PR #663，**待用户确认合并**。
3 个提交 + 1 个前向合并，20 文件 / +5108。

## 做了什么

事件定价第一刀：**事件锚点日历**（编辑日历 + 官方日程合成，每类事件一个确定性反应日，
能答「站在 T 日已知最新一期是哪期 / 尚未发布」）→ **`EventReaction`**（锚点日前 m /
当日 / 后 k，指数与板块两层，形状标签对非事件日基准过四态统计门；`anchor_windows`
第二实例）→ **「已定价」三代理并排**（事前超额、拥挤度分位、舆论认同度阶段），
**刻意不合成一个数**。第三个源是 `026d8c47`：ev 直接消费知识库卖方观点事件文件
（narrative 等级，板块锚点两类）。

## 读数是双面的，别只报一半

`docs/superpowers/specs/2026-09-07-event-pricing-slice1-calendar-reaction-design.md:150`
[实测 2026-09-08，硬证据类 n=217，基准 N=15,993]：

- 事前 5 日板块超额中位 **+3.34%、74% 为正**——卖方硬证据多在板块已经动了之后写
- `continuation_up` 54/217 = **25%**（基准 8.9%）**supported**
- `pre_up_post_down` 21/217 = **9.7%**（基准 5.4%）**同样 supported**
- `flat` 12%（基准 29%）refuted、`pre_down_post_up` 1.4%（基准 5.1%）refuted
- 事后 5 日超额中位 +1.45%、65% 为正；**拥挤度分位中位 82–94**
- 首提类 n=25 无一形状过门（N 决定，不是无效应）

原文读法：**卖方硬证据落在已启动、已拥挤的板块上，之后延续多于反转，但「事前涨→事后跌」
也比基准厚——两头都比常态厚，中间的「没反应」少。** 只报 25% 那半会读成单纯正向信号。

## 本轮（接手方）做的

原分支落后 `gitea/main` **187 个提交**，`--base-drift-max 5` 会判需重跑。
**前向合并而非 rebase**（`block-dangerous-git.sh:45` 拦强推，rebase 推不上去）。

- 合并 `gitea/main@f90af450` → `4447f1f3`，**零冲突**
- ruff 全绿
- 全量 **8335 passed / 0 failed / 77 skipped / 1 xfailed**（537.93s）
  收据 `~/.finance-runtime/test-receipts/20260908T165950Z-4447f1f3.json`，`dirty=false`
- 基座漂移手算 **0**；已 push gitea

⚠ 验收据别读 `latest.json`——当晚多棵树并发跑 pytest，它被别的脏树收据覆盖过。按 revision 取。

## 未做

- 未合 main（等用户确认）。未碰 webapp / `skills.registry.json`。
- 指数层 20 日窗不进 v0（`history_outcomes` 只有 3/5/7/10，扩 horizons 会改共享表版本，§9 拍板）。
