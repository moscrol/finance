# Arena · 原版8798优化（2026-09-29）

## 这个分支做什么
在原App与导航内优化连板／长河，复用原daily归档与指标。详细快照：docs/handoffs/2026-09-29-original-8798-optimization.md。

## 决策与被否方案
原入口增量而非第二套侧栏；可读滚动轴而非120日硬挤；原归档而非重算；研报覆盖与公开传播分开而非混成热度。真实API只读隔离验证，不直接换生产JS。

## 当前状态
detached HEAD b4a35fa2c，混合脏树，未提交／未合并。本轮17文件已守卫上传并核对SHA；隔离构建在.tmp/arena-8798-opt/web-build。生产static未动，8798未重启；三条新API仍404。用户已选择“先看验证版，暂不发布”；不替换资源、不重启。

## 未验证 / 已知边界
没有生产配套上线验收；不是全仓验收。真实AIHOT信源未配置，未导入新闻／刷新行情／付费采集／调用模型。原版数据仍截至09-24。
只读预览是原App+水印和只读桥；预览main.tsx、vite配置、数据桥不可上传生产。私人会话／凭据／问答禁止载入。之前独立设计HTML不是本轮入口。

## 下一步
仅在用户再次明确授权发布后，先核对并发改动、运行配置、活动任务与回滚，再配套发布前后端。8798当次PID92925（cwd主仓）；launchd com.a77.finance-workbench是另一PID79816，不可直接当作8798重启。勿误动其他端口服务或他人脏文件。
生产仍用index-BqIYiaO5.js/index-DLCJm1Ks.css；新隔离JS index-CJbthfHq.js。后端必须加载daily-review/daily-overview/opinion-attention；不能只替换静态资源。

## 已验证
本轮前端37项／7文件，后端127项／11文件；TS、改动TSX ESLint、隔离build通过。后端收据20260929T071413Z-b4a35fa2.json。浏览器1440与390：梯队／股票、120日密度、同日跨页、历史07-06、最新、缺失日报、六轨／横扫／纵扫／区间、公开消息缺口通过；列中心误差<1px，无页面脚本或市场API错误。模型配置403是预览故意拒绝。证据.tmp/arena-8798-opt/verification/。

## 踩过的坑
最新操作须解除历史锚定，迟到响应不可改写新日期；切实体清旧图、切日期清旧行。浏览器等业务元素而非networkidle；MCP桥延迟不能用5秒断言判断故障。th加scope=col，真实Chrome与JSDOM隐式表头行为不同。备份before、before-fix1、before-fix2在.tmp/arena-8798-opt/。


## 2026-09-29 DuckDB消费与SPT/风远观察验证增量

详见 `docs/handoffs/2026-09-29-agent-consumption-observation.md`。新只读物理审计器、8个测试及原RiverHome的观察验证已上传；7文件哈希见`.tmp/arena-consumption-0929/verification-final/source-hashes.json`。同前阶段合并23文件哈希一致。

- 72对象；56 fact/feature=26语义+16豁免+14未归属（10非空）；脚本exit1=正确发现缺口，未加入CI，无DB修复。
- 26 SQL成功；Episode15success/10stale/1 intentional empty。主线69行8指标空仍success的问题未修。
- 同日同码389新高股票对应3443成分记录high_status空。原生turnover/1e8与主表amount的5555条逐码匹配四位小数，是金额口径，不能补主表换手率。
- 观察页：同日事实、人工SPT/风远条件、反证/复查、浏览器冻结记录及JSON导出/人工提示词。非回测/非服务器台账，无模型提交。
- Mac185后端、44前端测试与TS/相关lint/隔离构建通过；12新浏览器+14旧回归通过。初次Node存储fixture失败已修，真实浏览器另验。
- 8798仍PID92925、旧index-BqIYiaO5.js，daily-review仍404；profiles接口200[]未解决。没有发布、重启、采集或模型调用。
- 新隔离Mac构建 `.tmp/arena-consumption-0929/web-build/` JS index-CE_FA8mp.js。Arena只读8911默认长河→观察验证；预览专用main/代理没有上传。
- 用户“先看验证版，暂不发布”仍有效，后续发布必须再授权。不得把此报告写成全库消费已打通或全仓测试通过。


## 2026-09-29 字段质量门槛与新高语义执行完成

详见`docs/handoffs/2026-09-29-agent-quality-high-status.md`。当前基线已并发推进到f922f5d3，旧b4a35fa2和旧23文件一致性不能作为当前全仓状态。

- 已按SHA防覆盖合并7文件；备份`.tmp/arena-quality-0929/before/`，清单`applied-hashes.json`。
- FinanceQuery对请求字段缺值/非有限值及普通聚合有效输入不足标记quality_gaps；Episode变partial，gaps与query_basis/证据卡保留提示，不完整数值不投影为可计算观察值。
- 合法0、未请求字段、仅查名单、明确有限样本均值契约不误判。high_status空/空串未核验不等于非新高，已有明确标签保留；个股同日同码查stock_high_daily，不能用来证明板块新高。没有回填或跨源COALESCE。
- 实库八组前后对照：主线8指标从success/0gap变partial/8gaps，名单仍success；原生turnover未用于填换手率。389股票/3443空标记关联仍在。
- 顺带恢复create_app此前丢失的register_river_routes(app)，原基线也失败的路由测试已修；加3条日报API登记断言。source TestClient四条GET都200。
- 最终21个相关测试文件404项通过，新质量用例18项包含其中；Ruff通过。源代码测试收据20260929T084701Z-f922f5d3-ca8a93bd9f1a.json。不是全仓测试，没有模型调用。
- 本轮没有发布、前端构建、DB写入、采集或重启。8798仍PID92925，日报仍404。但复核发现生产assets变为index-BA_Tz2HK.js / index-D80DtDZY.css（非本轮命令造成），未回滚它。明确存在共享环境资源漂移，不能再宣称生产静态资源整体未变化。
- 保持用户暂不发布的边界。正式发布前重新检查前后端来源、进程、授权和回滚方案。
