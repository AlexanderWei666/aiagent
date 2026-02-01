# AI Agent 学习笔记 - Day 1 (2026-01-31)

## 目标
快速验证一个最简 LangGraph 对话 demo，建立“代理 = LLM + 状态 + 图结构”的直观感受

## 环境搭建

- Miniconda + Python 3.12.3 (ARM64)
- 创建独立环境 py312 并设为默认激活

```bash
# 1. 创建环境
conda create -n py312 python=3.12 -y

# 2. 禁止 base 自动激活
conda config --set auto_activate_base false

# 3. 写入 .zprofile 自动激活 py312
echo -e "\n# Conda default environment\nconda activate py312" >> ~/.zprofile
source ~/.zprofile

# 4. 验证
python --version

# 5.安装依赖
python -m pip install -U \
    langgraph \
    langchain \
    langchain-core \
    langchain-openai \
    langchain-community \
    python-dotenv \
    httpx
```

- 环境优化：切换到 `libmamba` 求解器，将默认 Python 改为 3.12，引入`conda-forge`

```shell
conda update -n base conda -y
conda install -n base conda-libmamba-solver -y
conda config --set solver libmamba
conda config --add channels conda-forge
conda config --set channel_priority strict
```

- LLM 选择：qwen-flash,理由，速度快，免费

## 代码实现
- 文件：`hello_agent.py`
- 关键代码片段：

```python
#构建prompt
def create_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("messages"),
    ])

#构建带prompt的llm实体
llm = ChatOpenAI(
    base_url=config.base_url,
    api_key=config.api_key,
    model=config.model,
    temperature=config.temperature,
)
prompt = create_prompt()
llm_chain = prompt | llm

#构建代理节点
def agent(state: MessagesState) -> dict:
    """核心代理节点"""
    try:
        response = llm_chain.invoke(state["messages"])
        logger.debug(f"生成回复，长度：{len(response.content)}")
        return {"messages": [response]}
    except Exception as e:
        logger.error(f"代理执行失败: {str(e)}")
        error_msg = AIMessage(content=f"抱歉，发生内部错误：{str(e)}\n请稍后再试。")
        return {"messages": [error_msg]}

#构建图      
def build_graph():
    workflow = StateGraph(state_schema=MessagesState)
    workflow.add_node("agent", agent)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)
    return workflow.compile()
graph = build_graph()

# 循环调用代理，并加入上下文
result = graph.invoke({"messages": messages_history})
ai_msg = result["messages"][-1]
messages_history.append(ai_msg)
```

- 运行输出：

```bash
❯ python hello_agent.py
2026-01-31 16:42:03 | INFO  | 加载模型配置：openrouter / deepseek/deepseek-chat (temp=0.4)
2026-01-31 16:42:03 | INFO  | LangGraph 已编译完成

══════════════════════════════════════════════════════════════════════
🤖 AI 代理对话模式 已启动
  模型：deepseek/deepseek-chat
  温度：0.4
  最大历史：20 条
  命令：/help 查看帮助   exit / quit / q 退出
══════════════════════════════════════════════════════════════════════

你: 你好啊
2026-01-31 16:42:19 | INFO  | HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
AI : <thinking>
1. 理解用户意图：用户在进行简单的问候
2. 需要的信息/工具：无需额外信息
3. 我的推理步骤：作为AI助手，应该礼貌回应问候
</thinking>

<final_answer>
您好！我是AI助手，很高兴为您服务。请问有什么可以帮您的吗？
</final_answer>

你: 
```

## 问题 & 解决

- **ModuleNotFoundError: No module named 'langgraph'** 
  - 原因：pip 装到了错的环境
  - 解决：`conda activate py312 + python -m pip install ...`
- **多轮对话失忆** 
  - 原因：每次invoke只传当前消息
  - 解决：外部维护`messages_history`列表，完整传入


## 关键概念总结
1. **ChatPromptTemplate + MessagesPlaceholder**

   用来构建带历史消息的结构化提示模板，是控制输出格式的关键

2. **ChatOpenAI + LCEL 链式调用（prompt | llm）**

   LangChain 的现代写法，简洁且可组合。

3. **MessagesState**

   LangGraph 内置的状态类型，自动处理 messages 追加，比自定义 TypedDict 更简洁。

4. **agent 节点**

   代理的核心逻辑：接收 state → 调用 LLM → 返回更新后的 state。

5. **StateGraph & compile**

   定义图结构（节点 + 边），compile 后得到可调用的 graph 对象。

6. **上下文记忆的真相**

   LangGraph invoke是无状态的，必须自己每次传入完整消息历史。

## 心得 & 最大收获

- 第一次感受到“写 AI 代理”和“写普通函数”很像（节点 = 函数，状态 = 参数）
- 明白了为什么很多人说 LangGraph 比老 LangChain AgentExecutor 更灵活（但也更需要手动管理状态）
- 环境配置虽然花了时间，但一旦通了，后续开发效率很高
- 最大的惊喜：跑通多轮对话后，真的有“它在和我聊天”的感觉

# AI Agent 学习笔记 - Day 2 (2026-02-01)

## 今日目标
让代理具备工具调用能力，实现基础 ReAct 循环

## 学习内容概要

1. 核心概念
   - Tool / Tool calling / function calling
   - ReAct 工作流（Reason → Act → Observe → Reason ...）
   - LangGraph 中的工具支持：ToolNode、tools_condition

2. 第一个工具实现
   - 工具名称：`calculate`
   - 定义方式：@tool 装饰器
   - 代码片段：

     ```python
     @tool
     def calculate(expression: str) -> str:
         """描述..."""
         ...