"""命令行交互模块：负责会话循环、用户输入处理与持久化对话运行。"""

from pathlib import Path
from typing import Any, Optional

from langgraph.checkpoint.sqlite import SqliteSaver
from agent_core import (
    build_checkpoint_config,
    continue_after_interrupt,
    compile_runtime_graph,
    get_pending_tool_call,
    invoke_user_turn,
)


def run_interactive_chat(
    graph: Any,
    config: Any,
    thread_id: str = "my_test_session_1",
    db_path: Optional[Path] = None,
) -> None:
    """启动带 SQLite 持久化的交互式对话。"""
    print(f"模型：{config.model}  温度：{config.temperature}")
    print("命令：/help 查看帮助   exit / quit / q 退出\n")

    checkpoint_config = build_checkpoint_config(thread_id)
    if db_path is None:
        db_dir = Path(__file__).parent / "data" / "checkpoints"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "checkpoints.db"

    with SqliteSaver.from_conn_string(str(db_path)) as memory:
        compiled_graph = compile_runtime_graph(graph=graph, checkpointer=memory)
        while True:
            try:
                user_input = input("你: ").strip()
                if not user_input:
                    continue

                cmd = user_input.lower()
                if cmd in ["exit", "quit", "q"]:
                    break

                if cmd in ["/clear", "/reset"]:
                    memory.delete_thread(thread_id)
                    print(f"会话历史已清空 (thread_id: {thread_id})\n")
                    continue

                if cmd == "/help":
                    print(
                        "/clear /reset    清空当前会话历史\n"
                        "/help            显示此帮助\n"
                        "exit / quit / q  退出对话\n"
                    )
                    continue

                result = invoke_user_turn(
                    compiled_graph=compiled_graph,
                    user_input=user_input,
                    checkpoint_config=checkpoint_config,
                )

                pending = get_pending_tool_call(result)
                cancelled = False
                while pending:
                    print(f"[待确认] 工具：{pending['name']}  参数：{pending['args']}")
                    confirm = input("执行？(y/n): ").strip().lower()
                    if confirm != "y":
                        print("已取消。输入 /clear 可重置会话。\n")
                        cancelled = True
                        break

                    result = continue_after_interrupt(
                        compiled_graph=compiled_graph,
                        checkpoint_config=checkpoint_config,
                    )
                    pending = get_pending_tool_call(result)

                if not cancelled:
                    print(f"AI: {result['messages'][-1].content}\n")

            except KeyboardInterrupt:
                break
            except Exception as exc:
                print(f"错误：{exc}\n")
