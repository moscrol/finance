# e7 工程与独审封存

受测候选 `e7a6cb412865fdd189cf51a17f93622fa3d4fe55`，基线 `3bb81b9638f97b4773ce0f338df3a505b7c0162f`。文档提交不继承候选收据。所有运行已经结束，不得续跑旧批。

## 结果分账

| 范围 | 结果 | 证据入口 |
| --- | --- | --- |
| 工程0326 | 七叶exit0；Python15396P/85S/2X，collected15483、无筛选；前端六步和五个registry/ledger叶通过 | `host/gates.json`、`python-receipts/gate-Pq59hxEb/pytest.json`、完整pytest.log及XML、`frontend/` |
| QC0400宿主准入 | 首版两轴exit120/空日志；管道版各10P/6个git-init setup error。简单打印的文件/管道控制均exit0，不能泛化原120的原因。零模型消费封存 | `host/author-admission*.json`、`qc-0400/closure-unadmitted.json` |
| QC0415宿主准入 | 只增加批次父目录metadata；原路径各16P/81 deselected，沙箱预检PASS | `host/author-admission-0415.json`、各轴`sandbox-preflight-04/receipt.json` |
| QC0415独立执行 | 两轴必红控制exit1；原路径作者测试各16P。Spec四阶段完成，verdict为PASS_WITH_LIMITS且C3/C7未验证；Quality执行交付内部JSON字符串语法错误，未进入report，无有效最终verdict | `qc-0415/host-evidence-audit.json`、原始阶段目录 |
| 模型总账 | 本批57，历史74，累计131/152，剩21；所有已起shim active=0、shutdown_complete=true；无重试/续批 | `qc-0415/batch.json`、`closure-current-turn.json`及阶段controller/counts |
| 自然金融 | 未启动新批；旧NOT_PASSED不变 | 既有L6封存，不在此包补签 |
| 对象交付原型 | 离线15项对照通过，含注册工具调用；没有安装进旧批，没有模型请求，不是reviewer verdict | `host/structured-delivery-offline.json`、`structured-delivery-candidate/`、`structured-delivery-offline/` |

Spec原始四次探针执行分别为6/6、3/9、4/4、4/6子项；两个脚本exit0、两个exit1，不能把解释后的异常类型差异抹成原断言通过。Quality三组原探针中的语法错误与HTTP自检404保留，各只形成一个修正版；成功脚本6/6与7/7，另一修正版4/5且exit1。参数错位、转发桩触达与真实流式取消分开解释，宿主不代签。

工程新绿没有修复或解释旧c315的7个RAG失败与前缀共享窗覆盖失败；它们仍在旧归档。最新main远程复核仍为上述基线。未push、合main、部署或比较生产身份。

## 归档合同

`archive-manifest.json`登记530个源工件，存储2730215字节。每项分别记录源路径/源字节数/SHA256，以及存储字节数/SHA256和编码方式。大文件用确定性gzip+base64，原有行尾空白或末尾空行用可逆base64封套；不裁剪任何原件。源脚本以`.txt`保存，防止被自动发现为可执行入口。按manifest定位编码后的实际文件名。

`host/archive_e7.py.txt`保存选取与封装规则。归档含全部已执行阶段的原始事件、命令、退出码、探针源码、输入和计数；不含生成的庞大pytest夹具、虚拟环境或真实密钥。模式扫描零命中只证明所列模式未命中，不泛称全能密钥审计。

`structured-delivery-offline/valid/REPORT.md`是**宿主合成对象的工具边界测试产物**，不是Quality补交报告。旧Quality原请求SHA256为`55c59793a38004e83e01774846ff5ec2daa12d79b9abc56b2d72c173e8dc143f`，字节不变；旧字符串仍按原协议拒收。

下一批若保持每轴4/17/17/1，完整上限仍为78；剩21不足按该方案完成新的双轴审查。扩大总额度或改变方案需重新确认，不能消费到一半再借L6额度或重置历史账。对象协议也仍需新批端到端验证。
