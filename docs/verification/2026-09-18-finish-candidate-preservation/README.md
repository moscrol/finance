# 准入前研究稿保留：固定提交离线验收

**本轮工程与固定原件回放通过；没有新产品live，原整体验收仍 `not_passed`。**

代码：`35ee8a5c05aa1a25498ab9c32cc548d0166bb5a7`，分支 `feat/research-answer-preservation`。本页是作者收据，不是独立安全/金融认证。未 push、未开 PR、未合 main、未部署或切换8792；本轮未重新核验生产health。

## 入口与身份

- [设计、发现顺序及被否方案](../../handoffs/2026-09-18-finish-candidate-preservation.md)
- [原真实失败，保留原判](../2026-09-18-research-answer-preservation/README.md)
- [机器收据](receipt.json) / [新包内容指纹清单](artifact-manifest.json)
- 私有根 R：`~/.finance-runtime/reviews/research-candidate-preservation-20260918/`。新包封存**90文件、445,767字节**；原件/失败日志只存本地，不上传正文、DuckDB或浏览器trace。
- 旧214文件/5,475,994字节包与44文件/16,937,713字节组件包逐文件hash/长度复核未变；见 `R/previous-bundles-integrity.json`。本轮不是覆盖旧包的新版本。

## 做了什么

`FinishAdmission.candidate` 与合法finish、完成度分离；拒收安全稿入同任务候选账，旧稿在前、补修在后。格式错按码纠正，研究缺口在原预算与权限内继续；不再统一要求研究稿1000字、恢复稿1200字。用户篇幅、材料合同、上下文容量及资源上限不变。

连续Episode/SDK续修、headless一次禁工具恢复均承接候选；取消后已返回安全稿可保留，但仍 `failed/cancelled`、无额外调用。恢复携带完整候选及实际绑定/正文引用卡，必要证据不再受12卡/360字符截断，E号稳定；普通工具900/240预览未改。身份/假hash/同hash语义变化/重复JSON键/私有协议及未知E号复活仍拒。

## 固定提交工程检查

| 叶子 | 实际结果 | 原件 |
|---|---|---|
| Python全仓 | **11664 passed / 81 skipped / 2 xfailed / 17 warnings**；0失败/错误，662.25秒 | `R/checks/research-freedom-clean24.txt` |
| pytest收据 | 干净树、依赖门未绕过；期望SHA/解释器/依赖/本地基座漂移校验通过 | `20260918T101211Z-35ee8a5c.json`；`research-freedom-receipt25.txt` |
| 前端 | lint/typecheck/build通过，8文件**107 passed** | `research-freedom-frontend24.txt` |
| 浏览器E2E | **34 passed / 2 skipped**，8846/8847隔离fixture，非真模型研究 | `research-freedom-e2e26.txt` |
| 静态与目录 | Ruff/diff/layer/path/unread-fields/tool reachability/runtime catalog通过 | `research-freedom-ruff24.txt`、`clean-static30.txt` |
| 注册表 | parseability/check/backfill-tables/generate-views均exit0 | `research-freedom-registry24.txt` |
| 台账交叉核对 | exit0，反向**98 warnings**保留 | `research-freedom-crosswalk24.txt` |

完整Python收据在 `~/.finance-runtime/test-receipts/20260918T101211Z-35ee8a5c.json`，R内有副本。后续文档提交不移绑这份代码收据。`env -i`只保留PATH/HOME/KNOWLEDGE_WIKI，`umask 022`；Python3.12.13、依赖指纹 `3328bed61f3e21ea`。macOS26.4/Node26.0.0/pnpm10.12.1/DuckDB1.5.4，与CI的Linux/Node22/DuckDB1.4.3不等价。skip/xfail/warnings不计通过案例。基座漂移0仅对本地冻结 `gitea/main@0a1cb8c4`；本轮未fetch远端，合并前须另验最新基线。

失败也保留：开发 `full20` 为2F/11662P（缺task事件的测试夹具、后稿覆盖旧合同），随后改正并在干净35ee重跑。E2E25为1F/33P/2S：服务改8847但测试仍访问默认8794，补 `RE06_E2E_URL` 后E2E26通过；首败日志与trace在 `R/e2e-first-failure/` 和 `R/checks/`，不删测试换绿。8846/8847结束后无监听。

## 原件回放：两路径均保留四段，拒收不变

复跑命令（输出必须用新路径，拒绝覆盖）：

