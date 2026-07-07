# 2026-07-05 Launch Batch（首批产品介绍内容）

- brief：`docs/marketing/content-briefs/2026-07-05-launch-batch.yaml`
- 状态：待人工审核，未发布
- 定位：产品介绍为主线；本批教学向内容 2/15（13%，≤20% 达标）

---

## 一、短帖（10 条）

### SP-01 · FinHot 是什么（feature_showcase）
- persona：主观交易者 / 财经内容创作者
- hook：你刷金融消息要开几个 App？我只开一个。
- 正文：FinHot 把财经 RSS、微博、雪球、微信、X 聚合成一条信息流，每条自动 AI 摘要、外文中译、质量打分。高信号内容自己浮上来，噪音沉下去。本地桌面应用，数据存自己电脑。
- CTA：想看完整 demo 的评论区扣 1。
- claim_ids：[claim-finhot-one-feed, claim-finhot-local-first]
- 风险提示：无收益表达；通过。

### SP-02 · 官方披露查新（feature_showcase）
- persona：主观交易者
- hook：一个金融阅读器如果不能查源头证据，就只能帮你更快刷噪音。
- 正文：FinHot 内置官方披露查新：按公司或关键词直接查公告、互动易、问询函，并按重要度 P0-P3 分级。看到题材先看源头，再看热闹。
- CTA：你现在查公告用什么工具？评论区聊聊。
- claim_ids：[claim-finhot-source-evidence]
- 风险提示：review_required=true，发布前人工确认"分级"表述不被理解为投资评级。

### SP-03 · 每日复盘（feature_showcase）
- persona：主观交易者
- hook：收盘后你复盘要一小时？我的 Agent 十分钟跑完。
- 正文：金融 Agent 的每日复盘一次生成：市场强弱、板块信号、涨停连板、新高、策略矩阵。全部结构化、带数据出处，第二天还能回头验证昨天的判断。
- CTA：想看一份真实复盘输出样例，关注下一条。
- claim_ids：[claim-finance-daily-review]
- 风险提示：不得改写为"跟着复盘操作"；通过。

### SP-04 · Theme Radar（feature_showcase）
- persona：主观交易者 / 财经内容创作者
- hook：新题材出来，别人在群里问"龙头是谁"，我先看产业链和证据。
- 正文：给金融 Agent 输入一个新题材，Theme Radar 输出：题材定义、产业链拆解、公司分层、证据强度、信号缺口。一张图看清题材结构，缺口在哪一目了然。
- CTA：留一个你最近关注的题材，下期用它做 demo。
- claim_ids：[claim-finance-theme-radar]
- 风险提示：不得暗示"分层=买入名单"；发布前人工复核。

### SP-05 · 证据驱动定位（use_case_story）
- persona：主观交易者
- hook：我不想让 AI 告诉我买什么，我想让它告诉我为什么这个判断可能错。
- 正文：金融 Agent 的定位是研究员，不是操盘手。它把每个判断拆成证据、反证和验证路径：证据从哪来、什么情况下会被证伪、盘后怎么验证。结论可复盘、可追溯。
- CTA：认同这个定位的点个赞，产品细节陆续发。
- claim_ids：[claim-evidence-first-research]
- 风险提示：明确"不荐股"边界；通过。

### SP-06 · 组合工作流（use_case_story）
- persona：主观交易者
- hook：从看到一条消息，到搞清一个题材，我的完整流程只有两步。
- 正文：第一步 FinHot：信息流里发现线索，顺手查官方披露确认不是空穴来风。第二步金融 Agent：Theme Radar 拆产业链、分层公司、看证据强度。信息发现到题材验证，一条链走完。
- CTA：想看这条链的完整视频 demo？点关注。
- claim_ids：[claim-combo-workflow]
- 风险提示：无收益表达；通过。

### SP-07 · 创作者场景（use_case_story）
- persona：财经内容创作者
- hook：财经创作者最大的成本不是写，是消化。
- 正文：我用 FinHot 一条流看全所有选题来源，AI 摘要先帮我过滤；确定选题后，金融 Agent 的题材拆解直接变成内容大纲——产业链、公司分层、证据来源都是现成的素材。
- CTA：做财经内容的朋友，评论区聊聊你的选题流程。
- claim_ids：[claim-finhot-one-feed, claim-finance-theme-radar]
- 风险提示：无收益表达；通过。

### SP-08 · 本地优先（feature_showcase）
- persona：AI 工具爱好者
- hook：订阅制信息工具最大的问题：你的阅读数据不是你的。
- 正文：FinHot 是本地优先的桌面应用：数据存本地 SQLite，AI 能力 BYOK（自带 API key）。不锁订阅、不上传数据，自己的阅读历史和打分模型自己掌控。
- CTA：本地优先党举个手。
- claim_ids：[claim-finhot-local-first]
- 风险提示：不得改写为"绝对安全"；通过。

