import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.graph import MessagesState
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

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

SYSTEM_PROMPT = """你是一个实验性 AI 代理，基于 LangGraph 构建。
你**必须**严格按照以下格式回复，不要添加任何多余内容：

<thinking>
1. 理解用户意图：...
2. 需要的信息/工具：...
3. 我的推理步骤：...
</thinking>

<final_answer>
最终清晰、完整的回答写在这里
</final_answer>

全程用中文，语气专业且友好。"""


def create_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("messages"),
    ])


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

prompt = create_prompt()
llm_chain = prompt | llm


# ────────────────────────────────────────────────
# 代理节点
# ────────────────────────────────────────────────

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


# ────────────────────────────────────────────────
# 构建图
# ────────────────────────────────────────────────

def build_graph():
    workflow = StateGraph(state_schema=MessagesState)
    workflow.add_node("agent", agent)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)
    return workflow.compile()


graph = build_graph()
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
            result = graph.invoke({"messages": messages_history})
            # logger.info(f"代理返回结果: {result['messages']}")
            ai_msg = result["messages"][-1]

            print(f"AI : {ai_msg.content}\n")

            # 加入 AI 回复到历史
            messages_history.append(ai_msg)

            # 显示历史（调试用）
            if verbose and len(messages_history) > 2:
                print("[最近消息历史]")
                for i, msg in enumerate(messages_history[-6:], len(messages_history)-5):
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