```bash
cd ~/fwp-wt-research-answer-preservation
~/finance-workspace-private/.venv-workbench/bin/python \
  scripts/replay_finish_candidate_preservation.py \
  ~/.finance-runtime/reviews/research-answer-preservation-20260918/users/probe-preservation-20260918/runs/run_20260918_113122_450933/continuous-episode.json \
  --output /tmp/finish-candidate-replay-NEW.json
```

固定源2,095,066字节，SHA256：`2ec9617b42c551ac42b882a9c5b339d0894a0037904de263465bfec539aad4f0`。脚本先校验原件指纹，预置93张冻结卡，回放turn-6、turn-7、恢复三次返回；此前8次工具不重执行。这是**候选边界回放**，不是原完整运行或原根预算时序的重演。

| 项目 | 继续研究路径 | 禁工具恢复路径 |
|---|---|---|
| 原拒收 | `not_json_object`、`history_missing_comparison` | 相同 |
| 四部分原文/顺序 | 全部精确保留 | 全部精确保留 |
| 合稿/公开字符数 | 3512 / 3722 | 3512 / 3722 |
| 模型替身/真模型/工具调用 | 3 / 0 / 0 | 3 / 0 / 0 |
| 状态/判官 | partial / unavailable | partial / unavailable |
| stop reason | model_finish | finalization_recovered |

合稿SHA：`41b6b3f80a58d37976e86f7aff53ee2f9fb5965e21904d5fb2679e1786e468d7`；公开SHA：`8b6b0d4781c841ad10d15a8300cd5f69194f0921413e9aeb3337e65de4c3610c`。`R/original-replay.json`绑定干净35ee；判官故意不可用，未模拟金融通过；原live `not_passed`、`new_product_submissions=0`不变。

## 保护确实承重，而非只看绿灯

正式专项68项通过；R的 `mutations-v2/receipt.json` 为八组**进程内撤保护**反证，均出现预期失败，源文件hash不变。测试收据自动写入关闭，避免变异结果冒充固定提交。不是穷尽性变异覆盖，也不是独立审查。

| 撤掉什么 | 命中的失败 |
|---|---|
| 候选保留 | 3F，前两稿丢失 |
| 待复核计数 | 1F，精确包含抹掉复核债务 |
| 同hash语义复核 | 1F，日期变更仍拼稿 |
| E号身份复核 | 2F，重排/未知号复活 |
| 候选公开清洗 | 2F，测试秘密及私有行留存 |
| 实际正文判定 | 10F/3P，标题/来源/notice撑稿并花判官调用 |
| 恢复完整依赖卡 | 1F，仍只有12张卡 |
| 取消出口入候选账 | 1F，返回安全稿又变空 |

v1恢复变异同时去掉candidate_drafts键，失败命中太早；v2只撤完整证据块，命中证据数量断言。两版原件均保留，不算16种保护或移除失败。

## 扫描及封存如何解读

`R/secret-scan.json`扫描88份文本，记录**10个“文件×模式”命中、52次具体匹配**：38次Python点号模块符号误报、14次显式测试假秘密（含pytest截短表示），未分类0。它们作为失败证据保留，**不能宣称整包零命中**。本次回放原件/公开结果的限定扫描为0，文档另扫；均是现有模式扫描器，不是独立安全证明。二进制失败trace不纳入文本扫描，包含在hash清单。

首次封存量具自身的局部变量赋值被secret_assignment误认，因未分类而停止；改变量名后封存成功，未放宽扫描器。首次脚本/失败日志/未完成summary留在 `R/closeout/`，不计入已封存90份分母；不覆盖原失败日志。

清单只对列出的文件成立；不对后增closeout目录或共享vault全局作认证。完整记录见机器收据，不把“扫描通过、作者回读、引用号存在”解释为逐句金融真实性。

## 仍未证明什么

1. **跨进程保稿未做。** 候选账目前在内存，`EpisodeState`没有候选恢复合同；`episode_restore._terminal_outcome()`仍可能空draft。
2. 新版Workbench真实模型研究交付、旧 `answer_query` 真实保稿、独立质量/金融认证未跑。浏览器fixture及固定模型替身不等于这些验收。
3. 旧helper/eval动态兼容链未全审；普通预览、受控按E扩读、进度计数、板块比较覆盖和原七类金融问题仍另线。
4. 没有换SDK、模型或扩大根预算，未作公平A/B或收益认证。下一次live须另冻结协议并确认，不能覆盖原一次首题的失败。
5. 与并行runtime/材料/财报分支尚未组合验收；本地基线不代表远端最新。合main、部署或8792切换仍需用户确认。
