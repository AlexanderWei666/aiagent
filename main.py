"""主程序入口：组装默认配置、工具与图，并启动 CLI 对话。"""
import readline
import logging

from agent.cli import run_interactive_chat
from agent.core import create_configured_graph
from agent.tools import get_default_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

tools = get_default_tools()
config, graph = create_configured_graph(tools=tools)
logger.info(f"加载模型配置：{config}")
logger.info("LangGraph 已构建完成")

if __name__ == "__main__":
    run_interactive_chat(graph=graph, config=config)
