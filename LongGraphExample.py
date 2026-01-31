import os
import operator
from pathlib import Path
from dotenv import load_dotenv
from typing import Literal, Annotated
from typing_extensions import TypedDict

from langchain.tools import tool
from langchain_openai import ChatOpenAI  # 更改为更通用的 ChatOpenAI
from langchain.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END

# ────────────────────────────────────────────────
# 1. 配置环境与模型
# ────────────────────────────────────────────────

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path, override=True)

# 请替换为你的 OpenRouter 或 OpenAI API Key
os.environ["OPENAI_API_KEY"] = os.getenv("LLM_API_KEY")
os.environ["OPENAI_API_BASE"] = os.getenv("LLM_BASE_URL")

# 初始化模型 (以兼容 OpenRouter 的方式)
model = ChatOpenAI(
    model="deepseek/deepseek-chat",  # 或者你定义的模型 ID
    temperature=0,
)


# ────────────────────────────────────────────────
# 2. 定义工具 (Tools)
# ────────────────────────────────────────────────

@tool
def multiply(a: int, b: int) -> int:
    """Multiply `a` and `b`."""
    print(f"调用工具：Multiplying {a} and {b}")
    return a * b


@tool
def add(a: int, b: int) -> int:
    """Adds `a` and `b`."""
    print(f"调用工具：Adding {a} and {b}")
    return a + b


@tool
def divide(a: int, b: int) -> float:
    """Divide `a` and `b`."""
    return a / b


tools = [add, multiply, divide]
tools_by_name = {tool.name: tool for tool in tools}
model_with_tools = model.bind_tools(tools)


# ────────────────────────────────────────────────
# 3. 定义状态与节点逻辑
# ────────────────────────────────────────────────

class MessagesState(TypedDict):
    # Annotated[..., operator.add] 确保新消息被追加到列表末尾而不是覆盖
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


def llm_call(state: MessagesState):
    """LLM 决策节点：决定是否调用工具"""
    response = model_with_tools.invoke(
        [SystemMessage(content="You are a helpful assistant tasked with performing arithmetic.")]
        + state["messages"]
    )
    return {
        "messages": [response],
        "llm_calls": state.get('llm_calls', 0) + 1
    }


def tool_node(state: MessagesState):
    """工具执行节点：执行具体的函数调用"""
    result = []
    # 遍历最后一条 AI 消息中的所有工具调用请求
    for tool_call in state["messages"][-1].tool_calls:
        tool_obj = tools_by_name[tool_call["name"]]
        observation = tool_obj.invoke(tool_call["args"])
        result.append(ToolMessage(content=str(observation), tool_call_id=tool_call["id"]))
    return {"messages": result}


def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    """条件边逻辑：判断是去执行工具还是结束"""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"
    return END


# ────────────────────────────────────────────────
# 4. 构建并编译图 (Graph)
# ────────────────────────────────────────────────

agent_builder = StateGraph(MessagesState)

agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)

agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "tool_node": "tool_node",
        END: END
    }
)
agent_builder.add_edge("tool_node", "llm_call")

agent = agent_builder.compile()

# ────────────────────────────────────────────────
# 5. 运行示例
# ────────────────────────────────────────────────

if __name__ == "__main__":
    # 输入指令
    input_state = {"messages": [HumanMessage(content="Add 3 and 4, then multiply the result by 10.")]}

    # 执行图
    final_state = agent.invoke(input_state)

    # 打印完整的对话链路
    print("\n--- 对话流结果 ---")
    for m in final_state["messages"]:
        m.pretty_print()

    # print(f"\n最终回答: {final_state['messages'][-1].content}")
    print(f"\n总计调用 LLM 次数: {final_state['llm_calls']}")