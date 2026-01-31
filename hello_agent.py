import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

# ────────────────────────────────────────────────
# 环境变量 & 日志
# ────────────────────────────────────────────────

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path, override=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-5s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────
# 配置类
# ────────────────────────────────────────────────

class LLMConfig:
    """LLM 配置管理"""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openrouter")
        self.api_key = os.getenv("LLM_API_KEY")
        self.model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.4"))
        self.base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        self.max_history = int(os.getenv("MAX_HISTORY", "20"))

    def validate(self) -> bool:
        if not self.api_key:
            logger.error("缺少 LLM_API_KEY 环境变量")
            return False
        return True

    def __str__(self):
        return f"{self.provider} / {self.model} (temp={self.temperature})"


# ────────────────────────────────────────────────
# 提示词
# ────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一个具备计算能力的 AI 助手。
当用户要求进行数学运算时，请调用 calculate 工具。
计算完成后，请根据工具返回的结果给用户最终答案。

全程用中文回复。"""


def create_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("messages"),
    ])


# ────────────────────────────────────────────────
# 工具定义
# ────────────────────────────────────────────────
@tool
def calculate(expression: str) -> str:
    """执行数学计算。注意：sin/cos/tan 默认使用弧度。
    如需计算角度，请使用圆周率pi配合计算"""
    try:
        logger.info(f"调用工具：传入表达式{expression}")
        # 安全起见，只允许基本的数学运算
        allowed_names = {"__builtins__": {}}
        allowed_names.update({
            "sin": __import__("math").sin,
            "cos": __import__("math").cos,
            "tan": __import__("math").tan,
            "sqrt": __import__("math").sqrt,
            "pi": __import__("math").pi,  # 允许使用圆周率
            # 可以继续加其他函数
        })
        result = eval(expression, allowed_names)
        logger.info(result)
        return str(result)
    except Exception as e:
        return f"计算错误：{str(e)}"


# ────────────────────────────────────────────────
# 初始化
# ────────────────────────────────────────────────

config = LLMConfig()
if not config.validate():
    raise RuntimeError("LLM 配置不完整，请检查 .env 文件")

logger.info(f"加载模型配置：{config}")

llm = ChatOpenAI(
    base_url=config.base_url,
    api_key=config.api_key,
    model=config.model,
    temperature=config.temperature,
)
# 在初始化 llm 之后，加这一行
# 可以以后加更多工具
tools = [calculate]
llm_with_tools = llm.bind_tools(tools)

prompt = create_prompt()
llm_chain = prompt | llm_with_tools


# ────────────────────────────────────────────────
# 代理节点
# ────────────────────────────────────────────────

def agent(state: MessagesState) -> dict:
    """核心代理节点"""
    try:
        response = llm_chain.invoke({"messages": state["messages"]})
        logger.debug(f"生成回复，长度：{len(response.content)}")
        return {"messages": [response]}
    except Exception as e:
        logger.error(f"代理执行失败: {str(e)}")
        error_msg = AIMessage(content=f"抱歉，发生内部错误：{str(e)}\n请稍后再试。")
        return {"messages": [error_msg]}


# ────────────────────────────────────────────────
# 构建图
# ────────────────────────────────────────────────

def build_graph_with_tool():
    workflow = StateGraph(state_schema=MessagesState) # type: ignore
    # 工具执行节点（LangGraph 官方预置）
    tool_node = ToolNode(tools=tools)
    workflow.add_node("agent", agent) # type: ignore
    workflow.add_node("tools", tool_node)
    # 条件边：由 tools_condition 自动判断
    # 如果最后一条消息是 AIMessage 且有 tool_calls，就去 tools 节点
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        tools_condition,  # 官方工具条件判断函数
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")  # 工具执行完回到 agent

    return workflow.compile()


graph = build_graph_with_tool()
logger.info("LangGraph 已编译完成")


# ────────────────────────────────────────────────
# 交互函数
# ────────────────────────────────────────────────

def test_interactive_chat(verbose: bool = True):
    """
    多轮对话模式（带上下文记忆）
    支持命令：
      /clear, /reset   → 清空历史
      /help            → 显示帮助
      exit/quit/q      → 退出
    """
    print("\n" + "═" * 70)
    print("🤖 AI 代理对话模式 已启动")
    print(f"  模型：{config.model}")
    print(f"  温度：{config.temperature}")
    print(f"  最大历史：{config.max_history} 条")
    print("  命令：/help 查看帮助   exit / quit / q 退出")
    print("═" * 70 + "\n")

    messages_history = []

    while True:
        try:
            user_input = input("你: ").strip()
            if not user_input:
                continue

            # 特殊命令处理
            cmd = user_input.lower()
            if cmd in ['exit', 'quit', 'q']:
                print("\n👋 对话结束，欢迎下次使用！\n")
                break

            if cmd in ['/clear', '/reset']:
                messages_history.clear()
                print("🧹 对话历史已清空\n")
                continue

            if cmd == '/help':
                print("""
可用命令：
  /clear 或 /reset    清空当前对话历史
  /help               显示此帮助
  exit / quit / q     退出对话
                """.strip())
                continue

            # 正常用户输入
            user_msg = HumanMessage(content=user_input)
            messages_history.append(user_msg)

            # 限制历史长度
            if len(messages_history) > config.max_history:
                messages_history = messages_history[-config.max_history:]

            # 调用代理
            result = graph.invoke({"messages": messages_history}) # type: ignore
            # logger.info(f"代理返回结果: {result['messages']}")
            ai_msg = result["messages"][-1]

            print(f"AI : {ai_msg.content}\n")

            # 加入 AI 回复到历史
            messages_history.append(ai_msg)

            # 显示历史（调试用）
            if verbose and len(messages_history) > 2:
                print("[最近消息历史]")
                for i, msg in enumerate(messages_history[-6:], len(messages_history) - 5):
                    role = "👤 你" if isinstance(msg, HumanMessage) else "🤖 AI"
                    preview = msg.content[:60].replace("\n", " ").strip()
                    if len(msg.content) > 60:
                        preview += "..."
                    print(f"  {i:2d}  {role}: {preview}")
                print("─" * 70 + "\n")

        except KeyboardInterrupt:
            print("\n⚠️  对话已手动中断\n")
            break
        except Exception as e:
            print(f"❌ 发生错误：{str(e)}\n")
            logger.exception("交互循环异常")


# ────────────────────────────────────────────────
# 主程序
# ────────────────────────────────────────────────

if __name__ == "__main__":
    test_interactive_chat(verbose=True)
    # 如果想单次测试，可以改用：
    # response = graph.invoke({"messages": [HumanMessage(content="你好")]})["messages"][-1].content
    # print(response)
