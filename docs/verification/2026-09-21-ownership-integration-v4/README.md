# Ownership v4：固定新组合工程验证通过，独立验收未补跑

## 对象与授权

用户再次“继续”后，只承接三单的新隔离组合、Python/frontend/E2E/finance-only registry 工程检查、证据与交接；无新模型会话/预算扩张、main 合入、部署、生产回填或真实 worktree 删除。

- 固定基线：`c615adbd2f861e23f2c8d03631833f98b3ae5aba`（授权时远端 main）。
- 候选：**`6eb12c1b8a41071fd4af8bee343950fe0b85b221`**，Git tree `e99dad14cb946a112d92537289854d914e558936`。
- 检出：`/Users/a77/fwp-wt-ownership-gates-v4-0921`，分支 `baseline/ownership-gates-v4-0921`，已原样推 Gitea；未另开组合 PR。
- 四个父提交：基线 + #812 `8d955fc38747bc0e0aad32f6889b0b7d84f79530` + #813 `5994230dadcf23ec0a17c0b27e3a649d782ecf94` + #814 `ffc8e1a83032cc06881aa3a1132947fd7feac363`。
- #814 已含 `a092a021c` 的调用级收据归属修复；`source-inclusion.json` 逐字节核对十个相关源码/测试文件与三来源一致。

`assemble_candidate.py` 在 Git 对象库执行三次真实 merge-tree，每次 exit 0、无冲突、无手改源码；最终四父提交保留来源身份，不借用各来源索引。适用 pre-commit 检查随后显式对固定候选执行并通过，不声称 commit-tree 自带提交 hook。

## 本轮实测

| 检查 | 结果 | 原件 |
|---|---|---|
| Python shell gate（含 Ruff） | exit 0；**12461 passed / 85 skipped / 2 xfailed / 0 failed，17 warnings**；pytest 1377.05 秒，整门 1380.761 秒 | `gates/python/run.json`、`0.stdout.log.txt`、`0.stderr.log.txt` |
| 唯一 Python 收据 | target/tree/revision 正确，dirty=false，总脏路径0，依赖闸未绕过；与终端/JUnit一致 | `gates/python/receipts/gate-bVVRCApx/pytest.json` |
| JUnit | **12548** 个 testcase，2 个 xfail 是 skipped 子类型；2X不在receipt计数schema里 | `gates/python/junit.xml` |
| 前端六步 | frozen install、lint、typecheck、test、build、test:e2e 全 exit 0；整组164.113秒 | `gates/frontend/gate/frontend.json` 与六份日志 |
| 前端单测 / E2E | **110P / 34P+2S**；E2E=端到端浏览器测试，使用自建隔离服务/夹具，不是线上部署检查 | `frontend-3.log.txt` / `frontend-5.log.txt` |
| 注册表 | finance-only 五项全部 exit 0 | `gates/registry/run.json` 与逐命令日志 |
| 提交前检查 | 适用 hooks 通过，代码树未变 | `gates/hooks/run.json` |
| 严格回读 / 兼容条件检查 | `run_main_gate.sh --receipt` 与 `check_test_receipt.py --expect-revision` 均 exit 0 | `readback/run.json` |

各叶首尾 revision、Git tree、全树干净状态和十二个源文件哈希一致；`gate-qc.json` 核对原始日志哈希、全部叶子退出码、精确收据、JUnit与终端结果。运行一次，无门禁重试。Python/front-end/registry 同时起，使用独立输出；前端约三分钟结束，未因首叶结果跳过其他叶。

环境仅保留明确白名单，`umask 022`，共享项目 venv/Python3.12.13，`PYTHONDONTWRITEBYTECODE=1`。Python临时目录/缓存/收据/JUnit均在树外；前端安装/build/测试产物为该候选的ignored文件。registry按仅检出金融仓的CI合同排除跨仓工作区漂移，不是全workspace注册表验收。

## 上游漂移与结论边界

- 授权时 main=`c615adbd2`；候选组装后曾观察 `80bf6bb9`，07:12Z已为 **`adcda94b5e401158f1c3aa51f210e1e8d0f0b713`**（其他会话推进）。未改变候选、未重签收据。
- 十个本轮直接相关路径在基线→当时main间无差异，**但研究运行时等存在真实增量**。该零差只是范围观察，不能推导后来的main合流绿。详情 `main-drift-source-stat.txt`、`main-drift-since-freeze.txt`。
- **本轮是作者工程合流验证，不是新独立Spec/Quality审查。** 未新启动K3。旧v3 `47530e20` 的双轴触40请求上限、缺终审及旧缺陷历史不改；修复已包含且有作者回归，不再描述为“修复未做”。
- 未跑302132真实冻结输入/完整数据库副本父子发布与备份恢复演练，未生产回填、合main、部署、删真实树或接管Arena。
- shell仅留下pytest末15行；JUnit是逐用例结果不是全量stdout。首尾干净采样不证明中途未发生改后还原；归属标记不是恶意写者/OS沙箱。
- 数字不能混比：`11963` 是#814旧单分支、`12068` 是历史v3组合、`12461` 是新基线组合；不能仅凭这些不同对象总数算质量改善或回归。

## 历史保护与设施错误

六个旧档 **30/30/86/26/450/115** 文件（各含README、不含manifest）成员/大小/哈希/冻结提交字节一致，候选包含的旧证据副本也一致；三棵v3审查树保持净`47530e20`，来源树首尾未改。详 `previous-archives.json`、`protected-trees-before-closeout.json`、`preseal-state.json`。

两次记录器前置错误均保留，见 `apparatus-notes.md`：缺ref的show-ref退出码预期错；旧manifest的files/entries schema差异。未当作产品失败，也未抹去原件。

## 归档规则与下一步

`manifest.json` 列出封存成员/原路径/字节/哈希；文件数从manifest生成，不人工维护。`.py/.sh/.log`只附`.txt`改存档名，不改字节。排除缓存、测试临时树、DB二进制、node_modules、Git对象及latest导航；原件根为 `~/.finance-runtime/reviews/ownership-integration-v4-20260921/`。

候选保持冻结。下一步需明确：独立复审的对象、有限会话/预算，以及是否在届时main上重新冻结合流。不能将#812/#813/#814与组合重复合并；合main/部署/生产回填/删树分别授权。本轮不创建新的长期调度设施；永久回归保护仍在#814源码中，有限记录器是审计证据。
