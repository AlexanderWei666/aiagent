"""系统局限性测试：验证多步推理、失败处理与工具调用边界。"""
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径，便于直接运行本文件
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from pathlib import Path
from typing import Optional, Sequence

from langgraph.checkpoint.sqlite import SqliteSaver

from agent.core import (
    DEFAULT_SYSTEM_PROMPT,
    build_checkpoint_config,
    compile_runtime_graph,
    continue_after_interrupt,
    create_configured_graph,
    get_pending_tool_call,
    invoke_user_turn,
)
from agent.tools import get_default_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

tools = get_default_tools()
_, graph = create_configured_graph(tools=tools, system_prompt=DEFAULT_SYSTEM_PROMPT)


def run_test(
    test_name: str,
    user_input: str,
    thread_id: str = "test_session",
    expected_keywords: Optional[Sequence[str]] = None,
    expected_tool_keywords: Optional[Sequence[str]] = None,
    min_tool_calls: Optional[int] = None,
) -> bool:
    """运行单个测试，输出通过/失败判定。"""
    print(f"\n[{test_name}]")
    print(f"输入: {user_input}\n")

    db_dir = Path(__file__).resolve().parent.parent / "data" / "checkpoints"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "test_checkpoints.db"

    with SqliteSaver.from_conn_string(str(db_path)) as memory:
        compiled_graph = compile_runtime_graph(graph=graph, checkpointer=memory)
        checkpoint_config = build_checkpoint_config(thread_id)

        try:
            result = invoke_user_turn(
                compiled_graph=compiled_graph,
                user_input=user_input,
                checkpoint_config=checkpoint_config,
            )

            max_auto_approvals = 8
            pending = get_pending_tool_call(result)
            while pending and max_auto_approvals > 0:
                result = continue_after_interrupt(
                    compiled_graph=compiled_graph,
                    checkpoint_config=checkpoint_config,
                )
                pending = get_pending_tool_call(result)
                max_auto_approvals -= 1

            if pending:
                print("FAIL: 自动批准工具调用超出上限，疑似进入循环")
                return False

            ai_msg = result["messages"][-1]
            print(f"AI: {ai_msg.content}\n")

            tool_calls_count = sum(
                1 for msg in result["messages"] if hasattr(msg, "tool_calls") and msg.tool_calls
            )
            print(f"工具调用次数: {tool_calls_count}")

            tool_outputs = [
                str(msg.content)
                for msg in result["messages"]
                if getattr(msg, "type", "") == "tool"
            ]
            for idx, output in enumerate(tool_outputs, start=1):
                print(f"工具输出[{idx}]: {output}")

            checks = []
            if expected_keywords:
                checks.append(("关键词检查", all(k in ai_msg.content for k in expected_keywords)))
            if expected_tool_keywords:
                merged = "\n".join(tool_outputs)
                checks.append(("工具输出关键词", all(k in merged for k in expected_tool_keywords)))
            if min_tool_calls is not None:
                checks.append((f"工具调用 >= {min_tool_calls}", tool_calls_count >= min_tool_calls))
            if not checks:
                checks.append(("回复非空", bool(ai_msg.content.strip())))

            passed = all(ok for _, ok in checks)
            print(f"结果: {'PASS' if passed else 'FAIL'}")
            for name, ok in checks:
                print(f"  {'OK' if ok else 'NG'} {name}")
            return passed

        except Exception as exc:
            print(f"FAIL: {exc}")
            logger.exception("测试异常")
            return False


def clear_test_session(thread_id: str = "test_session") -> None:
    """清空测试会话。"""
    db_path = Path(__file__).resolve().parent.parent / "data" / "checkpoints" / "test_checkpoints.db"
    if db_path.exists():
        with SqliteSaver.from_conn_string(str(db_path)) as memory:
            memory.delete_thread(thread_id)


if __name__ == "__main__":
    test_results = []

    clear_test_session("test_multistep")
    test_results.append(run_test(
        test_name="多步推理：查天气 → 计算",
        user_input="帮我查一下成都的天气，然后计算：温度 * 2 + 10 等于多少？",
        thread_id="test_multistep",
        expected_keywords=("成都",),
        min_tool_calls=2,
    ))

    clear_test_session("test_failure")
    test_results.append(run_test(
        test_name="工具失败：查询不支持的城市",
        user_input="帮我查一下纽约的天气",
        thread_id="test_failure",
        expected_tool_keywords=("暂不支持查询", "纽约"),
        min_tool_calls=1,
    ))

    clear_test_session("test_nested")
    test_results.append(run_test(
        test_name="嵌套推理：天气 → 计算 → 再计算",
        user_input="查成都天气，把温度记为 T，然后算 T * 2，再算这个结果的平方根",
        thread_id="test_nested",
        expected_keywords=("成都",),
        min_tool_calls=2,
    ))

    clear_test_session("test_parallel")
    test_results.append(run_test(
        test_name="并发需求：同时查询多个城市",
        user_input="帮我同时查询北京、上海、成都三个城市的天气",
        thread_id="test_parallel",
        expected_keywords=("北京", "上海", "成都"),
        min_tool_calls=1,
    ))

    clear_test_session("test_default_city")
    test_results.append(run_test(
        test_name="默认城市：今天天气怎么样",
        user_input="今天天气怎么样",
        thread_id="test_default_city",
        expected_keywords=("成都",),
        expected_tool_keywords=("成都",),
        min_tool_calls=1,
    ))

    passed_count = sum(1 for r in test_results if r)
    print(f"\n回归结果：{passed_count}/{len(test_results)} 通过")
