"""核心运行时模块：负责环境加载、LLM 配置与 LangGraph 构建装配。"""

import logging
import os
from pathlib import Path
from typing import Callable, Sequence, Tuple

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """你是一个具备计算、查时间、查天气能力的 AI 助手。

工具使用规则：
- 数学运算 → 调用 calculate 工具
- 查询时间 → 调用 get_current_time 工具
- 查询天气 → 调用 get_weather 工具

重要提示：
1. 如果需要多步操作（如先查天气再计算），请按顺序调用工具
2. 使用上一个工具的返回结果作为下一个工具的输入
3. 对于天气查询，必须调用 get_weather 工具后再回复
4. 未指定城市时直接用 city='成都'，不要询问用户
5. 全程用中文回复"""


def load_project_env() -> None:
    """加载项目根目录 .env。"""
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path, override=True)


class LLMConfig:
    """LLM 配置管理。"""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openrouter")
        self.api_key = os.getenv("LLM_API_KEY")
        self.model = os.getenv("LLM_MODEL", "qwen-flash")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.4"))
        self.base_url = os.getenv(
            "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.max_history = int(os.getenv("MAX_HISTORY", "20"))

    def validate(self) -> bool:
        if not self.api_key:
            logger.error("缺少 LLM_API_KEY 环境变量")
            return False
        return True

    def __str__(self) -> str:
        return f"{self.provider} / {self.model} (temp={self.temperature})"


def create_prompt(system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("messages"),
        ]
    )


def create_llm(config: LLMConfig) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        temperature=config.temperature,
    )


def create_agent_node(llm_chain) -> Callable[[MessagesState], dict]:
    """创建 agent 节点函数。"""

    def agent(state: MessagesState) -> dict:
        try:
            response = llm_chain.invoke({"messages": state["messages"]})
            logger.debug(f"生成回复，长度：{len(response.content)}")
            return {"messages": [response]}
        except Exception as exc:
            logger.error(f"代理执行失败: {str(exc)}")
            error_msg = AIMessage(content=f"抱歉，发生内部错误：{str(exc)}\n请稍后再试。")
            return {"messages": [error_msg]}

    return agent


# 需要人工确认才能执行的工具名集合
TOOLS_REQUIRING_CONFIRMATION = {"calculate"}


def _route_tools(state: MessagesState):
    """将 calculate 路由到独立节点（可插入 interrupt），其他工具直接执行。"""
    last = state["messages"][-1]
    if not getattr(last, "tool_calls", None):
        return END
    tool_name = last.tool_calls[0]["name"]
    return "calculate" if tool_name in TOOLS_REQUIRING_CONFIRMATION else "tools"


def build_agent_graph(
    config: LLMConfig,
    tools: Sequence[BaseTool],
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> StateGraph:
    """构建带工具调用能力的 LangGraph 图。

    图结构：
      START → agent → [_route_tools] → calculate → agent → END
                                     ↘ tools    → agent
                                     ↘ END
    """
    tool_list = list(tools)
    llm = create_llm(config)
    llm_with_tools = llm.bind_tools(tool_list)
    prompt = create_prompt(system_prompt)
    llm_chain = prompt | llm_with_tools
    agent = create_agent_node(llm_chain)

    confirm_tools = [t for t in tool_list if t.name in TOOLS_REQUIRING_CONFIRMATION]
    auto_tools = [t for t in tool_list if t.name not in TOOLS_REQUIRING_CONFIRMATION]

    workflow = StateGraph(state_schema=MessagesState)  # type: ignore
    workflow.add_node("agent", agent)  # type: ignore
    workflow.add_node("calculate", ToolNode(tools=confirm_tools))
    workflow.add_node("tools", ToolNode(tools=auto_tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        _route_tools,
        {"calculate": "calculate", "tools": "tools", END: END},
    )
    workflow.add_edge("calculate", "agent")
    workflow.add_edge("tools", "agent")
    return workflow


def create_default_config() -> LLMConfig:
    """加载环境变量并返回默认配置。"""
    load_project_env()
    config = LLMConfig()
    if not config.validate():
        raise RuntimeError("LLM 配置不完整，请检查 .env 文件")
    return config


def create_configured_graph(
    tools: Sequence[BaseTool],
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> Tuple[LLMConfig, StateGraph]:
    """一键创建默认配置和已装配工具的图。"""
    config = create_default_config()
    graph = build_agent_graph(config=config, tools=tools, system_prompt=system_prompt)
    return config, graph
