"""Loop 底座：agent 编排、provider 适配、子研究。

这里是可替换的固定底座，与领域层（intelligence/services/）单向解耦：

    services/**  不得 import  runtime.*
    runtime/**   可以 import  services/**（正常方向）

新增模块的判别口径：
  做 IO / 调模型 / 起子进程 / 管预算  →  runtime/
  只声明"长什么样"、纯变换、Protocol 与数据类  →  services/
"""
