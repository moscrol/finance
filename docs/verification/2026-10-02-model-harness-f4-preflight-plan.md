# R-20261002-16：四格接线预检（零模型）

目标是回到 harness 对不同模型的实际帮助/约束，不按模型档位分配语义解释权。本轮只打通量具与完整入口，不能认领质量收益。

- 私有计划先于实现冻结：`~/.finance-runtime/model-harness-f4-preflight-20261002/plan.json`；模型物理请求帽 **0**。
- 产品基线 origin/main `3a2718c6c7db`；独立评测分支只前移到依赖 PR18 `a57eaf678`，复用已验外层预算监督，不合 main、不部署。
- 已知：旧 Python3.12 缓存曾通过 D9 基线与四项变异；D1 六项数值真值及阶段与只读快照一致。这不是盲预测。
- 不重写评分规则：仅接受缓存 SHA256 `195ad5598432e64f9be8a0a60025f8a14d7e2df5b246ecdd2f82c9a21366ac88`、magic `cb0d0d0a`。一次读取的相同字节执行，不导入原空源码、不跑旧批量 runner。不提交私有 pyc/题面/答案；明确 source_restored=false。
- 负测：错 hash、解释器/缓存 magic、非代码、无 callable、异常及坏返回不得变成分数；不得触发旧 __main__；advisory/分数原样保留；输入真值隔离。
- 完整入口必须走 POST /api/conversations → /messages，配置独立用户/队列/episode/部署账本及冻结数据。禁止核心 Episode 替代。断网拦截只证明入口/身份绑定，不是完成任务或 F4。
- 复用现有 eval-only thin/admission 时留来源 revision/hash，不复制未合入的生产优化。
- 边界：共享 httpx 与 lock 漂移仍在、代码地图 unavailable，不能宣称 clean-lock E2E；机器尺不是完整来源/语义判断，不能替代完整答案审查。
- 真实四格另登记：GLM 两候选同 endpoint，不称已标定强弱；串行至少90秒启动间隔、绝对截止/物理帽、父子身份与原始HTTP留证；先四格一题，不开240。旧R14不重开，累计真实模型仍100。
