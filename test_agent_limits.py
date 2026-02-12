"""
AI Agent 系统局限性测试
Day 5 - 深入理解当前 ReAct 循环的边界

测试目标：
1. 多步推理：需要链式调用多个工具
2. 工具失败处理：工具无法执行时的行为
3. 上下文长度：长对话的性能和稳定性
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
import requests

# ────────────────────────────────────────────────
# 环境初始化
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
# 配置 & 工具定义（复用 v3 代码）
# ────────────────────────────────────────────────

class LLMConfig:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.model = os.getenv("LLM_MODEL", "qwen-flash")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.4"))
        self.base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def validate(self) -> bool:
        return bool(self.api_key)

@tool
def calculate(expression: str) -> str:
    """执行数学计算。支持 sin/cos/tan/sqrt/pi"""
    try:
        logger.info(f"🔧 工具调用 | calculate | 表达式: {expression}")
        allowed_names = {"__builtins__": {}}
        allowed_names.update({
            "sin": __import__("math").sin,
            "cos": __import__("math").cos,
            "tan": __import__("math").tan,
            "sqrt": __import__("math").sqrt,
            "pi": __import__("math").pi,
        })
        result = eval(expression, allowed_names)
        logger.info(f"✅ 计算结果: {result}")
        return str(result)
    except Exception as e:
        logger.error(f"❌ 计算错误: {str(e)}")
        return f"计算错误：{str(e)}"

@tool
def get_current_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间"""
    try:
        logger.info(f"🔧 工具调用 | get_current_time | 格式: {format_str}")
        result = datetime.now().strftime(format_str)
        logger.info(f"✅ 当前时间: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ 时间格式错误: {str(e)}")
        return f"时间格式错误：{str(e)}"

@tool
def get_weather(city: str = "成都") -> str:
    """获取指定城市天气（支持：成都、北京、上海、广州、深圳、杭州、西安、重庆、武汉、南京）"""
    try:
        logger.info(f"🔧 工具调用 | get_weather | 城市: {city}")
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
        
        if city not in city_coords:
            logger.warning(f"⚠️  不支持的城市: {city}")
            return f"抱歉，暂不支持查询 {city} 的天气。目前仅支持：{', '.join(city_coords.keys())}"
        
        coords = city_coords[city]
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&current=temperature_2m,weathercode&timezone=Asia/Shanghai"
        resp = requests.get(url, timeout=5).json()
        temp = resp["current"]["temperature_2m"]
        weather_code = resp["current"]["weathercode"]
        
        weather_map = {
            0: "晴朗", 1: "多云", 2: "阴天", 3: "小雨",
            45: "雾", 51: "小雨", 61: "中雨", 80: "阵雨"
        }
        weather_desc = weather_map.get(weather_code, "未知天气")
        result = f"{city}当前天气：{weather_desc}，温度 {temp}℃"
        logger.info(f"✅ 天气查询成功: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ 天气查询失败: {str(e)}")
        return f"天气查询失败：{str(e)}"

# ────────────────────────────────────────────────
# 构建代理
# ────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一个具备计算、查时间、查天气能力的 AI 助手。

工具使用规则：
- 数学运算 → 调用 calculate 工具
- 查询时间 → 调用 get_current_time 工具
- 查询天气 → 调用 get_weather 工具

