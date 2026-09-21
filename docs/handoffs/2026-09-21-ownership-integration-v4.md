# 2026-09-21 · Ownership v4 固定新组合工程门禁

## 背景与本轮权限

#812看板、#813回填、#814收据曾组成旧v3 `47530e20`。旧K3 Spec/Quality各触40请求上限未给终审，操作员确认O-K3-001：同进程内层pytest先写外层唯一收据。随后#814在`a092a021c`以Config调用级归属+PID+cleanup修复并完成作者验证，单分支全量11963P/85S/2X；不是独立复审，也未解决新main合流。

用户再说“继续”，本轮限定为：以授权时最新`gitea/main`冻结三单新组合，跑工程全叶，封存和交接。**未授权追加模型会话/预算、main合入、部署、生产回填、真实worktree删除或Arena接管。** 授权原件：`docs/verification/2026-09-21-ownership-integration-v4/authorization.json`。

## 按发现顺序

1. 核对协调/源树及PR open/unmerged精确头。主检出有他人改动，未拿它验收；来源#813尖是`5994230d`，其中父`--db`拒绝修复来自`49f32259`，不能把代码提交与PR头混称。
2. 授权时main=`c615adbd2f861e23f2c8d03631833f98b3ae5aba`。锁#812 `8d955fc3`、#813 `5994230d`、#814 `ffc8e1a8`。
3. 初版组装器对缺失ref的`show-ref --verify`退出码理解错，任何合并/ref/worktree动作前即停；改为`--quiet`后继续。初版与错误描述保留，不伪造终端原log。
4. 对象库内三次真实`merge-tree --write-tree`均exit0，无冲突、无手改文件；生成四父提交 **`6eb12c1b8a41071fd4af8bee343950fe0b85b221`**，tree=`e99dad14cb946a112d92537289854d914e558936`。新树`~/fwp-wt-ownership-gates-v4-0921`，分支`baseline/ownership-gates-v4-0921`。
5. 逐文件核对十个相关源码/测试和三来源一致，#814包含a092修复。commit-tree不跑普通提交hook，故随后明确对base→candidate执行适用pre-commit，全部通过且源码未变。
6. 主干在其他会话继续前进，先观察到`80bf6bb9`、后`adcda94b`。没有更换候选。十个范围内路径零差不代表其余研究运行时没有改动，差异记录归档。
7. 使用最小环境、umask022、共享项目venv，Python/frontend/registry三条记录器同时起，frontend包括E2E；所有输出独立。frontend约三分钟结束，Python一次全量约23分钟结束，无重跑。
8. 旧档核查器初版假设统一manifest.entries，首个旧档实际用files而报KeyError；原错误log/脚本保留。按实际schema兼容后，六代30/30/86/26/450/115成员/大小/哈希/旧提交字节/候选副本一致。
9. 机械QC核对四个执行记录（hooks及三组门禁），逐log哈希、Python唯一收据、JUnit和终端、前端六步与首尾身份；严格回读/兼容检查均0。候选原样推Gitea，未新建组合PR。
10. 07:12Z封存前：三来源PR仍open/unmerged；旧三v3审查树净`47530e20`，候选净`6eb12c1b8`；远端main=`adcda94b5e401158f1c3aa51f210e1e8d0f0b713`。新证据82文件/2,600,457字节，含README、不含manifest。#814随后仅交接更新至`790dc27a6029d48c795ad896e24ff8b058bd4e23`，源码不变，未把收据移签此文档尖。

## 决策与替代方案

