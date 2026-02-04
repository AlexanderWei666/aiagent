import logging
import os
import requests
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import MessagesState, StateGraph, START, END
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
        self.model = os.getenv("LLM_MODEL", "qwen-flash")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.4"))
        self.base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
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
        logger.info(f"调用工具：传入表达式 {expression}")
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
        logger.info(f"计算结果：{result}")
        return str(result)
    except Exception as e:
        logger.error(f"计算错误：{str(e)}")
        return f"计算错误：{str(e)}"

@tool
def get_current_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间，格式化输出"""
    try:
        logger.info(f"调用工具：获取当前时间，格式化输出 {format_str}")
        now = datetime.now()
        return now.strftime(format_str)
    except Exception as e:
        logger.error(f"时间格式错误：{str(e)}")
        return f"时间格式错误：{str(e)}"

@tool
def get_weather(city: str = "成都") -> str:
    """获取指定城市天气，默认成都"""
    try:
        logger.info(f"调用工具：获取指定城市 {city} 天气，默认成都")
        # 城市经纬度映射
        city_coords = {
            "成都": {"lat": 30.57, "lon": 104.06},
            "北京": {"lat": 39.90, "lon": 116.40},
            "上海": {"lat": 31.23, "lon": 121.47},
            "广州": {"lat": 23.12, "lon": 113.26},
            "深圳": {"lat": 22.54, "lon": 114.05},
            "杭州": {"lat": 30.27, "lon": 120.15},
            "西安": {"lat": 34.26, "lon": 108.94},
            "重庆": {"lat": 29.56, "lon": 106.55},
            "武汉": {"lat": 30.59, "lon": 114.30},
            "南京": {"lat": 32.04, "lon": 118.79}
        }
        
        # 获取城市坐标，如果不在列表中则默认成都
        coords = city_coords.get(city, city_coords["成都"])
        
        # open-meteo 免费 API，无需 key
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&current=temperature_2m,weathercode&timezone=Asia/Shanghai"
        resp = requests.get(url, timeout=5).json()
        temp = resp["current"]["temperature_2m"]
        weather_code = resp["current"]["weathercode"]
        
        # 天气代码映射
        weather_map = {
            0: "晴朗",
            1: "多云",
            2: "阴天",
            3: "小雨",
            4: "中雨",
            5: "大雨",
            6: "雪",
            7: "雾",
            8: "雷阵雨",
            9: "冰雹"
        }
        
        weather_desc = weather_map.get(weather_code, "未知天气")
        return f"{city}当前天气：{weather_desc}，温度约 {temp}℃"
    except Exception as e:
        logger.error(f"天气查询失败：{str(e)}")
        return f"天气查询失败：{str(e)}"

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
tools = [calculate, get_current_time, get_weather]
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
memory = MemorySaver()

def build_graph_with_tool():
    """构建带有工具调用能力的 LangGraph 图"""
    workflow = StateGraph(state_schema=MessagesState)  # type: ignore
    # 工具执行节点（LangGraph 官方预置）
    tool_node = ToolNode(tools=tools)
    workflow.add_node("agent", agent)  # type: ignore
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

    return workflow.compile(checkpointer=memory)


graph = build_graph_with_tool()
logger.info("LangGraph 已编译完成")


# ────────────────────────────────────────────────
# 交互函数
# ────────────────────────────────────────────────

def test_interactive_chat(verbose: bool = True):
    """启动交互式对话模式
    
    Args:
        verbose: 是否显示详细信息
    """
    print("\n" + "═" * 70)
    print("🤖 AI 代理对话模式 已启动（支持持久化）")
    print(f"  模型：{config.model}")
    print(f"  温度：{config.temperature}")
    print("  命令：/help 查看帮助   exit / quit / q 退出")
    print("═" * 70 + "\n")

    # 固定 thread_id，重启后还能接着聊
    checkpoint_config = {"configurable": {"thread_id": "my_test_session_1"}}

    while True:
        try:
            user_input = input("你: ").strip()
            if not user_input:
                continue

            cmd = user_input.lower()
            if cmd in ['exit', 'quit', 'q']:
                print("\n👋 对话结束，欢迎下次使用！\n")
                break

            if cmd in ['/clear', '/reset']:
                # 清空当前会话（删除 checkpoint）
                memory.delete(checkpoint_config)
                print("🧹 当前会话历史已清空\n")
                continue

            if cmd == '/help':
                print("""
可用命令：
  /clear 或 /reset    清空当前会话历史
  /help               显示此帮助
  exit / quit / q     退出对话
                """)
                continue

            # 只传当前用户消息，checkpointer 自动加载历史
            inputs = {"messages": [HumanMessage(content=user_input)]}
            result = graph.invoke(inputs, config=checkpoint_config)

            ai_msg = result["messages"][-1]
            print(f"AI : {ai_msg.content}\n")

            # 调试：显示当前保存的状态（可选）
            if verbose:
                saved_state = memory.get(checkpoint_config)
                if saved_state and "channel_values" in saved_state:
                    messages = saved_state["channel_values"].get("messages", [])
                    print("----- 当前保存的历史（从 checkpointer 读取） -----")
                    for msg in messages[-5:]:  # 只显示最近5条
                        role = "你" if isinstance(msg, HumanMessage) else "AI"
                        print(f"{role}: {msg.content[:60]}...")
                    print("--------------------------------------------\n")

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
