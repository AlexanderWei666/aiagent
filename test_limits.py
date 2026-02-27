"""系统局限性测试脚本：验证多步推理、失败处理与工具调用边界。

AI Agent 系统局限性测试
Day 5 - 深入理解当前 ReAct 循环的边界

测试目标：
1. 多步推理：需要链式调用多个工具
2. 工具失败处理：工具无法执行时的行为
3. 上下文长度：长对话的性能和稳定性
"""

import logging
from pathlib import Path
from typing import Optional, Sequence

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from agent_core import create_configured_graph
from agent_tools import get_default_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

TEST_SYSTEM_PROMPT = """你是一个具备计算、查时间、查天气能力的 AI 助手。

工具使用规则：
- 数学运算 → 调用 calculate 工具
- 查询时间 → 调用 get_current_time 工具
- 查询天气 → 调用 get_weather 工具

重要提示：
1. 如果需要多步操作（如先查天气再计算），请按顺序调用工具
2. 使用上一个工具的返回结果作为下一个工具的输入
3. 对于天气查询，必须调用 get_weather 工具后再回复
4. 全程用中文回复
"""

tools = get_default_tools()
_, graph = create_configured_graph(tools=tools, system_prompt=TEST_SYSTEM_PROMPT)


def run_test(
    test_name: str,
    user_input: str,
    thread_id: str = "test_session",
    expected_keywords: Optional[Sequence[str]] = None,
    expected_tool_keywords: Optional[Sequence[str]] = None,
    min_tool_calls: Optional[int] = None,
) -> bool:
    """运行单个测试，并输出最小通过/失败判定。"""
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

            tool_calls_count = sum(
                1 for msg in result["messages"] if hasattr(msg, "tool_calls") and msg.tool_calls
            )
            print(f"📊 统计: 共调用 {tool_calls_count} 次工具")

            tool_outputs = [
                str(msg.content)
                for msg in result["messages"]
                if getattr(msg, "type", "") == "tool"
            ]
            if tool_outputs:
                print("🧰 工具原始输出:")
                for idx, output in enumerate(tool_outputs, start=1):
                    print(f"  [{idx}] {output}")

            checks = []
            if expected_keywords:
                keyword_ok = all(keyword in ai_msg.content for keyword in expected_keywords)
                checks.append(("关键词检查", keyword_ok))
            if expected_tool_keywords:
                merged_tool_output = "\n".join(tool_outputs)
                tool_keyword_ok = all(
                    keyword in merged_tool_output for keyword in expected_tool_keywords
                )
                checks.append(("工具输出关键词检查", tool_keyword_ok))
            if min_tool_calls is not None:
                tool_call_ok = tool_calls_count >= min_tool_calls
                checks.append((f"工具调用次数 >= {min_tool_calls}", tool_call_ok))

            if not checks:
                checks.append(("回复非空", bool(ai_msg.content.strip())))

            failed_checks = [name for name, ok in checks if not ok]
            passed = not failed_checks
            status = "PASS" if passed else "FAIL"
            print(f"🧾 判定结果: {status}")
            for name, ok in checks:
                mark = "✅" if ok else "❌"
                print(f"  {mark} {name}")
            return passed
        except Exception as exc:
            print(f"❌ 测试失败: {str(exc)}")
            logger.exception("测试异常")
            return False


def clear_test_session(thread_id: str = "test_session") -> None:
    """清空测试会话。"""
    db_path = Path(__file__).parent / "data" / "checkpoints" / "test_checkpoints.db"
    if db_path.exists():
        with SqliteSaver.from_conn_string(str(db_path)) as memory:
            memory.delete_thread(thread_id)
        print(f"🧹 已清空测试会话: {thread_id}\n")


if __name__ == "__main__":
    print("\n" + "🚀 " * 20)
    print("AI Agent 系统局限性测试 - Day 5")
    print("🚀 " * 20)
    test_results = []

    print("\n\n" + "▶️ " * 20)
    print("测试 1：多步推理能力")
    print("目标：考察代理能否先调用 get_weather，再用返回的温度调用 calculate")
    print("▶️ " * 20)
    clear_test_session("test_multistep")
    test_results.append(
        run_test(
            test_name="多步推理：查天气 → 计算",
            user_input="帮我查一下成都的天气，然后计算：温度 * 2 + 10 等于多少？",
            thread_id="test_multistep",
            expected_keywords=("成都",),
            min_tool_calls=2,
        )
    )

    print("\n\n" + "▶️ " * 20)
    print("测试 2：工具失败处理")
    print("目标：考察代理如何处理不支持的城市查询")
    print("▶️ " * 20)
    clear_test_session("test_failure")
    test_results.append(
        run_test(
            test_name="工具失败：查询不支持的城市",
            user_input="帮我查一下纽约的天气",
            thread_id="test_failure",
            expected_tool_keywords=("暂不支持查询", "纽约"),
            min_tool_calls=1,
        )
    )

    print("\n\n" + "▶️ " * 20)
    print("测试 3：复杂嵌套推理")
    print("目标：考察代理能否处理更复杂的多步任务")
    print("▶️ " * 20)
    clear_test_session("test_nested")
    test_results.append(
        run_test(
            test_name="嵌套推理：天气 → 计算 → 再计算",
            user_input="查成都天气，把温度记为 T，然后算 T * 2，再算这个结果的平方根",
            thread_id="test_nested",
            expected_keywords=("成都",),
            min_tool_calls=2,
        )
    )

    print("\n\n" + "▶️ " * 20)
    print("测试 4：并发工具调用需求")
    print("目标：暴露当前系统无法并行调用工具的局限")
    print("▶️ " * 20)
    clear_test_session("test_parallel")
    test_results.append(
        run_test(
            test_name="并发需求：同时查询多个城市",
            user_input="帮我同时查询北京、上海、成都三个城市的天气",
            thread_id="test_parallel",
            expected_keywords=("北京", "上海", "成都"),
            min_tool_calls=1,
        )
    )

    print("\n\n" + "✅ " * 20)
    print("所有测试完成！")
    print("✅ " * 20)
    passed_count = sum(1 for item in test_results if item)
    total_count = len(test_results)
    print(f"\n📌 回归判定：{passed_count}/{total_count} 通过")