| 决策 | 被否方案 | 理由 |
|---|---|---|
| 固定授权时main和三来源，另建v4树 | 在来源脏/共享树直接混合测试 | 固定revision/tree才能归属结果，也不污染他人的索引 |
| 对象库真实三方合并、保留四父身份，单独跑适用hooks | 手工拷文件伪造组合；声称commit-tree已跑hook | 可追溯真实祖先/合并结果，并补足提交检查事实 |
| 测试中上游变化只另记 | 持续前移候选或给后来main盖旧收据 | 会把结果对象变成移动靶；新main含真实运行时变化 |
| frontend第六步实际跑E2E，五个registry检查全跑 | 只看聚合退出码/首叶绿就推其余绿 | 上次缺叶被fail-fast遮盖的失败形状仍需防 |
| 保留记录器前置错误、旧六档原件 | 修后覆盖失败log/重算旧结论 | 设施错误与产品失败分层，完整审计链不等于只留绿 |
| 独立状态仍NOT_RERUN | 让作者工程绿充当K3终审 | 两者回答不同问题；旧有限预算没有留下最终独立裁决 |
| 有限记录器归档，永久回归仍在#814 | 新装常驻任务/扩建第二套门禁 | 本轮没有新产品洞，调用现有门禁即可；无需扩大运行面 |

## 实测与证据

证据目录：`docs/verification/2026-09-21-ownership-integration-v4/`；入口`README.md`、`gate-qc.json`、`manifest.json`。原件：`~/.finance-runtime/reviews/ownership-integration-v4-20260921/`。

| 叶子 | 实测 |
|---|---|
| Python | Ruff0；**12461P/85S/2X/0F/17warnings**，pytest1377.05s，shell1380.761s，gate0 |
| 前端 | frozen install/lint/typecheck/test/build全部0，**110P** |
| E2E | 真浏览器+隔离测试服务，**34P/2S**，命令0；非线上/生产回填演练 |
| registry | finance-only五项0，符合仅checkout金融仓的CI范围；不覆盖别仓实时工作区 |
| hooks | 适用pre-commit通过，源码未变 |
| readback | 严格树绑定回读/按revision兼容检查均0 |

Python唯一原件：`gates/python/receipts/gate-bVVRCApx/pytest.json`，SHA256=`4223d0f758ca5f35c5be396d4ad6ce25abfece0eb6c7b174538eb9015eff036c`。JUnit12548条，2X来自JUnit/终端，不在receipt counts schema内。各叶首尾同revision/tree/净状态，源文件哈希一致。

前端收据：`gates/frontend/gate/frontend.json`，六命令完整、`identity_stable=true`、`dirty=false`。其他原log与执行环境见各`run.json`。

新manifest哈希：`369fb25cb4a36aae94ac50fab82ff0aead73c771b31af8b074a95585eb1730c9`。脚本/日志仅存档名附.txt，字节不变；临时测试树、缓存、Git对象、DB二进制、node_modules、latest导航不封入。

## 成立与不成立

- 成立：**c615基线上固定组合6eb12的作者工程门禁全绿**，包含a092修复。
- 不成立：独立Spec/Quality通过、后来main合流通过、已合main或部署、生产数据回填成功。
- 旧v3及旧失败结论不改。a092已有作者修复，不写成“待修”；新组合已有工程绿，不写成“未建组合”。
- 未验：真实冻结输入/完整数据库副本的302132父子发布/备份恢复；这是单独数据安全验收，不由普通测试替代。
- shell保留pytest末15行，JUnit不是全stdout；端点净采样不证明中途无改后还原；合作任务归属不是恶意写者沙箱。
- `11963`/`12068`/`12461`分属不同源码/组合/基线；不要据总数差直接算回归或改善。

## 接手顺序

1. 从协调inflight与本证据入口接手；v4及旧v3树保持冻结，别在上面补文档导致身份变化。
2. 明确独立复审对象和有限会话/请求预算；既有K3授权已用完，本轮未自动续。
3. 若要对届时main验收，重新观察/固定基线、组合、跑新全叶，旧收据不移签。
4. 三单与其组合只选择一条合入路径，避免重复合并；合入/部署/生产回填/真实树删除逐项确认。
5. 证据发布评论/最终协调提交指针在本分支inflight维护；此日期快照不反复改写。
