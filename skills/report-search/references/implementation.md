# report-search 技术实现

> 本文件由 `skills/report-search/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

### Python代码要求
- 使用Python 3.7+版本
- 优先使用Python标准库和官方包
- 常用库允许使用：requests, pandas, numpy等
- 尽量减少第三方库依赖
- 代码结构清晰，模块化设计

### 配置文件要求
- 必须包含 `config.example.json` 配置文件示例
- 必须实现 `config.py` 配置管理模块
- API密钥必须从环境变量 `IWENCAI_API_KEY` 获取，不得硬编码

### 目录结构要求
```
研报搜索/
├── README.md              # 技能说明文档（中文）
├── SKILL.md              # 技能主文档（包含YAML frontmatter）
├── references/           # 参考文档目录
│   └── api.md           # 接口文档副本
└── scripts/             # 源代码目录
    ├── __main__.py      # 命令行入口点
    ├── config.py        # 配置管理模块
    ├── config.example.json # 配置文件示例
    ├── requirements.txt # Python依赖文件
    ├── setup.py         # 安装配置
    ├── research_report_search.py # 主程序文件
    ├── api_client.py    # API客户端模块
    ├── data_processor.py # 数据处理模块
    ├── cli.py           # CLI接口模块
    ├── example_usage.py # 使用示例
    └── test_basic.py    # 基础测试
```

### CLI接口要求
- 支持 `python research_report_search.py` 调用方式
- 支持 `python -m scripts.research_report_search` 调用方式
- 提供完整的命令行参数和帮助文档
- 支持多种输出格式：csv, json, text, markdown

### API透明传递与CLI数据处理区分说明
1. **API客户端模块 (api_client.py)**：
   - 严格遵守响应透明传递要求，返回完整的API响应
   - 不进行任何数据清洗、重组或业务逻辑处理
   - 仅处理网络层错误和认证问题

2. **CLI工具与数据处理模块 (cli.py, data_processor.py)**：
   - 这些模块仅用于命令行工具的后处理功能
   - 当使用CLI工具时，可以对API响应进行格式化、过滤等用户界面友好的处理
   - 但在技能被AI调用时，必须使用API客户端模块的透明传递方式

3. **重要原则**：
   - 当技能被AI代理调用时，必须生成使用api_client.py的代码，并保持响应透明传递
   - 当用户直接使用CLI工具时，可以使用data_processor.py进行后处理
   - SKILL.md中的代码示例应优先展示透明传递的API调用方式
