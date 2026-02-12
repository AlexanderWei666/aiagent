# AI Agent 项目上下文

> **本文件用途**：快速同步项目状态，避免每次读所有文件。  
> **更新频率**：每完成一个阶段（Phase）后更新。  
> **详细学习日志**：见 `notebook.md`

---

## 一、项目目标

从零系统学习 AI Agent，最终能独立实现类似 Manus / OpenClaw 的可运行原型。

**学习路径**：
- 基础 → 工具 → 记忆 → 系统局限 → 人在回路 → 复杂图结构 → 多 Agent

---

## 二、当前进度

### ✅ 已完成阶段

| 阶段 | 核心内容 | 对应文件 | 状态 |
|------|----------|----------|------|
| Phase 1 | 基础 LangGraph（StateGraph + agent 节点 + 手动历史） | `hello_agent_v1.py` | ✅ |
| Phase 2 | 工具调用（ReAct 循环 + ToolNode + tools_condition） | `hello_agent_v1.py` | ✅ |
| Phase 3 | 内存持久化（MemorySaver） | `hello_agent_v2.py` | ✅ |
| Phase 4 | 真持久化（SqliteSaver + 项目结构优化） | `hello_agent_v3.py` | ✅ |
| Phase 5 | 系统局限性测试（多步推理 + 工具失败 + 嵌套 + 并发） | `test_agent_limits.py` | ✅ 已跑完 |

### 🔄 当前阶段

**Phase 6：Human-in-the-loop（人在回路中）**
- **状态**：待开始
- **目标**：学习在关键操作前暂停，等人工确认/修改后继续
- **下一步**：选择第一个实现场景（如：计算前确认 / 天气查询前确认城市）

---

## 三、技术栈快照

### 3.1 核心依赖

```
langgraph >= 0.2.x
langchain-core
langchain-openai
python-dotenv
requests  # 天气 API
```

### 3.2 当前架构

```
代理图结构（hello_agent_v3.py）：
  START → agent → [tools_condition] → tools → agent → END
                              ↓
                             END

核心模块映射：
- Executor：StateGraph + 条件边
- Tool：@tool + bind_tools + ToolNode
- Memory：SqliteSaver（./data/checkpoints/checkpoints.db）
- Planner：隐式（模型自己决定用哪个工具）
```

### 3.3 可用工具

| 工具名 | 功能 | 文件 |
|--------|------|------|
| `calculate` | 数学计算（支持 sin/cos/tan/sqrt/pi） | v1/v2/v3 + test_agent_limits |
| `get_current_time` | 获取当前时间 | v2/v3 + test_agent_limits |
| `get_weather` | 查询中国 10 城天气（open-meteo API） | v2/v3 + test_agent_limits |

### 3.4 配置（.env）

```bash
LLM_PROVIDER=openai
LLM_MODEL=qwen-flash
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=<your-key>
LLM_TEMPERATURE=0.6
MAX_HISTORY=20
```

---

## 四、Phase 5 核心结论（系统局限）

### 测试结果总结

| 测试 | 结果 | 关键发现 |
|------|------|----------|
| 多步推理（天气→计算） | ✅ 成功 | ReAct 循环支持顺序多步任务 |
| 工具失败（查询纽约） | ✅ 优雅拒绝 | 模型能预判工具能力，避免盲目调用 |
| 嵌套推理（3 步链式） | ✅ 成功 | 当前 MessagesState 支持 3 步推理 |
| 并发需求（查三城） | ⚠️ 部分支持 | 模型能一次发 3 个请求，但 ToolNode 可能顺序执行 |

### 两大核心局限

1. **隐式规划 = 不够可控**
   - 模型自己决定用哪个工具、何时用
   - 复杂任务可能跳步或重复
   - 需要更显式的 Planner 或 Human-in-the-loop

2. **工具执行可能是顺序瓶颈**
   - ToolNode 默认可能顺序执行多个工具
   - 涉及慢速 API 时性能低
   - 需要并行图结构或异步工具节点

---

## 五、文件结构

```
aiagent/
├── agent-context.md        # 本文件（项目快照）
├── notebook.md             # 详细学习日志
├── .cursorrules            # Claude/GPT 协作规则
├── propmt_list.txt         # 系统 Prompt 设计
├── .env                    # 配置文件
├── requirements.txt        # 依赖
│
├── hello_agent_v1.py       # Phase 1-2: 基础图 + 工具
├── hello_agent_v2.py       # Phase 3: MemorySaver
├── hello_agent_v3.py       # Phase 4: SqliteSaver（当前主版本）
├── test_agent_limits.py    # Phase 5: 系统局限性测试
├── llm_base_test.py        # 基座 LLM 测试工具
│
└── data/
    └── checkpoints/        # SQLite 持久化存储
        ├── checkpoints.db      # 正式会话
        └── test_checkpoints.db # 测试会话
```

---

## 六、下一步学习方向（Phase 6）

### 目标
在关键操作前插入人工确认点，学习「可控性」。

### 需要学习的概念
- LangGraph 的 `interrupt` / `Command` API
- 如何在图中标记「需要人工介入」的节点
- 如何恢复被暂停的执行

### 第一个实现场景（待选择）
1. **计算前确认**：在调用 `calculate` 前暂停，让用户确认表达式
2. **天气查询前确认**：让用户修改城市名再查询
3. **多步任务审核**：在第一步完成后暂停，用户确认是否继续

### 对 Manus/OpenClaw 的意义
- 机械臂执行前的轨迹确认
- 危险操作前的人工审批
- 紧急停止 + 恢复机制

---

## 七、协作规则（给 AI 助手）

### Claude（Sonnet）角色
- 导师身份：概念讲解、架构设计、方向判断
- **先读本文件**，了解当前进度和上下文
- 不直接写完整实现代码
- 每次回答说明下一步学习方向

### GPT（Codex）角色
- 工程师身份：代码实现、调试、重构
- **先读本文件**，了解技术栈和架构
- 优先点评代码问题，不整体重写
- 关注 Agent 执行循环、Tool 抽象、Memory 扩展性

### 高效上下文使用原则
1. **必读**：本文件（agent-context.md）
2. **按需读**：
   - 如果讨论学习路径/概念 → 读 notebook.md
   - 如果讨论当前实现 → 读 hello_agent_v3.py
   - 如果讨论测试结果 → 读 test_agent_limits.py
3. **不要每次都读所有文件**

---

## 八、快速定位指南

| 我想... | 应该读哪个文件 |
|---------|---------------|
| 了解项目进度和技术栈 | 本文件（agent-context.md）|
| 查看详细学习过程 | notebook.md |
| 看当前可运行的代码 | hello_agent_v3.py |
| 了解系统局限性 | 本文件第四节 + test_agent_limits.py |
| 查看工具定义 | hello_agent_v3.py（第 60-120 行）|
| 理解图结构 | 本文件 3.2 节 + hello_agent_v3.py（第 180-200 行）|
| 查看配置 | .env + 本文件 3.4 节 |

---

**最后更新**：2026-02-12（Phase 5 完成）  
**下次更新时机**：Phase 6 第一个场景实现完成后
