# 四周总结模板（对应 `PilotSummary`）

由 `summarize` 生成 `pilot-summary.json/.md` 后，执行人按本模板写一页人读总结。数字只从总结文件抄，不另算。

## 1. 三个状态（分开写，互不代签）

| 状态 | 值 | 含义 |
|---|---|---|
| `engineering_status` | engineering_complete / no_input / input_error | 管线能不能算 |
| `field_status` | pending / collecting / observed / inconclusive | 有没有真人读数；observed ≠ 效果成立 |
| `commercial_status` | unstarted / observed | 有没有凭据核验的真实付款 |

## 2. 判据结果（`criteria_results`）

| 判据 | 结论 | 原因 | 未知类型 | 分母 |
|---|---|---|---|---|
| completion_quality | pass / fail / unknown | … | sample / gap | 全部已分配任务 |
| time_saving | … | … | … | ≥3 人 · ≥6 完整配对 · 两类任务 |
| proactive_reuse | … | … | … | 激活后进入完整观察周者 ≥3 |
| recheck | observed_only / unknown | 只展示比率 | | 到期且可访问的判断 |
| cost | observed_only / unknown | 已知 / 估算 / 未知并列 | | 全部任务 / 重试 / 帮助 |
| renewal | observed_only / unknown | | unstarted | 真实首付后进入续费窗口者 |

建议（`recommendation`）：`continue_validation` 只表示省时 / 质量 / 主动复用三项达标，建议继续验证；`pause_recruitment` 表示质量红，暂停扩招；`keep_observing` 表示缺测继续观察。

## 3. 读数（`metrics`）

每项写：值（或 null + 原因）、分子 / 分母 ID 数、排除（规则与版本）、未知项、覆盖率。省时同时写全部分配任务的超时 / 未完成率；成本写已知 / 估算 / 未知 / 人工工时四栏。

## 4. 限制项（`limitations`）与偏差

漏审、缺同意、缺到期清单、非盲审、仿真输入、多份收据等逐条列出。

## 5. 探索性观察（不进判据）

访谈里的解释、未见案例的迁移、团队访谈的需求证据等级。

## 6. 下一步

按判据结果写：继续验证 / 暂停扩招 / 补记录。四周未到续费期就写「续费待测」。
