本次 Spec 结论为 FAIL。两份原始失败 JUnit 及协调侧红灯 JUnit 的 mock 断言展开了宿主环境，因此只把脱敏副本放入 sanitized/；原件留在外部受限目录，原始/脱敏 SHA-256 见 redaction-manifest.json。其余文件按原字节保存。

原探针中要求旧 FileNotFoundError 的部分只诊断修前行为，不适合作为修后通过条件。consumer-red-green/ 副本仅移除此诊断控制，两个变异输入和所有消费者断言保持；bc43ece9 上仍为2F。该适配独立记载于 adaptation.json。后续复验使用最小进程环境，避免断言输出包含凭据。
