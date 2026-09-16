# docs/fengyuan-distill-0916

## 这个分支做什么
把风远94 对账台账（`docs/learning/knevo-distill/fengyuan94-corpus-dedup-2026-09-16.md` §5）判为「新增」的卡
走 `perspective-distill` 闭环进 `fengyuan` 画像。画像、原料、卡片、patch 全在 gitignore 的用户空间；
进 git 的只有本交接、`evolution/backtest-queue.md` Q-002 #12–#23、skill 第 0 步过期段修正。

## 当前状态（2026-09-16 18:00，A 侧「新增」两批 + B 侧一批均已收口）
- **优先 8 卡**（`pa-516facf90296`）：4 批（R61 一致预期锚 / R12 纸面产能 / R65 比率口径 / R28 数据现查通用句）、
  1 拒（R35 数字未剥离，剥离版在 review-policy 待手编）、3 pending（R27/R29/R30，报表边界）。
- **第二批 14 卡**（`pa-e0178691c647`，15 候选全核验）：9 批（R15 Token成本定估值 / R16 缺料利好有渠道下游 /
  R18 铲子股三乘数 / R19 利润分配结构 / R26 风险侧扩产收窗 / R41 追第一波=接盘 / R43 一天共振=假共振 /
  R57 出清节奏定补跌窗口 / R62 二元事件做EV不做等）、4 拒（R13 与 R26 机会侧数字未剥离→剥离版待手编；
  R50 卡自标「刚提出待验证」成熟度不过；证据分级句与已有条目同义）、2 pending（R59/R60，技术面边界，
  台账 §5 预设；推荐采纳+剥数）。R38 未产出候选（事件性强，事实层已在 q17 文档）。
- **B 侧第三批 11 条**（`pa-403ebdafaf79`，date 2026-08-08，17 候选全核验）：11 批（类比同构 / 集体转向 /
  格局vs切换判别 / 五硬条件 / 底部双条件两半 / 恐慌业绩校准两半 / 尾盘三段式 / 三情景估值 / 系统性危机弃格局）、
  6 拒（B3 两半、B8 两条、B10 五维、B14——数字未剥离或与 Q-002 #6 重复；剥离版 4 句在 review-policy-batch3
  待手编）。Q-002 追加 #20–#23。
- 三批合计：24 批 / 11 拒 / 5 pending。approved 累计 94 条，全部 agent 起草待用户复核（known_gaps 已标）。
- 每批评审后考卷重跑均 3/3（边题「核报表质量」始终弃权）；8792（gitea/main=0758a423）可见 fengyuan 23 篇。
- 抽取经 `~/.local/bin/start-finance-workbench-glm-canary` 的智谱直连（glm-5.2）完成——8080 网关上游
  （Mirasim 账号组）自 14:50 起全 503，用户在会话中指路用 GLM。评审判据与结果：job 目录
  `~/.local/share/finance-workbench/private-distillation/fengyuan-20260916/review-policy{,-batch2}.md`。

## 下一步
1. 用户裁决五条 pending：报表边界（R27/R29/R30，推荐采纳+把边界第 1 条收窄为「报表只作涨价/订单兑现的验证
   信号」）；技术面边界（R59/R60，推荐采纳，R59 需先剥 ≥20日 数字）。三句剥离版手编句在两份 review-policy 里。
2. 复核 13 条已批；不认可的直接说，agent 撤（编辑 JSON 删条目 + patch_history 记 revert）。
3. 剩余语料：A 侧「部分」22 卡（台账 §5 各有建议动作，多为并入或改写已有条目=人工编辑域，逐张先看动作）。B 侧已完成。
4. Q-002 #12–#23 的标定各有数据源前提（#13/#14 依赖报表边界裁决；#16/#17 数据不在本仓；#19 依赖 R59 裁决）。

## 踩过的坑
- 用户空间与 user 真值都在启动器现查（本次 `FORESIGHT_USERS_DIR=~/.local/share/finance-workbench/users`、
  `FORESIGHT_USER=linxiaoqi5111`）；skill 第 0 步已改为现查。
- 启动器 `PYTHONPATH` 指向 runtime 树，整份 eval 会加载别的代码；只 eval 需要的 export。
- 网关探活只信 `chat/completions` 里的 `choices`；`/health`、`/v1/models` 全程是绿的。
- glm-5.2 小 `max_tokens` 会被思考吃空：max_tokens=5 返回空 content 不是坏，探针给 ~200。

## 未验证
- 生产 Workbench 单视角 smoke 未跑（Workbench 自身模型走 8080 网关，网关未恢复）。
- 13 批 + 5 pending 的最终认定权在用户。
