import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 加载 .env
load_dotenv(Path(__file__).parent / ".env")

# ====================== 选择基座（从 .env 读取） ======================
base_url = os.getenv("LLM_BASE_URL")
api_key = os.getenv("LLM_API_KEY")
model_name = os.getenv("LLM_MODEL")
temperature = float(os.getenv("LLM_TEMPERATURE", "0.4"))

llm = ChatOpenAI(
    base_url=base_url,
    api_key=api_key,
    model=model_name,
    temperature=temperature,
)

# ====================== 提示词模板 ======================
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个智能助手，用中文友好回复。"),
    MessagesPlaceholder("messages"),
])

llm_chain = prompt | llm

# ====================== 多轮对话测试 ======================
print("\n=== 基座测试模式启动 ===")
print(f"当前模型：{llm.model if hasattr(llm, 'model') else llm.model_name}")

human_input = "你好啊，这是是一个测试demo的输入"
print(f"Human : {human_input}\n")
user_msg = HumanMessage(content=human_input)

try:
    result = llm_chain.invoke({"messages": [user_msg]})
    ai_reply = result
    print(f"AI : {ai_reply.content}\n")
except Exception as e:
    print(f"错误：{str(e)}")