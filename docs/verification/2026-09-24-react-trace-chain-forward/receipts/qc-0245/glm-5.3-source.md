> ## Documentation Index
> Fetch the complete documentation index at: https://docs.bigmodel.cn/llms.txt
> Use this file to discover all available pages before exploring further.

# GLM-5.3

<Tip>
  GLM Coding Plan 已全量上线 GLM-5.3，编程体感较前代大幅提升50%。 [立即订阅](https://bigmodel.cn/glm-coding)
</Tip>

## 概览

GLM-5.3 是智谱最新旗舰模型，复杂软件工程与 Agent 任务能力全面进阶。它使用与 GLM-5.2 相同的基础模型——所有提升均来自后训练。与 GLM-5.2 相比，它在复杂编程和长程任务方面表现更加出色：

* **更强的编程能力**

  GLM-5.3 的编程能力大幅提升，在智谱内部 Z.ai Code Bench 上较 GLM-5.2 提升了 50%，在包括 Terminal Bench 3.0、Agents' Last Exam (CLI) 在内的公开基准测试中达到开源模型 SOTA 水平。

* **涌现的网络安全能力**

  随着后训练规模持续扩大，模型的网络安全能力以超出预期的速度提升。GLM-5.3 在漏洞发现基准 CyberGym 上取得当前最佳成绩；越深入漏洞利用链，其相较 GLM-5.2 的提升越显著，在漏洞利用类基准测试中的得分达到 GLM-5.2 的两倍以上。

[技术报告](https://z.ai/blog/glm-5.3) ｜ [体验中心](https://bigmodel.cn/trialcenter/modeltrial/text?modelCode=glm-5.3)

## 功能变更

GLM-5.3 目前仅支持处理文本模态信息，支持 1M 上下文窗口，最大输出 Tokens 为 128K。\
GLM-5.3 会始终启用思考功能，支持三个思考强度级别：`low`、`high` 和 `max`，并不再支持禁用思考功能。思考功能参数说明如下：

| Parameter          | Values               | Default   | Description                       |
| :----------------- | :------------------- | :-------- | :-------------------------------- |
| `thinking.type`    | `enabled`            | `enabled` | 仅支持开启思考，不支持禁用思考                   |
| `reasoning_effort` | `low`, `high`, `max` | `max`     | `low`-轻量推理；`high`-增强推理；`max`-深度推理 |

<Note>
  迁移提示：如果您的应用当前使用 `thinking.type: "disabled"`，请在将模型 ID 更新为 `glm-5.3` 之前，将其更改为 `enabled`，并将 `reasoning_effort` 设置为 `low`。否则，请求将失败。
</Note>

建议您在 Coding 等复杂任务上使用 `max`，示例如下：

```json theme={null}
{
  "model": "glm-5.3",
  "thinking": { "type": "enabled" },
  "reasoning_effort": "max"
}
```

关于更多深度思考能力详细介绍，请查阅文档：[深度思考](https://docs.bigmodel.cn/cn/guide/capabilities/thinking)

## 如何使用

#### **模型 API**

支持的协议与接入端点如下：

| 协议类型                      | Base URL                                 |
| :------------------------ | :--------------------------------------- |
| OpenAI Chat Completion 协议 | `https://open.bigmodel.cn/api/paas/v4`   |
| OpenAI Response 协议        | `https://open.bigmodel.cn/api/v1`        |
| Anthropic Message 协议      | `https://open.bigmodel.cn/api/anthropic` |

[↗ 接口文档](https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E5%AF%B9%E8%AF%9D%E8%A1%A5%E5%85%A8)：了解如何调用 API

<Note>
  如果您有订阅过 GLM Coding Plan（含已过期），那么暂时您只能通过 OpenAI Chat Completion 协议调用模型 API，我们将在近期迭代优化。
</Note>

#### **GLM Coding Plan**

您可以在常用的编程智能体中使用 GLM-5.3。[接入指南](/cn/coding-plan/latest-model)\
新版 GLM Coding Plan 采用基于积分的配额系统，额度公开透明。在包括周末全天在内的非高峰时段进行的模型调用仅消耗标准积分的 50%。\
立即订阅：[个人版](https://www.bigmodel.cn/glm-coding)、[团队版](https://bigmodel.cn/glm-coding?plantype=team)。

## 能力支持

* [思考模式](/cn/guide/capabilities/thinking-mode)：提供多种思考模式，覆盖不同任务需求
* [流式输出](/cn/guide/capabilities/streaming)：支持实时流式响应，提升用户交互体验
* [Function Calling](/cn/guide/capabilities/function-calling)：强大的工具调用能力，支持多种外部工具集成
* [上下文缓存](/cn/guide/capabilities/cache)：智能缓存机制，优化长对话性能
* [结构化输出](/cn/guide/capabilities/struct-output)：支持 JSON 等结构化格式输出，便于系统集成

## 详细介绍

GLM-5.3 在复杂软件工程、终端操作和更广泛的真实世界 Agent 任务上均取得显著进步。

![Description](https://cdn.bigmodel.cn/markdown/1786683281203image.png?attname=image.png)

#### 更强大的编程能力

在 GLM-5.3 的训练中，我们进一步推进了任务环境的规模化建设，使训练任务不再只是传统的编程题，而是更接近专家在真实工作中承担的完整专业工作单元。这些环境覆盖了更广泛的生产级工作流，任务设计也更加贴近工程与研究工作的实际开展方式，其中部分任务即使由经验丰富的工程师完成，也需要数天时间。

例如，在一项机器学习基础设施任务中，模型可能会获得与工程师相同的工作环境，包括计算集群、存储系统、内部文档、代码库和实验结果等资源。模型需要定位训练技术栈中的性能瓶颈，实施优化方案，运行实验，并在保证结果正确性的前提下，实现可量化的端到端加速。通过在此类高复杂度环境中训练，推动模型逐步具备端到端负责并完成复杂工作的能力，而不再依赖用户拆解问题并逐步监督执行。

随着智能体能力提升，后训练规模化的主要难点也逐渐从模型本身转移到任务环境。一个真正有价值的任务环境必须可执行、可验证，并贴近真实的专业工作；同时，我们需要的不是少量人工构建的环境，而是大规模、多样化的任务环境。为实现这一过程的规模化，我们构建了能够端到端合成任务环境的流水线，并针对部分任务进一步自动生成强化学习所需的奖励信号。研究智能体从真实工作中收集任务模式，并将其转化为可运行的长程任务环境，其中包含多步骤依赖关系和隐藏状态；随后，评审智能体会实际尝试完成每项任务，以验证任务是否确实可解。验证器在不访问参考解法的前提下生成；与此同时，系统会利用求解轨迹识别并消除奖励捷径。只有同时通过 Oracle、空操作和未解决状态检查的验证器，其生成的二值奖励信号才足够可靠，可直接用于模型训练。

GLM-5.3 延续了 GLM-5.2 中引入的强化学习策略，包括结合上下文压缩机制的 SAO，使能力增益能够在长程任务中持续体现，而非仅局限于短程任务。这些提升同时反映在编程任务和通用智能体任务中：GLM-5.3 在 Terminal-Bench 3.0 上的得分由 **4.6** 提升至 **28.3**，在 DeepSWE v1.1 上由 **46.2** 提升至 **66.9**，在 Agents' Last Exam 上由 **23.8** 提升至 **28.5**。目前，这些流水线仍需要较多人工参与。进一步提升任务环境生成与验证过程的自主化程度，是我们下一阶段的重点方向之一。

除公开基准测试外，我们还推出了内部基准 Z.ai Code Bench，用于在贴近真实用户场景的条件下评估编程智能体。该基准覆盖多种任务类别，并将智能体置于复杂的本地开发环境中。在不同推理强度档位下，我们从两个维度评估智能体：一是端到端任务完成率，二是细粒度检查项准确率。作为一项非公开基准，Z.ai Code Bench 还能降低公开测试集污染带来的风险，从而更准确地反映模型在真实用户场景中的使用体验。

![Description](https://cdn.bigmodel.cn/markdown/1786683377150image.png?attname=image.png)

如图所示，GLM-5.3 在能力表现和 Token 效率上均取得了提升。在所有推理强度档位下，GLM-5.3 的智能体编程表现均显著优于 GLM-5.2，同时消耗更少的输出 Token。在 Max 档位下，GLM-5.3 的准确率达到 **34.5%**，每项任务平均输出约 7.5 万 Token；相比之下，GLM-5.2 的准确率为 **23.4%**，平均输出约 9.6 万 Token。与闭源模型的对比也呈现出相同趋势：在 High 档位下，GLM-5.3 在每项任务平均输出约 5 万 Token 的情况下，准确率达到 **31.4%**，超过 Claude Opus 4.8 在每项任务平均输出约 12 万 Token 时取得的 **29.5%**。GLM-5.3 与 Claude Fable 5 仍存在差距，后者在 Max 档位下的准确率达到 **39.5%**。

#### 涌现的网络安全能力

在后训练阶段，我们将漏洞发现相关的数据与环境纳入训练体系。我们原本预计，这会提升模型发现漏洞并对其进行分析推理的能力。令人意外的是，随着训练规模持续扩大，这项能力也迅速演进。GLM-5.3 不仅更擅长识别孤立的安全缺陷，还开始能够跨越漏洞利用的多个阶段进行推理，形成连贯、完整的漏洞利用链方案。

我们通过三个分别覆盖漏洞分析与利用不同阶段的基准测试，对 GLM-5.3 进行了评估。

![Description](https://cdn.bigmodel.cn/markdown/1786683405531image.png?attname=image.png)

在 CyberGym 上，模型需要从白盒源代码出发，通过触发程序异常来识别并验证漏洞。GLM-5.3 得分达到 **84.5%**，较 GLM-5.2 的 **77.2%** 明显提升，并取得该基准当前最佳成绩，超过 Mythos 5 的 **83.8%** 和 GPT-5.6 Sol 的 **83.6%**。在 ExploitBench 上，模型需要对真实漏洞及其利用方式进行更深入的推理。GLM-5.3 得分达到 **54.4%**，较 GLM-5.2 的 **24.4%** 提升一倍以上；作为对比，Mythos 5 和 GPT-5.6 Sol 的得分分别为 **78.0%** 和 **76.5%**。在 ExploitGym 上，评测关注模型在经过时间归一化的预算下能够完成多少项漏洞利用任务。GLM-5.3 在两小时内完成 105 项任务、六小时内完成 130 项任务，显著高于 GLM-5.2 的 29 项和 39 项。Mythos 5 仍保持明显领先，两小时和六小时内分别完成 181 项和 247 项任务。

三个基准呈现出一致的趋势：基准测试覆盖的漏洞利用链阶段越深入，GLM-5.3 相比 GLM-5.2 的提升就越显著；与此同时，与闭源前沿模型之间的差距也越大。换言之，当前差距最大的方向，恰恰也是我们能力增长最快的方向。

随后，我们进一步测试这些能力能否从受控基准评测迁移到真实场景。自 GLM-5.2 起，我们便与中国多家安全团队合作，使用模型对真实代码库开展安全测试。经专家复核、筛选与去重，模型在 **269** 个项目中共发现 **2,436** 个漏洞，其中包括 **1,097** 个中高危漏洞。这些漏洞广泛分布于系统内核、操作系统、浏览器引擎、开源基础设施、Web 应用和网络协议等领域。许多漏洞此前已潜藏数年甚至数十年而未被发现，其中存在时间最长的漏洞已在代码库中潜藏约 40 年。

这项工作进一步发展为一项持续开展的漏洞披露计划。我们建立了 Z.ai 安全漏洞披露台账，用于公开记录相关漏洞在披露流程中的进展。随着新漏洞陆续完成审核并推进披露，该台账会持续更新，并明确区分已经公开的漏洞与仍处于协调披露阶段的漏洞。对于已披露漏洞，台账会记录受影响项目、漏洞严重等级、对应的 CVE 编号（如有），以及该漏洞在代码库中潜藏的时间等信息。

## 调用示例

以下是完整的调用示例，帮助您快速上手 GLM-5.3 模型。

<Note>
  GLM-5.3 始终启用思考功能，`reasoning_effort` 支持 `low`、`high`、`max` 三档（默认 `max`），不再支持 `thinking.type: "disabled"`。从 GLM-5.2 迁移时，请将 `disabled` 改为 `enabled`，并按需设置 `reasoning_effort`。
</Note>

<Tabs>
  <Tab title="cURL">
    **基础调用**

    ```bash theme={null}
    curl -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -d '{
      "model": "glm-5.3",
      "messages": [
        {
          "role": "system",
          "content": "你是一名资深的全栈软件工程师，擅长前端开发、后端架构设计以及现代 Web 技术栈"
        },
        {
          "role": "user",
          "content": "帮我设计并编写一个个人博客网站，包含首页、文章列表、文章详情页，使用 React + Node.js 技术栈"
        }
      ],
      "thinking": {
        "type": "enabled"
      },
      "reasoning_effort": "max",
      "max_tokens": 65536,
      "temperature": 1.0
    }'
    ```

    **流式调用**

    ```bash theme={null}
    curl -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -d '{
      "model": "glm-5.3",
      "messages": [
        {
          "role": "system",
          "content": "你是一名资深的全栈软件工程师，擅长前端开发、后端架构设计以及现代 Web 技术栈"
        },
        {
          "role": "user",
          "content": "帮我设计并编写一个个人博客网站，包含首页、文章列表、文章详情页，使用 React + Node.js 技术栈"
        }
      ],
      "thinking": {
        "type": "enabled"
      },
      "reasoning_effort": "max",
      "stream": true,
      "max_tokens": 65536,
      "temperature": 1.0
    }'
    ```
  </Tab>

  <Tab title="Python">
    **安装 SDK**

    ```bash theme={null}
    # 安装最新版本
    pip install zai-sdk
    # 或指定版本
    pip install zai-sdk==0.2.3
    ```

    **验证安装**

    ```python theme={null}
    import zai
    print(zai.__version__)
    ```

    **基础调用**

    ```python theme={null}
    from zai import ZhipuAiClient

    client = ZhipuAiClient(api_key="YOUR_API_KEY")  # 请填写您自己的 API Key

    response = client.chat.completions.create(
        model="glm-5.3",
        messages=[
            {"role": "system", "content": "你是一名资深的全栈软件工程师，擅长前端开发、后端架构设计以及现代 Web 技术栈"},
            {"role": "user", "content": "帮我设计并编写一个个人博客网站，包含首页、文章列表、文章详情页，使用 React + Node.js 技术栈"}
        ],
        thinking={
            "type": "enabled"    # GLM-5.3 始终启用思考，仅支持 enabled
        },
        reasoning_effort="max",  # 推理程度：low / high / max（默认 max）
        max_tokens=65536,          # 最大输出 tokens
        temperature=1.0           # 控制输出的随机性
    )

    # 获取完整回复
    print(response.choices[0].message)
    ```

    **流式调用**

    ```python theme={null}
    from zai import ZhipuAiClient

    client = ZhipuAiClient(api_key="YOUR_API_KEY")  # 请填写您自己的 API Key

    response = client.chat.completions.create(
        model="glm-5.3",
        messages=[
            {"role": "system", "content": "你是一名资深的全栈软件工程师，擅长前端开发、后端架构设计以及现代 Web 技术栈"},
            {"role": "user", "content": "帮我设计并编写一个个人博客网站，包含首页、文章列表、文章详情页，使用 React + Node.js 技术栈"}
        ],
        thinking={
            "type": "enabled"    # GLM-5.3 始终启用思考，仅支持 enabled
        },
        reasoning_effort="max",  # 推理程度：low / high / max（默认 max）
        stream=True,              # 启用流式输出
        max_tokens=65536,          # 最大输出tokens
        temperature=1.0           # 控制输出的随机性
    )

    # 流式获取回复
    for chunk in response:
        if chunk.choices[0].delta.reasoning_content:
            print(chunk.choices[0].delta.reasoning_content, end='', flush=True)

        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='', flush=True)
    ```
  </Tab>

  <Tab title="Java">
    **安装 SDK**

    **Maven**

    ```xml theme={null}
    <dependency>
        <groupId>ai.z.openapi</groupId>
        <artifactId>zai-sdk</artifactId>
        <version>0.3.5</version>
    </dependency>
    ```

    **Gradle (Groovy)**

    ```groovy theme={null}
    implementation 'ai.z.openapi:zai-sdk:0.3.5'
    ```

    **基础调用**

    ```java theme={null}
    import ai.z.openapi.ZhipuAiClient;
    import ai.z.openapi.service.model.ChatCompletionCreateParams;
    import ai.z.openapi.service.model.ChatCompletionResponse;
    import ai.z.openapi.service.model.ChatMessage;
    import ai.z.openapi.service.model.ChatMessageRole;
    import ai.z.openapi.service.model.ChatThinking;
    import java.util.Arrays;

    public class BasicChat {
        public static void main(String[] args) {
            // 初始化客户端
            ZhipuAiClient client = ZhipuAiClient.builder().ofZHIPU()
                .apiKey("YOUR_API_KEY")
                .build();

            // 创建聊天完成请求
            ChatCompletionCreateParams request = ChatCompletionCreateParams.builder()
                .model("glm-5.3")
                .messages(Arrays.asList(
                    ChatMessage.builder()
                        .role(ChatMessageRole.SYSTEM.value())
                        .content("你是一名资深的全栈软件工程师，擅长前端开发、后端架构设计以及现代 Web 技术栈")
                        .build(),
                    ChatMessage.builder()
                        .role(ChatMessageRole.USER.value())
                        .content("帮我设计并编写一个个人博客网站，包含首页、文章列表、文章详情页，使用 React + Node.js 技术栈")
                        .build()
                ))
                .thinking(ChatThinking.builder().type("enabled").build())
                .reasoningEffort("max")
                .maxTokens(65536)
                .temperature(1.0f)
                .build();

            // 发送请求
            ChatCompletionResponse response = client.chat().createChatCompletion(request);

            // 获取回复
            if (response.isSuccess()) {
                Object reply = response.getData().getChoices().get(0).getMessage();
                System.out.println("AI 回复: " + reply);
            } else {
                System.err.println("错误: " + response.getMsg());
            }
        }
    }
    ```

    **流式调用**

    ```java theme={null}
    import ai.z.openapi.ZhipuAiClient;
    import ai.z.openapi.service.model.ChatCompletionCreateParams;
    import ai.z.openapi.service.model.ChatCompletionResponse;
    import ai.z.openapi.service.model.ChatMessage;
    import ai.z.openapi.service.model.ChatMessageRole;
    import ai.z.openapi.service.model.ChatThinking;
    import ai.z.openapi.service.model.Delta;
    import java.util.Arrays;

    public class StreamingChat {
        public static void main(String[] args) {
            // 初始化客户端
            ZhipuAiClient client = ZhipuAiClient.builder().ofZHIPU()
                .apiKey("YOUR_API_KEY")
                .build();

            // 创建流式聊天完成请求
            ChatCompletionCreateParams request = ChatCompletionCreateParams.builder()
                .model("glm-5.3")
                .messages(Arrays.asList(
                    ChatMessage.builder()
                        .role(ChatMessageRole.SYSTEM.value())
                        .content("你是一名资深的全栈软件工程师，擅长前端开发、后端架构设计以及现代 Web 技术栈")
                        .build(),
                    ChatMessage.builder()
                        .role(ChatMessageRole.USER.value())
                        .content("帮我设计并编写一个个人博客网站，包含首页、文章列表、文章详情页，使用 React + Node.js 技术栈")
                        .build()
                ))
                .thinking(ChatThinking.builder().type("enabled").build())
                .reasoningEffort("max")
                .stream(true)  // 启用流式输出
                .maxTokens(65536)
                .temperature(1.0f)
                .build();

            ChatCompletionResponse response = client.chat().createChatCompletion(request);

            if (response.isSuccess()) {
                response.getFlowable().subscribe(
                    // Process streaming message data
                    data -> {
                        if (data.getChoices() != null && !data.getChoices().isEmpty()) {
                            Delta delta = data.getChoices().get(0).getDelta();
                            System.out.print(delta + "\n");
                        }
                    },
                    // Process streaming response error
                    error -> System.err.println("\nStream error: " + error.getMessage()),
                    // Process streaming response completion event
                    () -> System.out.println("\nStreaming response completed")
                );
            } else {
                System.err.println("Error: " + response.getMsg());
            }
        }
    }
    ```
  </Tab>

  <Tab title="Python（旧）">
    **更新 SDK 至 2.1.5.20250726**

    ```bash theme={null}
    # 安装最新版本
    pip install zhipuai

    # 或指定版本
    pip install zhipuai==2.1.5.20250726
    ```

    **基础调用**

    ```python theme={null}
    from zhipuai import ZhipuAI

    client = ZhipuAI(api_key="YOUR_API_KEY")  # 请填写您自己的 API Key

    response = client.chat.completions.create(
        model="glm-5.3",
        messages=[
            {"role": "system", "content": "你是一名资深的全栈软件工程师，擅长前端开发、后端架构设计以及现代 Web 技术栈"},
            {"role": "user", "content": "帮我设计并编写一个个人博客网站，包含首页、文章列表、文章详情页，使用 React + Node.js 技术栈"}
        ],
        thinking={
            "type": "enabled"
        },
        max_tokens=65536,
        temperature=1.0
    )

    # 获取完整回复
    print(response.choices[0].message)
    ```

    **流式调用**

    ```python theme={null}
    from zhipuai import ZhipuAI

    client = ZhipuAI(api_key="YOUR_API_KEY")  # 请填写您自己的 API Key

    response = client.chat.completions.create(
        model="glm-5.3",
        messages=[
            {"role": "system", "content": "你是一名资深的全栈软件工程师，擅长前端开发、后端架构设计以及现代 Web 技术栈"},
            {"role": "user", "content": "帮我设计并编写一个个人博客网站，包含首页、文章列表、文章详情页，使用 React + Node.js 技术栈"}
        ],
        thinking={
            "type": "enabled"
        },
        stream=True,              # 启用流式输出
        max_tokens=65536,
        temperature=1.0
    )

    # 流式获取回复
    for chunk in response:
        if chunk.choices[0].delta.reasoning_content:
            print(chunk.choices[0].delta.reasoning_content, end='', flush=True)

        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='', flush=True)
    ```
  </Tab>
</Tabs>
