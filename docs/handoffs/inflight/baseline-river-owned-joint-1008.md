## 这个分支做什么
隔离验证river历史与D4交付；NOT_PASSED，非可发布候选。不合main、不推送、不部署。

## 决策与被否方案
| 选用 | 否决与理由 |
|---|---|
| D4拒未类型化事实、D10整块INFERRED并存 | 不择一；任一旧实现均被另一合同证人拒绝 |
| 保留自然时钟两红 | 不删断言/xfail、抬12K/48KB或改哈希换绿 |
| 准入合同与日期夹具分账 | 不接管Codex owned/运行层；最早丢失在B材料准入 |
展开：[联合根因](../2026-10-08-river-owned-joint-consumer.md)、[午夜第二红](../2026-10-09-joint-closeout-clock-boundary.md)。

## 当前状态
树`~/fwp-wt-river-owned-joint-1008`。代码/测试642b45358=main bd66de250加river af1f64b9f整枝预览、两冲突解决、五联合证人。ea8a5c159仅文档。最终文档HEAD、独立复跑及封存查`~/.finance-runtime/reviews/river-joint-consumer-20261008/completion.json`与同级外部seal-check，指针不证明文件已生成。原river不动，Codex新研究流程在途不吸收。

## 已验证
642净树68文件2084P/1F；ea8自然时钟同范围2083P/2F/0E/0S，97.33秒，收据`20261008T162844Z-ea8a5c15-c626cc8658e9.json`可采信。第二红为协议字节测试漏设cutoff，跨午夜变日期；main/642同败，显式8日夹具原断言过、9日败，仅差截止日。未修产品/断言。普通B及原生Episode联合过；两冻结库三截止工具字节同原river、库哈希不变；旧118/46/60包未改。

## 未验证 / 已知边界
grounded联合D10行11228字符，反证/缺口后D4三事实送达0；D4-only送达3。最短一条可装，三条合计12943。DecisionBrief仍列省略ID。D4 query_basis/strict元数据在main grounded也丢。owned仅认证精确片段，全文unassessed。
新模型0；旧GLM全文未过。无联合HTTP专项、全仓/前端、真库、Workbench真写手判官、多轮或独立金融批准；日路径/源版本未补。

## 下一步
重核HEAD/脏路径并协调AnswerSpec→registry→DecisionBrief送达集合、元数据、引用闭合和溢出/反证负控。日期夹具交协议所有者；两个红灯均保留至实际修复。新revision独立复跑；真实GLM另阶段、真库另授权。

## 踩过的坑
首轮315P/2084P1F是脏预览，不能签main；exit0收据核验不是测试绿。设today不等于设cutoff。首次642控制漏cd零测试，已另跑纠正。12K为字符，48KB为UTF-8字节；快照非锁，私有非不可变。
