"""命令行交互模块：负责会话循环、用户输入处理与持久化对话运行。"""

from pathlib import Path
from typing import Any, Optional

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver


def run_interactive_chat(
    graph: Any,
    config: Any,
    thread_id: str = "my_test_session_1",
    db_path: Optional[Path] = None,
) -> None:
    """启动带 SQLite 持久化的交互式对话。"""
    print("\n" + "═" * 70)
    print("🤖 AI 代理对话模式 已启动（支持持久化）")
    print(f"  模型：{config.model}")
    print(f"  温度：{config.temperature}")
    print("  命令：/help 查看帮助   exit / quit / q 退出")
    print("═" * 70 + "\n")

    checkpoint_config = {"configurable": {"thread_id": thread_id}}
    if db_path is None:
        db_dir = Path(__file__).parent / "data" / "checkpoints"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "checkpoints.db"

    with SqliteSaver.from_conn_string(str(db_path)) as memory:
        compiled_graph = graph.compile(checkpointer=memory,interrupt_before=["tools"])
        while True:
            try:
                user_input = input("你: ").strip()
                if not user_input:
                    continue

                cmd = user_input.lower()
                if cmd in ["exit", "quit", "q"]:
                    print("\n👋 对话结束，欢迎下次使用！\n")
                    break

                if cmd in ["/clear", "/reset"]:
                    memory.delete_thread(thread_id)
                    print(f"🧹 当前会话历史已清空，thread_id: {thread_id}")
                    continue

                if cmd == "/help":
                    print(
                        """
可用命令：
/clear 或 /reset    清空当前会话历史
/help               显示此帮助
exit / quit / q     退出对话
                        """
                    )
                    continue

                inputs = {"messages": [HumanMessage(content=user_input)]}
                result = compiled_graph.invoke(inputs, config=checkpoint_config)
                last_msg = result["messages"][-1]
                if last_msg.tool_calls:
                    # 图被interrupted，工具调用未完成，提示用户等待
                    tool_call = last_msg.tool_calls[0]
                    print(f"⏸️  即将执行工具：{tool_call['name']}")
                    print(f"   参数：{tool_call['args']}")

                    comfirm = input("是否继续执行工具？(y/n): ").strip().lower()
                    if comfirm == "y":
                        result = compiled_graph.invoke(None, config=checkpoint_config)
                        last_msg = result["messages"][-1]
                        print(f"AI : {last_msg.content}\n")
                    else:
                        print("❌ 已取消工具调用。输入 /clear 可重置会话。\n")
                        continue
                else:
                    print(f"AI : {last_msg.content}\n")

            except KeyboardInterrupt:
                print("\n⚠️  对话已手动中断\n")
                break
            except Exception as exc:
                print(f"❌ 发生错误：{str(exc)}\n")