重要提示：
1. 如果需要多步操作（如先查天气再计算），请按顺序调用工具
2. 使用上一个工具的返回结果作为下一个工具的输入
3. 全程用中文回复
"""

def create_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("messages"),
    ])

config = LLMConfig()
if not config.validate():
    raise RuntimeError("LLM 配置不完整，请检查 .env 文件")

llm = ChatOpenAI(
    base_url=config.base_url,
    api_key=config.api_key,
    model=config.model,
    temperature=config.temperature,
)

tools = [calculate, get_current_time, get_weather]
llm_with_tools = llm.bind_tools(tools)
prompt = create_prompt()
llm_chain = prompt | llm_with_tools

def agent(state: MessagesState) -> dict:
    """代理节点"""
    response = llm_chain.invoke({"messages": state["messages"]})
    return {"messages": [response]}

def build_graph() -> StateGraph:
    """构建图"""
    workflow = StateGraph(state_schema=MessagesState)
    tool_node = ToolNode(tools=tools)
    workflow.add_node("agent", agent)
    workflow.add_node("tools", tool_node)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        tools_condition,
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")
    return workflow

graph = build_graph()

# ────────────────────────────────────────────────
# 测试函数
# ────────────────────────────────────────────────

def run_test(test_name: str, user_input: str, thread_id: str = "test_session"):
    """运行单个测试"""
    print("\n" + "═" * 80)
    print(f"🧪 测试：{test_name}")
    print("═" * 80)
    print(f"👤 用户输入: {user_input}\n")
    
    db_dir = Path(__file__).parent / "data" / "checkpoints"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "test_checkpoints.db"
    
    with SqliteSaver.from_conn_string(str(db_path)) as memory:
        compile_graph = graph.compile(checkpointer=memory)
        checkpoint_config = {"configurable": {"thread_id": thread_id}}
        
        try:
            inputs = {"messages": [HumanMessage(content=user_input)]}
            result = compile_graph.invoke(inputs, config=checkpoint_config)
            ai_msg = result["messages"][-1]
            
            print(f"🤖 AI 回复:\n{ai_msg.content}\n")
            
            # 统计工具调用次数
            tool_calls_count = sum(
                1 for msg in result["messages"] 
                if hasattr(msg, "tool_calls") and msg.tool_calls
            )
            print(f"📊 统计: 共调用 {tool_calls_count} 次工具")
            
            return ai_msg.content
            
        except Exception as e:
            print(f"❌ 测试失败: {str(e)}")
            logger.exception("测试异常")
            return None

def clear_test_session(thread_id: str = "test_session"):
    """清空测试会话"""
    db_path = Path(__file__).parent / "data" / "checkpoints" / "test_checkpoints.db"
    if db_path.exists():
        with SqliteSaver.from_conn_string(str(db_path)) as memory:
            memory.delete_thread(thread_id)
        print(f"🧹 已清空测试会话: {thread_id}\n")

# ────────────────────────────────────────────────
# 主测试流程
# ────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "🚀 " * 20)
    print("AI Agent 系统局限性测试 - Day 5")
    print("🚀 " * 20)
    
    # ============ 测试 1：多步推理（链式工具调用）============
    print("\n\n" + "▶️ " * 20)
    print("测试 1：多步推理能力")
    print("目标：考察代理能否先调用 get_weather，再用返回的温度调用 calculate")
    print("▶️ " * 20)
    
    clear_test_session("test_multistep")
    run_test(
        test_name="多步推理：查天气 → 计算",
        user_input="帮我查一下成都的天气，然后计算：温度 * 2 + 10 等于多少？",
        thread_id="test_multistep"
    )
    
    # input("\n⏸️  按 Enter 继续下一个测试...")
    
    # ============ 测试 2：工具失败处理 ============
    print("\n\n" + "▶️ " * 20)
    print("测试 2：工具失败处理")
    print("目标：考察代理如何处理不支持的城市查询")
    print("▶️ " * 20)
    
    clear_test_session("test_failure")
    run_test(
        test_name="工具失败：查询不支持的城市",
        user_input="帮我查一下纽约的天气",
        thread_id="test_failure"
    )
    
    # input("\n⏸️  按 Enter 继续下一个测试...")
    
    # ============ 测试 3：嵌套推理 ============
    print("\n\n" + "▶️ " * 20)
    print("测试 3：复杂嵌套推理")
    print("目标：考察代理能否处理更复杂的多步任务")
    print("▶️ " * 20)
    
    clear_test_session("test_nested")
    run_test(
        test_name="嵌套推理：天气 → 计算 → 再计算",
        user_input="查成都天气，把温度记为 T，然后算 T * 2，再算这个结果的平方根",
        thread_id="test_nested"
    )
    
    # input("\n⏸️  按 Enter 继续下一个测试...")
    
    # ============ 测试 4：并发需求（当前无法实现）============
    print("\n\n" + "▶️ " * 20)
    print("测试 4：并发工具调用需求")
    
    print("目标：暴露当前系统无法并行调用工具的局限")
    print("▶️ " * 20)
    
    clear_test_session("test_parallel")
    run_test(
        test_name="并发需求：同时查询多个城市",
        user_input="帮我同时查询北京、上海、成都三个城市的天气",
        thread_id="test_parallel"
    )
    
    print("\n\n" + "✅ " * 20)
    print("所有测试完成！")
    print("✅ " * 20)
    
    print("""
╔════════════════════════════════════════════════════════════════════╗
║  测试总结 - 请思考以下问题：                                          ║
╠════════════════════════════════════════════════════════════════════╣
║  1. 代理能否成功完成多步推理？如果不能，为什么？                        ║
║  2. 工具失败时，代理的错误处理是否优雅？                                ║
║  3. 复杂嵌套任务的表现如何？是否需要人工干预？                          ║
║  4. 并发查询时，代理是顺序执行还是并行？性能如何？                       ║
║  5. 当前 ReAct 循环的最大局限性是什么？                                ║
╚════════════════════════════════════════════════════════════════════╝
    """)