### SP-09 · 复盘可验证（use_case_story）
- persona：主观交易者
- hook：复盘写完就完了？我的每个判断都要过 T+1 验证。
- 正文：金融 Agent 把复盘里的判断登记成 checkpoint，盘后自动对照实际走势验证，偏差回灌到框架里。判断对不对不靠记忆，靠台账。
- CTA：你复盘后会回头验证自己的判断吗？
- claim_ids：[claim-evidence-first-research]
- 风险提示：不得表述为"验证后胜率提升→收益提升"；发布前人工复核。

### SP-10 · 真实 Agent 项目（辅线·教学向）
- persona：AI 工具爱好者
- hook：市面上 Agent demo 很多，跑在真实工作流里的很少。
- 正文：FinHot + 金融 Agent 是一套真实在用的系统：多源信息聚合、知识图谱、证据分层、每日自动复盘。不是玩具 demo，是每天跑的生产工具。后续会拆架构。
- CTA：想看哪部分架构？评论区点菜。
- claim_ids：[claim-combo-workflow]
- 风险提示：对外拆架构时不得泄露私有仓库细节；发布前人工复核。

---

## 二、长文大纲（3 篇）

### LF-01 · FinHot 是什么：本地优先的金融信息流阅读器全景介绍（feature_showcase）
- 渠道：知乎 / 公众号
- 标题候选：
  1. FinHot：我给自己做的金融信息流阅读器
  2. 刷不完的金融消息，让一个本地应用帮你分层
  3. 多源聚合 + AI 打分：一条信息流看全金融市场
  4. 为什么我的金融阅读器要能查公告和问询函
  5. 本地优先 + BYOK：不被订阅绑架的金融阅读工具
- 结构与论点：
  1. 痛点：信息太多不是问题，没法分层才是问题（场景引入）
  2. FinHot 是什么：一句话定位 + 主界面截图【截图：timeline】
  3. 多源聚合：RSS/微博/雪球/微信/X/watchlist【截图：源管理】
  4. AI 增强：摘要、中译、质量打分【截图：entry 详情】
  5. 官方披露查新：公告/互动易/问询函 + P0-P3 分级【截图：disclosure 结果】
  6. 本地优先：SQLite + 桌面应用 + BYOK
  7. 边界声明：它不预测股价、不荐股
  8. CTA：关注后续版本更新
- claim_ids：[claim-finhot-one-feed, claim-finhot-source-evidence, claim-finhot-local-first]
- 素材来源：finhot README「它是什么」、产品截图

### LF-02 · 金融 Agent 是什么：A 股主题研究工作台的四个核心能力（feature_showcase）
- 渠道：知乎 / 公众号
- 标题候选：
  1. 我做了一个不荐股的金融 Agent
  2. 金融 Agent 的四个核心能力：复盘、雷达、图谱、框架
  3. 把主题研究做成流水线：一个 A 股情报工作台的产品介绍
  4. 每个判断都带出处：证据驱动的市场研究工作台
  5. 从盘面到证据：金融 Agent 完整能力图
- 结构与论点：
  1. 定位：研究员不是操盘手，边界先讲清
  2. 能力一：每日复盘（强弱/板块/涨停/策略矩阵）【截图：复盘输出】
  3. 能力二：Theme Radar（题材拆解一张图）【截图：radar 报告】
  4. 能力三：Evidence Graph（判断逐条可溯源）【截图：证据链】
  5. 能力四：Perspective Lab（自己的框架可复盘可证伪）【截图：框架解读】
  6. 这四个能力如何串成一个日常工作流
  7. 边界与免责：不承诺收益、不给买卖指令
  8. CTA：关注产品建设进展
- claim_ids：[claim-finance-daily-review, claim-finance-theme-radar, claim-evidence-first-research]
- 素材来源：productization-roadmap 产品闭环章节、perspective-lab spec

### LF-03 · 从一条消息到一个题材结论：FinHot + 金融 Agent 组合使用实录（use_case_story）
- 渠道：知乎 / 公众号 / 研究网站
- 标题候选：
  1. 从 FinHot 到 Theme Radar：一条信息如何变成研究线索
  2. 一次完整的题材研究：信息发现 → 源头查证 → 产业链拆解
  3. 我处理一个新题材的完整流程（带工具实录）
  4. 两个工具一条链：金融信息的发现、查证与拆解
  5. 题材研究不靠灵感，靠流程
