# feat/substitute-observation-probe

## 这个分支做什么

空袋替补观察探针 P0：主线题材当日无严格双红匹配时，盘面题的组件包在缺口句之后
自动补带标签的替补池（题材→成交额最大匹配板块→前 2 只个股，`[出清/分歧观察]`
标签先于名单）。把五臂对照里现场写臂那半档 ReAct 增量收成确定性组件。
Spec：`docs/superpowers/specs/2026-08-25-substitute-observation-probe-design.md`。

## 当前状态

树 `/Users/a77/fwp-wt-substitute-probe`，基线 `gitea/main@760bf79b`。
改动三件：`market_watch_pack.py`（ProbeReceipt + 探针 + render 尾接）、
`ask.py`（`bind_market_watch_pack` 单点开 `substitute_probes=True`）、
新测试 `test_market_watch_substitute_probe.py`（10 例）。台账 `R-20260825-01…03`。

## 已验证

- 红→绿：收集期红（符号未实现）→ 实现后 10/10 绿。
- 变异实测：板块查询改 `<=` → 邻日测试翻红（`{'hit','no_match'} != {'no_match'}`），已还原复绿。
- 相关存量 66 过（market_watch 两文件 + outlook weekly pack）。
- ruff 三个改动文件 0。
- live（只读真实库，走 `bind_market_watch_pack` 生产接缝）：2026-08-24 主线=[医药,有色金属]，
  有色被双红覆盖、医药无匹配 → 探针补「医药医疗（1556.85 亿）→ 药明康德/沃森生物」，
  `served_date=2026-08-24`。收据 `~/.finance-runtime/substitute-probe-live-20260825/`。
  与 08-23 live-toolkit 手工决策同形（当时也是药明系医药池）。

## 未验证 / 已知边界

- 全量 pytest **6389 passed / 13 skipped / 0 failed**（沙箱外，287s）。注意该跑
  发生在删 `probe_id` 之前；删除后焦点 25 例 + 门禁全绿，且 unread-fields 门禁
  已证明该字段全仓无读者，全量结论不受影响。首跑被沙箱拦（3 个 sqlite 收集
  错误）是环境性，勿当代码红。
- 生产 8792 未切；episode 全链 live（模型在场）未跑——`supplemental_evidence` 已带
  替补块，模型残差是否规范引用替补池属质量观察，不阻塞本单。
- gap 句是全局判定（任一主线匹配双红即不出句），探针是逐题材判定——08-24 live
  就是「无 gap 句但医药探针触发」的形状，行为正确；trigger 文本自带原因。
- weekly 五日包、一般题路径未接（P1，`R-20260825-03`）；模型点菜 P2 须走开关板原子。

## 下一步

1. 全量 pytest 出结果 → 若干净（或与 main 同红）则开 Gitea PR，合并等用户确认。
2. P1-a：weekly 最新交易日袋接探针（开口预取账本纪律）。
3. P1-b：`research_contract` operator 接一般题路径（先冻结三道 SPT 原题今天编译出什么）。

## 踩过的坑

- 沙箱只允许写主工作区，worktree 里 shell 写文件/pytest 缓存/ruff 缓存都会被拦：
  编辑走编辑工具、ruff 加 `--no-cache`、全量测试要沙箱外跑。
- 按绝对路径跑脚本时 `sys.path[0]` 是脚本目录不是 cwd，live 脚本要手动
  `sys.path.insert(0, os.getcwd())` 才吃到干净树的代码。
- 变异捕获要分离播种：把「板块行在邻日、个股行在站立日」拆开，才能让
  「板块查询单独改 `<=`」这个变异不被个股层的 no_match 掩护。
