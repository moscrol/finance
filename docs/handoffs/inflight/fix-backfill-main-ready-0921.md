# 302132 当前main离线整合

## 这个分支做什么
前向整合302132受限回填实现到main基准728f3271，只交代码候选，不执行生产回填。

## 决策与被否方案
- 原1fd34dc7/be3f2930取4个源码/测试文件，否决整枝覆盖main CLI。
- 父命令拒绝会被忽略的--db，否决默用环境目标造成操作者误判。
- 原准备与旧全量收据保留，否决旧SHA移签。续轮见 `docs/handoffs/2026-09-21-backfill-parent-target.md`。

## 当前状态
代码49f32259已推WIP #813，父--db在文件探针/编排前返回2；内部child不变。原来源树保留。main未合，8792未切，生产库未写。
组合e1b63b1a在独占baseline/ownership-gates-v2-0921作者全叶验收通过；不移签本分支后续文档尖。

## 已验证
新增父目标反例旧版1F，修后整文件105P（提交前作者迭代）。旧400d02dd的12017P/85S/2X仅签旧代码。
组合前端110P/E2E34P2S、lint/typecheck/build和finance-only registry五项通过；Python12061P/85S/2X、门禁读回0，全叶只签e1b63b1a。原第一组合321712b6控制台12059P、收据门禁4，未追认绿。

## 未验证 / 已知边界
本轮未取得独立Spec/Quality裁决，没有真实冻结输入的完整副本父子发布演练或生产验收。合成产物通过不等于真实staging/备份/恢复可发布。分支名main-ready不是批准。

## 下一步
独立复核目标绑定、深schema/oracle、protected slices及失败不发布。原合同从849396d9读取docs/handoffs/2026-09-14-302132-prep-review.md；其中历史库哈希/磁盘数不可沿用。真实执行前重冻输入与基线并另获授权。
组合原件在协调分支ops/worktree-ownership-closeout-0921的docs/verification/2026-09-21-ownership-followup及ownership-recheck目录。

## 踩过的坑
父目标由MARKET_FEATURE_STORE_DB解析，--db仅内部child；别为方便另开直写通道。唯一收据设施修复在#814/d5d807f80，非本分支，合流时不能漏带或复用共享latest。
