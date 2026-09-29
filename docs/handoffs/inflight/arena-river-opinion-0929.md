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