- 结构与论点：
  1. 起点：FinHot 信息流里的一条高分消息【截图：打分详情】
  2. 第一步查证：disclosure_lookup 查官方披露【截图：披露结果】
  3. 第二步拆解：Theme Radar 输出产业链与公司分层【截图：radar】
  4. 第三步验证：证据强度与信号缺口，哪里还不硬
  5. 终点：一份带出处、可证伪的题材结论（脱敏示例）
  6. 全程没有"买什么"，只有"证据到哪一步"
  7. CTA：想看视频版实录，关注视频号/B 站
- claim_ids：[claim-combo-workflow, claim-finhot-source-evidence, claim-finance-theme-radar]
- 素材来源：真实使用记录（对外需脱敏具体标的与私有路径）

---

## 三、短视频脚本（2 条）

### SV-01 · FinHot 60 秒产品 demo（demo_script）
- 渠道：B 站 / 视频号 / 抖音 / 小红书；目标时长 60s
- 口播稿：
  - [0-8s Hook] 你刷金融消息要开几个 App？我只开这一个。
  - [8-20s] 这是 FinHot：RSS、微博、雪球、微信、X，全部聚合成一条信息流。每条自动摘要、打分，高信号的自己浮上来。
  - [20-35s] 看到一个题材想确认真假？直接查官方披露：公告、互动易、问询函，按重要度分级。先看源头，再看热闹。
  - [35-50s] 所有数据存在本地，桌面应用，AI 用自己的 key。你的阅读数据只属于你。
  - [50-60s CTA] 这是我给自己做的金融阅读器，后续更新会陆续发，关注不迷路。
- 分镜表：Hook 真人出镜/字幕卡 → 录屏 timeline 滚动 → 录屏 entry 摘要+打分 → 录屏 disclosure 查询 → 设置页本地存储/BYOK → 结尾卡
- 录屏清单：timeline 滚动、entry 详情（摘要/打分）、disclosure_lookup 查询与结果、设置页
- 字幕风格：中文硬字幕，关键词高亮
- video-use brief：快节奏产品 demo；结构 Hook→聚合→查证→本地优先→CTA；保留真实操作界面；不出现具体标的买卖建议
- claim_ids：[claim-finhot-one-feed, claim-finhot-source-evidence, claim-finhot-local-first]
- 风险提示：录屏中若出现具体个股，加"仅演示、不构成投资建议"角标。

### SV-02 · 金融 Agent：一次题材研究从盘面到证据（demo_script）
- 渠道：B 站 / 视频号；目标时长 90s
- 口播稿：
  - [0-10s Hook] 新题材出来，别人在问买谁，我先问：证据到哪一步了？
  - [10-30s] 这是我的金融 Agent。每天收盘，它自动生成复盘：市场强弱、板块信号、涨停连板、策略矩阵。
  - [30-55s] 复盘里冒出一个新题材，丢给 Theme Radar：题材定义、产业链、公司分层、证据强度，一张图出来。哪里证据硬、哪里还是传闻，分得清清楚楚。
  - [55-75s] 最关键的是：每个判断都带出处，都能被证伪。盘后自动验证，错了就回灌修正。
  - [75-90s CTA] 它不告诉我买什么，它让我的判断流程可检查。这就是我要的金融 Agent。关注看更多真实使用记录。
- 分镜表：Hook 字幕卡 → 录屏复盘生成 → 录屏 Theme Radar 报告滚动 → 录屏证据链/checkpoint → 结尾定位卡+CTA
- 录屏清单：每日复盘输出、Theme Radar 报告、证据出处展示、checkpoint 验证记录（全部脱敏具体标的）
- 字幕风格：中文硬字幕，"证据/反证/验证"三词高亮
- video-use brief：结构 Hook→复盘→雷达→证据验证→定位 CTA；风险边界：不承诺收益、不出现买卖建议、标的脱敏
- claim_ids：[claim-finance-daily-review, claim-finance-theme-radar, claim-evidence-first-research]
- 风险提示：review_required claims 集中，发布前逐句过 Review Gate。

---

## Review Gate 自查记录

- 事实：15 条内容均绑定 claim_ids，全部 claim 已登记。
- 合规：全文未命中禁用表达清单（收益承诺类、代客操作类、荐股指令类）。
- 隐私：无 .env/token/私有路径；对外发布前录屏与截图需二次脱敏检查。
- 占比：教学向 2/15 ≈ 13%（SP-10、LF-02 第 4 节技术展示部分），≤20% 达标。
- 待人工：SP-02/SP-04/SP-09/SP-10、SV-02 涉及 review_required claim，发布前人工确认。
