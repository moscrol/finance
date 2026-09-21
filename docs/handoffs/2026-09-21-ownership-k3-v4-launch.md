# 归属三单 v4：K3 不限用量复审启动

## 背景与授权变化

#812 看板、#813 回填、#814 收据归属修复已真实合流到冻结候选 `6eb12c1b8a41071fd4af8bee343950fe0b85b221`，基线 `c615adbd2f861e23f2c8d03631833f98b3ae5aba`，Git tree `e99dad14cb946a112d92537289854d914e558936`。该对象作者工程全叶通过，详情见 `2026-09-21-ownership-integration-v4.md`；这不替代独立终审，也不签后来 main。

用户先“启动”同意两轴 K3 复审，随后明确纠正：“不用给k3设置预算，随便用”。以最新指示为准，取消原拟每轴 20 分钟/40 请求及总 80 请求、强制探索截止点；订阅通道与业务权限边界不扩大。纠正已通过 `record-correction` 记入用户空间，不写入冻结的仓内用户存档。

## 已完成动作（按顺序）

1. 独占新根 `~/.finance-runtime/reviews/ownership-k3-v4-20260921/`，旧 v3 及七档已封证据不改。
2. 新建只读任务约束下的 detached reviewer checkout：`~/fwp-wt-ownership-spec-v4-0921`、`~/fwp-wt-ownership-quality-v4-0921`，均净且为精确候选；没有换基线或移动作者树。
3. 新授权、源身份、输入差异、历史 backfill 契约、公共约束和两轴 prompt 写入新根。契约明确同进程重入、顺序调用配置失败清理、输出路径归属及独立 board/backfill 探针，不读取另一轴结论。
4. 执行器实际去掉请求/时间 watchdog，`process.wait()` 不设总超时，reservation/authorization 的 limits 为 null。保留 once-only session 预占，禁止自动重试、另开代理、切换付费通道或购买。
5. 订阅鉴权改为内存缓存、临近过期通过既有 resolver 更新；用量不限不意味着凭证永不过期。更新失败即停，不记录 token，不复制凭证到 argv/env/auth 文件。相同本地 `mirasim-kimi/kimi-k3` route；配置零价不能当真实账单。
6. 工具封装保留单命令防卡死超时、完整合并 stdout/stderr 与 shell exit。直接文件工具约束根目录；shell 的读写/联网红线仍是任务约束，**没有 OS 沙箱**。`finish_review` 校验最终报告的结构/身份并结束，不替代人工/机械证据核验。
7. 离线设施检查最终 **19/19 通过**，含模拟 121 次请求且已过 2000 秒仍能准入。安装版 Pi 的离线 stub smoke 通过；它没有真实模型请求，不计为独立审查。
8. **2026-09-21T08:07:40Z 两轴已实际启动**。Spec runner/Pi PID `53701/53716`，Quality `53702/53717`。首次回读均 Plus READY、真实请求已准入、stderr 为空；08:08:51Z 四进程仍在。此快照仅记启动，不声称审查完成。

## 选型与被否方案

| 方案 | 评价/理由 | 结果 |
|---|---|---|
| 只改 prompt，执行器仍保留40/1200 | 会继续静默触帽，违背最新授权 | 否 |
| 删除审计、路径和生产权限限制 | “随便用”只改变 K3 用量，不授权副作用 | 否 |
| 保留强制第28轮/15分钟收尾 | 仍是用量驱动而非覆盖驱动的截止 | 否 |
| 无总用量限制，按覆盖/真实阻塞结束 | 正式报告仍必需，未覆盖明确标注 | 选 |
| 永远缓存启动时 token | 过期会形成伪总时限 | 否 |
| 内存缓存+既有订阅临期刷新 | 不暴露明文；失败停止，不换路由 | 选 |
| 不限额等同重跑全部全仓工程测试 | 已有固定对象工程证据，独立审应集中反例 | 否 |

## 原件与设施错误

新根的 `authorization.json`、`inputs/source-provenance.json`、`run_k3.py`、`launch.py`、`credential-bootstrap.mjs`、`review-tools.mjs`、两轴 prompt/config 是实际执行件。`{spec,quality}-launch.json` / `*-reservation.json` 记录 once-only 预占；各轴 `execution.json`、`events.jsonl`、`request-admissions.jsonl`、`shell-records/` 持续产出。

`apparatus-notes.md` 记两处离线错误：文档示例的 `openAICompletionsApi` 顶层导出在本地安装版不存在，修成实际 lazy API 路径；shell 非零 exit 会 throw，初始测试错当返回值，改断言。初版脚本和两次红日志均保留。Ruff 检查准备器/runner 通过。设施测试不是候选产品测试。

## 接下来与明确边界

先读每轴 execution/admissions/events 尾状态和 PID，**不要重跑 launch.py 或 run_k3.py**。不限额无需再为旧40/20限制申请；真正凭证/服务/环境阻塞须如实记录。审查最终完成后核对报告身份、源树未变、真实 exit、反例因果、覆盖分母；模型原件不改，operator QC 另写，再单独封档/发布。

当前没有新的独立 PASS/CHANGES_REQUIRED。later-main 合流、真实完整副本302132父子发布恢复演练、合并、部署、生产回填、真实工作树删除、Arena 均未授权/未完成。两轴同模型/共同输入，不能称全盲实验。单命令超时不是整场用量预算；首尾净不能证明中途无改后还原。

工具沉淀：这一轮脚本是显式单次 review artifact，不是常驻调度服务；真实运行和 QC 后再决定通用复用，当前不对共享 harness/全局配置做新写入。
