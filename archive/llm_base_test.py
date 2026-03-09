import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

# 加载 .env
load_dotenv(Path(__file__).parent / ".env")

# ====================== 日志配置 ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

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

# ====================== 基座测试（仅输出关键参数） ======================
def _base_url_summary(url: str | None) -> str:
    """仅输出 base_url 的 host，便于区分端点且不泄露路径"""
    if not url:
        return "未设置"
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        return p.netloc or p.path or url[:32]
    except Exception:
        return url[:32] + "…"


human_input = "你好啊，这是一个测试 demo 的输入"
user_msg = HumanMessage(content=human_input)

logger.info(
    "基座测试启动 | 模型=%s | 温度=%.2f | 端点=%s",
    model_name, temperature, _base_url_summary(base_url),
)
logger.info("输入长度=%d 字符", len(human_input))

try:
    t0 = time.perf_counter()
    result = llm_chain.invoke({"messages": [user_msg]})
    latency_ms = (time.perf_counter() - t0) * 1000
    ai_reply = result
    out_len = len(ai_reply.content) if ai_reply.content else 0

    # Token 用量（部分 API 在 usage_metadata 或 response_metadata.usage）
    usage = getattr(ai_reply, "usage_metadata", None) or {}
    if not usage and isinstance(getattr(ai_reply, "response_metadata", None), dict):
        usage = (ai_reply.response_metadata or {}).get("usage") or {}
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)

    # 实际返回的模型名、结束原因
    meta = getattr(ai_reply, "response_metadata", None) or {}
    resp_model = meta.get("model_name") or meta.get("model")
    finish_reason = meta.get("finish_reason") or meta.get("stop_reason")

    logger.info(
        "延迟=%.0f ms | 输出长度=%d 字符 | 状态=成功",
        latency_ms, out_len,
    )
    if input_tokens is not None or output_tokens is not None:
        logger.info(
            "Token 用量 | 输入=%s | 输出=%s | 合计=%s",
            input_tokens if input_tokens is not None else "-",
            output_tokens if output_tokens is not None else "-",
            total_tokens if total_tokens is not None else "-",
        )
    if output_tokens and output_tokens > 0 and latency_ms > 0:
        logger.info("吞吐≈%.1f token/s", output_tokens / (latency_ms / 1000))
    if resp_model:
        logger.info("实际模型=%s", resp_model)
    if finish_reason:
        logger.info("结束原因=%s", finish_reason)
    logger.info("回复摘要: %s", (ai_reply.content[:80] + "…") if out_len > 80 else (ai_reply.content or "(空)"))
except Exception as e:
    logger.error("基座调用失败: %s", str(e), exc_info=True)
