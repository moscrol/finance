## 这个分支做什么
Knevo材料处置与入口修复留证；PR #877仍WIP，语义验收未通过。

## 决策与被否方案
- 不改冻结28题/原件，不关审稿闸、不缩八问义务凑绿；揭盲不进盲测分母。
- 入口修复与语义交付分账；判官passed、completed、作者意见均不自动放行。
- 最终快照：`docs/handoffs/2026-09-23-knevo-material-repair-closeout.md`；原阶段快照和失败原件不覆盖。

## 当前状态
- 修复及live固定`f1fd8aa1a16bea4f3dd4e2ba0e5fd92114aea2c6`；工程固定`8aadc23d4873251ffb3b0ecf4f9355f111ba6253`。本次后续提交只留证，不代签全仓/live。
- runtime根`~/.finance-runtime/knevo-absorption-20260923/`；新live看`material-repair-f1fd8aa1a/observations.json`及179文件manifest；工程看`material-repair-closeout/current.json`。
- 新12题仍9 completed/3 failed、端到端0/12；隔离服务已停，生产8792未动。PR评论6251已回读；最终平台状态看收据目录`pr-final.json`，缺文件不代表已更新。
- 不合main、不部署、不回补、不写画像。main观察2edbe4c46与8aadc无文本冲突，组合版本未验。

## 已验证
- f1fd定向580P/4S；真实run_turn探针12题保合同/原题/三包八问，受测前置读取尝试0，不等于全部IO认证。
- 新live12题私有原题保真、material_only、0工具请求；三包八问齐。Q14输入hash精确复现，news_impact三层指导确已送达。
- 8aadc干净全仓14664P/85S/2X/0F，collected14751；Ruff与完整收集面验签0。前端120P、E2E34P/2S、安装/lint/typecheck/build及registry五项通过。

## 未验证 / 已知边界
协议失败3、来源拒绝3、无效出稿/漏答5、实质越界1。Q14judge passed却无依据称小额、情绪主导/大概率回吐，未接纳。Q18真实台账/空集/权限/身份/跨轮未验；无独立审查、质量增益、胜率/top3或完整消融。

## 下一步
1. 按原件捕获判官invalid tool call具体协议原因，不猜字段后放宽。
2. 修一claim多句/私有标识的续修失败；再验逐句支持、删句后的任务完整性。旧失败不改判。
3. 等用户合并授权；固定届时main+PR组合另跑完整门禁。

## 踩过的坑
用主树`.venv-workbench/bin/python`，run_main_gate从目标树cwd启动。PR diff-check仍exit2（原件文末空行），七份hash正确不改；registry bundle因此总exit1。附加vault lint仍38错/17警告，非全检查绿。缺audit记unknown；端点diff的D不证明主干删除，#879只改四份claim-scope文档。
