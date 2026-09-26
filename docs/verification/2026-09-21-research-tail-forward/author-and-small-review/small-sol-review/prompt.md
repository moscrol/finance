请独立审核固定候选，不改源码，不合并/部署/写生产、不联网金融查询，不再转委派。现有ChatGPT订阅，固定gpt-5.6-sol，不新增付费通道。

独占隔离检出 /Users/a77/fwp-wt-tail-prereq-review-0921
固定 HEAD ea5c3a94618a15e37f914c8b1a13e271875e4337
基线 f783f19c8a01fbe8d0ed70d851df7ed14598c051
PR #831，增量7文件。先验证头与干净状态，若不同停止签字。该检出只读源码；仅测试产生的忽略缓存允许写。额外探针只可放 /Users/a77/.finance-runtime/reviews/research-tail-integration-20260921/small-sol-review，不改tracked/untracked源码。

只审两份合同：
1. API测试夹具登记自己启动的Timer，任务完成从原表移除后仍等待该Timer；不扫描无关线程、不修改生产shutdown。归属登记须先于测试提交任务，退出时保留已触发回调的依赖生命周期。
2. code-map原始查询必须保留，最多多一次连字符到下划线别名查询；结果去重且总限额；原检索真失败不得冒称成功零命中，正常无匹配不应报后端不可用。别把别名改写成唯一问句。

先规格审核再质量审核，同一个独立session分两节，不冒称两位审核者。查真实消费者；设计少量正负例，测试一律 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest 。只跑定向，不跑全量。shell保持umask022，干净环境PATH=/Users/a77/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin，HOME=/Users/a77，FWP_TEST_RECEIPT=0；不碰凭证/全局设置。测试单命令最多120秒，若阻塞如实交付已有结论，不无限重试。没有自然模型金融验收不妨碍这两项离线小片，但不能外推#798/#800领域代码。

最终报告：准确HEAD/基线，具体严重度/路径行，实际命令和结果、独立动态探针/静态阅读分别标明，未验证边界、PASS/FAIL/BLOCKED。输出中给详细定位；不需要仓内handoff。完成后再核git HEAD/status，若源码dirty则不能签原提交。
