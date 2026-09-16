# E2 D1/P1 六类反例修复与质检阻塞

2026-09-14；代码1a7363c4，fix/e2-boundary-closeout，树 `/Users/a77/fwp-wt-e2-boundary-closeout`，基于gitea/main=1fef3d27。未合/未推/未部署。

## 背景与决定

旧实现8bd55b26的独立报告六类反例未过。按限定路径移植旧P1、v10设计和测试到最新main基点，而非整体合入作者旧树/旧交接；独立脚本逐字保留为scripts/e2_boundary_review_probe.py，不改原题和判据求绿。

修复顺序：引用/围栏屏障→长文候选先复核→题组续行保真→同句A/B状态分离。外层闭合引用保护其内部引号，避免吞外部禁令；识别掩码与原文分开，段落和题文仍看原文；复核失败块不能被后扫认作确认指令；长题续行不另起长文抢走限定。

| 选择 | 否决 | 为什么 |
|---|---|---|
| 长材料先复核再认题组 | 先见编号就认题 | 研报内部编号不是用户问题，不能借题组绕过歧义 |
| 掩码仅用于识别，原文保留 | 用掩码空行裁题 | 全引用续行仍是题文，不能丢限定 |
| 沿用原独立46针并加相邻组合 | 修改评分/删除失败针 | 要证明修反例，不是修验收尺 |
| P1独立通过才能P2 | 作者定向绿后直接接线 | 局部分类器与全链权限/跨轮合同是不同结论 |

## 验证

原探针29/46→46/46。固定干净提交1a7363c4上六文件定向234 passed /4 skipped /1 xfailed，原收据 `~/.finance-runtime/test-receipts/20260914T082049Z-1a7363c4.json`。4skip是同类引号参数组合不适用，同类嵌套另测；没有隐藏已知反例。全仓Ruff/提交钩子/diff绿；不宣称全仓pytest或真实材料题PK完成。

本树 `docs/verification/e2-boundary-closeout/` 归档原探针JSON、最终测试日志和第三/四次QC阻塞报告。测试代码 `intelligence/tests/test_e2_boundary_closeout.py` 与原脚本是可复跑产物，不仅/tmp聊天结论。

## 独立QC现状

独立树 `/Users/a77/fwp-wt-e2-closeout-qc` 固定1a7363c4。前两次连接/并发失败；第三次模型连通但命令宿主 `/Users/a77/.local/bin/codex-code-mode-host` 缺失，未读取代码/运行测试；第四次仅本次关闭code_mode_host开关也无可用命令入口，明确未完成。没有有效findings与放行结论，不能把环境受阻当作“零缺陷”。没有修改全局配置/权限或安装宿主。

提示 `/tmp/e2-closeout-qc-prompt.txt`，日志 `/tmp/e2-closeout-qc-{process,retry,third,fourth}.txt`。第四次结果 `/tmp/e2-closeout-qc-fourth-result.md`；报告已归档。独立树未改应用代码。

## 下一步与不能做的事

恢复一个可实际执行命令的独立审查入口（不关闭安全边界），复核1a7363c4六类和相邻组合；通过才进P2–P7。split_user_message仍为旧抽取逻辑，只附加regions；真实入口吞题、工具权限、逐题交付、跨轮继承、纯度检查尚不能称修复。

依v10继续；最后全新会话原始T2→T3，T3不重贴禁令；之后冻结版本/主备模型、真实金融推理可用性，才做Knevo配对与迁移题。与6c7bea6e材料账本、413b7a07降级留痕有重叠，集成时声明接替，不另开平行完成链。RE06后台计时在另一树fix/re06-visibility-timing@a4ace074部分工程已验，未反向混进本修复。

本轮未改harness-reference脏树；引用边界风险已沉淀为可复跑探针，不新建第二套能力清单。
