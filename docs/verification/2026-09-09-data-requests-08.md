# 验收收据 · 08 问题驱动补数（隔离链）· 2026-09-09

分支 `feat/demand-driven-data-requests`（底 `gitea/main@5eb24515`），树 `~/fwp-wt-demand-driven-data`。
**全部写入都在隔离 staging 库**（`~/.finance-runtime/data-requests-08/*.duckdb`，生产库整文件拷贝），生产库一个字节未动；
生产回填仍归 daily-full 维护者（工单 #33）。四项状态见文末。

## 1. 断点与接法（任务 0 → 实现）

| 环节 | 之前 | 现在 |
|---|---|---|
| 回答里的数据缺口 | 只在给模型的 observation 里一句「没有结构化结果」，无机器痕迹 | `tool_hunger.jsonl` 多一类 `window_uncovered`（dataset / 物理表 / 请求窗 / 实际覆盖 / 行数 / 未覆盖侧），观测型，observation 逐字节不变（接缝测锁定） |
| 结构化请求 | 无 | `data-requests build`：同 dataset 窗口重叠合并、消费者（run / 用户 / 原问题 / 会话）并集、路线表（已有 writer 才叫可补）、优先级按消费者数 + 新鲜度 |
| 补齐 | 手工 | `data-requests fill`：隔离库上按依赖顺序调现有 writer；指向生产库拒绝；fupanhui 家族 / OPT-03 占位只显示真正缺什么 |
| 完成信号 | 无 | `data-requests check`：交易日历（`fact_stock_daily`）× 关键字段非空 × 日期/来源合理性 → `satisfied` 才给 `data_version`，并逐项报告依赖 |
| 恢复研究 | 用户重问 | `data-requests resume`：沿 Workbench 原会话重问原问题；`(request_id, data_version, consumer_run_id)` 只恢复一次 |

## 2. 反向验证（排练库 `rehearsal.duckdb`，真 writer、真 akshare）[实测 14:55–15:00]

| 步 | 动作 | 检查结果 | 说明 |
|---|---|---|---|
| 0 | 补前 | `market_daily` open「窗口内无行」；`sw_l1_daily` open | 基线 |
| 1 | fill `market_daily`（index-daily 19 行 + overview-local 19 日，27.8 s） | **partial**「有行但关键字段值空：industry_1」；依赖 `{stock_daily: satisfied, sw_l1_daily: open}` | 有行不等于补齐；依赖没满足就不放行 |
| 2 | fill `sw_l1_daily` **不关实时步**（41.2 s，589 行） | **invalid**「31 行历史日被实时源覆写」：`2024-06-28 source=akshare:index_realtime_sw:8017xx` | writer 缺 historical 模式（blocked/08.md B2），检查器抓到真实缺陷 |
| 3 | fill `sw_l1_daily` 关实时步（38.8 s） | **satisfied** 19/19，`pct_chg` 非空 1.0 | 06-28 被 hist 值覆盖回来 |
| 4 | 再 fill `market_daily`（62.0 s） | **satisfied** 19/19，`sh_index_close / total_amount / limit_up / industry_1` 均 1.0；依赖全 satisfied；`data_version=4c71ef2190ca` | 同一请求重复 check 版本不变（单测锁定），数据一改版本即变 |

单测另覆盖：部分回填（缺日）、全 NULL、来源失败（库不可读）、日历未知、重复完成信号（`completed` 只落一次）、重放（第二次 `resume` 0 动作、不打 Workbench）、dry-run 无副作用、原会话 404 时新开会话、拒绝生产库。

## 3. 真实对话入口（隔离实例 :8808）

（待网关冷却结束后回填：四问补前基线 → 请求 → 补齐 → 恢复 → 差量 → 重放。）

## 4. 四项状态

| 项 | 状态 |
|---|---|
| 已实现 | ✅ 事件 / 请求 / 检查 / 隔离补齐 / 完成回执 / 恢复 / CLI / 日产物兄弟件（`{date}-data-requests.json`） |
| 已进默认入口 | ✅ 接缝在生产装配的 `finance_query` runner 上（`build_episode_registry`），任何 Workbench / CLI 对话走到该工具都会留痕；`resume` 走 Workbench 消息接口 |
| 真实验收 | ⏳ 见第 3 节 |
| 生产生效 | ❌ 未合 main、8792 未切流、生产库未回补（按单：只完成隔离验收） |
