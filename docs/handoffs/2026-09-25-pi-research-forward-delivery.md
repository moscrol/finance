# Pi 研究：对齐 #868 候选并交付两个 PR

## 背景与本轮范围

用户要求继续推进。沿用已有 P0/P1 实现，本轮只做离线组合、定向复验和正式交付；不启动真实模型、独审批、自然金融验收、main 合入或8792部署。主检出树 detached b4a35fa2c 有他人改动，未使用它的代码树。

## 发现顺序与已完成动作

1. 重核 #868 的2105封存批：f531，spec PASS_WITH_LIMITS且C3/C7未验，quality/explore路径失败，213/244。旧结果未改判。本会话不把其他会话授权移作自己的模型预算。
2. 推送路径验证分支并开 #910，最初base为#906。原owner随后将#906合入#868（2239c1e82），再前向main至f2610293f；据此把#910的base改为feat/adaptive-research-loop，仍保留WIP。评论906/6854及868/6857明确交接。
3. 研究树先前向固定main03352758c，得到cb343356a；唯一冲突是工单INDEX的新旧状态，保留主线2105状态及历史指针。合并前开发读数171P/3S是脏树定向诊断，不用作冻结验收。
4. 只读doctor发现共享解释器httpx=0.25.2，锁要求0.28.1；当时另一owner已在pr868-gates-20260925-c跑全量工程门禁。本会话未改共享venv、未停其进程、未启动重复全量门禁，已将版本事实通知owner。
5. 将作者的精确候选f2610293fdbe合进研究树，得到6b7c4c4c61ee13f35f32e15cd69311bcf72f99fa。INDEX冲突采用作者保留的L6历史记录，撤掉本会话刚加的重复摘要；最终相对f261恰为一个测试文件和四份文档，生产Runtime/Harness及审查脚本无差分。
6. 固定干净6b7复验七目标，606P/0F/0E/3S/1X，collected610，18.53秒；Ruff全仓通过。推送研究枝并开#911，base同为feat/adaptive-research-loop，WIP。
7. gitea_pr.py conflict-check对#910/#911各自相对当时#868基线均clean；仅证明合并预演无冲突，不证明测试、审查或合入许可。两项PR都未合，#868仍open/WIP。
8. 收尾观察到pr868-glm-qc-20260925-next目录仅有prepare_next.py与next_offline_test.mjs，没有STATE/batch/authorization；它是准备现场，不能据目录名认定已授权或已跑独审。本会话未执行其中脚本。

## 方案取舍

| 选择 | 否决的替代 | 理由 |
| --- | --- | --- |
| 两个窄PR都交给#868 owner | 在研究枝再造或直接替owner合修补 | 单一产品owner，协议与验收可分别审阅；不改变作者受测树 |
| 固定f261进行离线组合 | 测试过程中不断追main | 收据必须对应确切提交；main再变由下一次准入处理 |
| 定向回归并显式记录依赖漂移 | 擅自升级共享venv，或把定向绿叫四叶绿 | 避免影响并发测试；依赖指纹一致不等于符合锁 |
| 保留WIP等待审阅 | 工程数绿就合main或启动新独审 | 授权、工程、独审、自然质量和部署是不同条件 |

## 验证与边界

精确受测版本：6b7c4c4c61ee13f35f32e15cd69311bcf72f99fa。

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -rsx \
  intelligence/tests/conformance \
  intelligence/tests/test_glm_agent_runtime.py \
  intelligence/tests/test_research_progress.py \
  intelligence/tests/test_adaptive_research.py \
  intelligence/tests/test_research_plan.py \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_research_harness.py
```

收据：`~/.finance-runtime/test-receipts/20260924T161506Z-6b7c4c4c-0922655b0f78.json`，校验器按精确revision和全部七目标通过；dirty=false、worktree_dirty_total=0、Python3.12.13、依赖指纹e1c50cb821a30f00。实际共享依赖与锁有漂移，未宣称doctor ready。

3S是参考后端声明不适用的合同；1X是既有codex_headless修复入口缺显式收据基线。36项研究链场景覆盖off/on、quick/deep、观察追查、异常恢复、越权拒绝、复核再查、耗尽/取消及变异证人；模型和来源均为替身，真实模型0。

#910仍使用原3e8ea5b64的57P/0S收据，未给当前PR或f261移签；细节见前日路径验证快照。本轮研究收据也不移签后续文档HEAD或原owner候选。没有完整Python/frontend/E2E/registry四叶结论，没有自然模型主动纠错、真实Workbench研究质量或8792身份结论。

## 下一步与不做什么

- 原owner分别审阅#910、#911，再对最终组合冻结候选并验证。需按锁处理依赖，但不在别人的测试运行中改共享环境。
- 新独审批用新证据根、当前输入、工程及身份准入和明确额度。1405/2105仍封存；不得直接执行生成器遗留历史配置。
- 独审闭合后才接#76/L6逐行授权；main与生产另批。
- 本轮复用merge-tree、doctor、收据校验器和Gitea工具，未新增临时框架。依赖漂移已由现有doctor捕获，不需要再造第二个检查器；本次协作/版本取舍留作项目快照，不另写通用理论。
