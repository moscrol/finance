# 三张收尾代码 PR 的隔离合流验收

## 授权与输入

用户对“先做隔离合流和本地完整门禁，不合 main、不部署”明确说“执行”。
本轮只组合 #806/#805/#808；不关闭原 PR、不新开替代 PR，不调用付费外审。

开工复核三个 PR 均 open、未合并，base 均为
`728f327160bbd2485cb635e7ef09d040d718d7b5`，实际 Gitea main 也相同。
主检出 detached b4a35fa2 有其他任务改动，未在其中编辑。

| 顺序 | 来源 | 完整提交 |
| --- | --- | --- |
| 1 | #806 宽基指数 | `5d46e626abf4eec3f2f384747e3152959b3e2f90` |
| 2 | #805 生成降级 | `4aa805400690d3d1b9f9a02eae765a85810d0db8` |
| 3 | #808 两参数表格 | `89e6217a254f56aba4737798d487cd33ded0106b` |

## 已完成的合流

从固定 main 新建 `baseline/stale-closeout-integration-0921`，独立工作树
`~/.finance-runtime/reviews/stale-integration-20260921/candidate/finance-workspace-private`。
按表中顺序使用普通双亲合并，保留各候选的完整历史，不重写候选提交号。

三次合并均无冲突：`2767b4ee`、`9af87377`、`db2bf702`。
文档前组合提交为 `db2bf7021c8f06f20e0e7feeaf14cadf5bec5559`。

逐来源核对：三个源提交都是组合提交的祖先；各自修改的所有路径与来源逐字节相同。
三组修改路径无交集，合流后相对基底恰为三者并集（45 路径），没有额外改动。
这只是来源/文本检查，不代替运行验证；`merge-union-check.json` 保留结果。
本说明与本分支 inflight 是额外的两份文档，不修改 inherited 交接或业务代码。

## 选择与被否方案

| 选择 | 被否方案 | 原因 |
| --- | --- | --- |
| 独立验收分支先组合 | 未授权直接合入 main | main 合入和部署均需另行确认 |
| 保留原提交的双亲合并 | squash/cherry-pick 或移动原候选 tip | 可追溯原 PR 来源，旧候选收据身份不被改写 |
| 含交接的最终提交重新跑完整门禁 | 把三张分支的绿拼成组合绿 | 行为可能相互影响，收据必须证明同一个实际版本 |
| 最终结果外置并回贴原 PR | 测完又追加结果文档、沿用旧 SHA 收据 | 后者改变被测提交；外部收据按完整 SHA 绑定 |
| 复用现有 Python/前端门禁入口 | 新造执行框架或增加 skip | 本次不是工具能力建设，没有新框架必要 |

## 门禁收据合同

证据根：`~/.finance-runtime/reviews/stale-integration-20260921/`。
最终入口为 `README.md`、`python/python-registry.json`、`frontend/receipt/frontend.json`。
只认与本分支最终完整 SHA 相同的收据；本文不提前声明尚未结束的门禁通过。

- Python 解释器固定主检出 `.venv-workbench/bin/python`，env-i 白名单、umask022。
- PATH 包含 `~/.local/bin` 的 uvx；不删图或加 skip 来隐藏环境失败。
- Python 和前端分别用独占检出，首尾 SHA 相等且全树干净；收据目录在树外且不覆盖旧运行。
- 固定只读邻仓 KB `1254224be89e2c4974350b7f3e985dbedb5dc043`、研究站
  `f606583867fe1cad8de96b06be1dd6cfe2b57e51`。门禁复用既有 runner，仅重定向收据输出。
- 完整检查包括 Python/Ruff、registry 四项与 ledger-crosswalk、前端 install/lint/typecheck/
  test/build/E2E；原生收据严格 expect-revision、base-drift-max=0，另校验日志哈希。
- 前端测试服务使用独立端口 19581/19584，不借用 8792；不挂生产库或模型凭证。

## 边界与后续

本轮是作者本地组合验证，不是独立复核，也不认证真实模型回答质量、供应商支持或数据覆盖。
#804/#807 文档 PR 不纳入组合，不继承本组合签字；本轮也不代审其全部内容。
#770 的材料来源、权限、身份、同数重算输入和 requests_recompute 仍独立处理。

原 PR 中旧交接的“未跑全量”是历史阶段文字，单枝最新结果看各 PR 评论；
任何单枝结果都不能替代本次组合收据。也不能把本次组合结果移签给未来不同的 main 提交。

全门禁成功后保留并推送验收分支、把同 SHA 证据回贴三个原 PR；不自动合并或关闭它们。
后续独立复核/合 main/部署由用户另行授权。若 main 或输入 PR 改变，先判断差异并对实际版本重验。
旧树、ignored 数据、补丁、原始失败日志和恢复锚均保留；不做生产采集、回填或工作树清理。
