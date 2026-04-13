# AI Agent 项目上下文

> **本文件用途**：快速同步项目状态，避免每次读所有文件。  
> **更新频率**：每完成一个阶段（Phase）后更新。  
> **详细学习日志**：见 `notebook.md`

---

## 一、项目目标

从零系统学习 AI Agent，实现一个**教学版 OpenClaw**——理解并掌握生产级 Agent 的核心架构原理。

### 什么是 OpenClaw？

**OpenClaw** = 开源个人 AI 助手（187k+ GitHub stars，MIT 许可）

**核心能力**：
- 🖥️ **电脑操作**：终端命令、文件操作、浏览器控制（Puppeteer/Playwright）
- 💬 **多渠道接入**：WhatsApp、Telegram、Slack、Discord、Signal、iMessage 等
- 🧠 **持久记忆**：跨会话的 Markdown 文件存储 + 用户习惯学习
- 🤖 **主动执行**：cron 任务、webhook、后台守护进程
- 🛡️ **安全沙箱**：Docker 隔离、DM 配对、权限控制

**架构特点**：
- **Gateway 控制面**：WebSocket 统一管理会话、渠道、工具、事件
- **Agentic Loop**：Think → Plan → Act → Observe → Iterate（显式规划）
- **多 Agent 路由**：不同渠道/账号可路由到隔离的 Agent
- **本地优先**：运行在自己设备上，隐私可控

**技术栈**：TypeScript + Node ≥22 + Claude/GPT + MCP 协议

---

## 📦 教学版 OpenClaw 范围定义

### ✅ 必须实现（核心原理）

**目标**：理解并实现 Agent 的核心架构，做出最小可行原型

| 能力 | 实现方式 | 对应 OpenClaw |
|------|----------|---------------|
| 电脑操作 | `bash` 执行命令 + `file.read/write` | 核心工具（简化版）|
| 显式规划 | Think → Plan → Act → Observe 独立节点 | Agentic Loop |
| 安全机制 | 人工确认 + 权限检查 | 安全层（无 Docker）|
| 持久记忆 | Markdown 文件 + SqliteSaver | Memory 层 |
| 单渠道接入 | CLI 或 Telegram Bot（二选一）| Channel 层（1 个）|

**预计时间**：7-11 周（每周 10-15 小时）

---

### 🔸 可选实现（进阶能力）

完成核心后，按兴趣选择：
- 浏览器控制（Playwright/Selenium）
- 简单沙箱（用户隔离，不做 Docker）
- Cron 定时任务
- 第二个渠道（Slack/Discord）

---

### ❌ 不实现（工程化，非核心原理）

保持聚焦，以下不做：
- ❌ 10 个渠道同时接入（只做 1 个）
- ❌ Gateway WebSocket 架构（用简单 HTTP/轮询）
- ❌ 多 Agent 路由（只做单 Agent）
- ❌ macOS/iOS/Android 原生 App（只做 CLI）
- ❌ Docker 沙箱（用简单权限检查代替）
- ❌ MCP 协议（直接集成工具）
- ❌ 生产级部署（Tailscale/云服务）

---

## 🎯 学习路径（已调整）

**核心原则**：理解原理 > 完整功能，教学原型 > 产品级质量

```
Phase 1-5  ✅ 基础 + 工具 + 记忆 + 测试         （已完成）
Phase 6    ✅ Human-in-the-loop                （已完成：interrupt 确认机制）
Phase 7    ⏳ 显式规划循环（Think→Plan→Act→Observe）
Phase 8    🆕 电脑操作工具（bash + file）
Phase 9       持久记忆优化（Markdown 文件）
Phase 10      单渠道接入（Telegram Bot，可选）
```

---

## 二、当前进度

### ✅ 已完成阶段

| 阶段 | 核心内容 | 对应文件 | 状态 |
|------|----------|----------|------|
| Phase 1 | 基础 LangGraph（StateGraph + agent 节点 + 手动历史） | `hello_agent_v1.py` | ✅ |
| Phase 2 | 工具调用（ReAct 循环 + ToolNode + tools_condition） | `hello_agent_v1.py` | ✅ |
| Phase 3 | 内存持久化（MemorySaver） | `hello_agent_v2.py` | ✅ |
| Phase 4 | 真持久化（SqliteSaver + 项目结构优化） | `main.py` | ✅ |
| Phase 5 | 系统局限性测试 + 工具层抽取 + 回归测试框架 | `tests/test_limits.py` + `agent/tools.py` | ✅ 已完成并优化 |
| Phase 6 | Human-in-the-loop（interrupt 确认机制） + 代码重构 | `agent/cli.py` / `agent/core.py` | ✅ |

### 📅 后续阶段（教学版 OpenClaw 路线）

| Phase | 核心内容 | 预计时间 | 对应 OpenClaw |
|-------|----------|----------|---------------|
| Phase 7 | 显式规划循环（Think→Plan→Act→Observe）| 2-3 周 | Agentic Loop |
| Phase 8 | 电脑操作工具（bash + file.read/write）| 2-3 周 | 核心工具 |
| Phase 9 | 持久记忆优化（Markdown 跨会话存储）| 1 周 | Memory 层 |
| Phase 10 | Telegram Bot 接入（可选）| 1-2 周 | Channel 层 |

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
代理图结构（Phase 6 后）：
  START → agent → [_route_tools] → calculate → agent → END
                               ↘ tools    → agent
                               ↘ END

  interrupt_before=["calculate"]：calculate 节点前暂停，等待人工确认

核心模块映射：
- Executor：StateGraph + 条件边
- Tool：@tool + bind_tools + ToolNode（calculate/tools 两个节点）
- Memory：SqliteSaver（./data/checkpoints/checkpoints.db）
- Planner：隐式（模型自己决定用哪个工具）
- Safety：interrupt_before + 人工确认（calculate 专属）
```

### 3.3 可用工具（已抽取到 `agent/tools.py`）

| 工具名 | 功能 | 策略 |
|--------|------|------|
| `calculate` | 数学计算（支持 sin/cos/tan/sqrt/pi） | 返回字符串结果或错误信息 |
| `get_current_time` | 获取当前时间 | 默认格式 `%Y-%m-%d %H:%M:%S` |
| `get_weather` | 查询中国 10 城天气（open-meteo API）| 未指定城市时默认查成都；**显式拒绝**不支持的城市 |

**工具层设计**：
- 所有工具集中在 `agent/tools.py`，便于复用和维护
- 不支持的操作返回友好错误信息，而不是抛异常
- 支持的城市列表：成都、北京、上海、广州、深圳、杭州、西安、重庆、武汉、南京

### 3.5 Prompt 设计原则（经验记录）

**教训 1**：Prompt 里的「默认值」不等于「强制指令」

| 写法 | 效果 |
|------|------|
| `默认查询成都天气`（描述性）| ❌ 模型可能忽略，转而反问用户 |
| `未指定城市时直接用 city='成都'，不要询问用户`（命令性）| ✅ 模型会直接调用工具 |

**规律**：模型的「内置安全习惯（问清楚用户意图）」优先级高于描述性 Prompt，必须用命令句 + 禁止反问才能覆盖。

**教训 2**：「默认值」规则不能覆盖「用户明确指定」的情况

| 写法 | 问题 |
|------|------|
| `未指定城市时直接用 city='成都'` | ❌ 模型可能对不支持的城市也用成都替换 |
| `未指定城市时用成都；用户明确指定了城市，必须用用户指定的城市` | ✅ 两种情况分别说清楚 |

**规律**：Prompt 里的条件分支要对每种情况都显式说明，不能假设模型能正确推断"反面情况"。

### 3.4 配置（.env）

```bash
LLM_PROVIDER=openai
LLM_MODEL=deepseek-v3.2
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=<your-key>
LLM_TEMPERATURE=0.6
MAX_HISTORY=20
```

---

## 四、Phase 5 核心结论（系统局限）

### 测试结果总结（5 个场景）

| 测试 | 结果 | 关键发现 |
|------|------|----------|
| 多步推理（天气→计算） | ✅ 成功 | ReAct 循环支持顺序多步任务 |
| 工具失败（查询纽约） | ✅ 优雅拒绝 | 模型能预判工具能力，避免盲目调用 |
| 嵌套推理（3 步链式） | ✅ 成功 | 当前 MessagesState 支持 3 步推理 |
| 并发需求（查三城） | ⚠️ 部分支持 | 模型能一次发 3 个请求，但 ToolNode 可能顺序执行 |
| 默认城市策略 | ✅ 成功 | 命令性 Prompt 覆盖模型"反问"习惯 |

### 两大核心局限

1. **隐式规划 = 不够可控**
   - 模型自己决定用哪个工具、何时用
   - 复杂任务可能跳步或重复
   - **OpenClaw 的解决方案**：显式 Agentic Loop（Think → Plan → Act → Observe → Iterate）

2. **工具执行可能是顺序瓶颈**
   - ToolNode 默认可能顺序执行多个工具
   - 涉及慢速 API 时性能低
   - **OpenClaw 的解决方案**：异步工具执行 + 并行节点路由

### 与 OpenClaw 的能力差距

| 维度 | 当前项目（Phase 5） | OpenClaw |
|------|---------------------|----------|
| **工具类型** | API 调用（计算、天气、时间）| 电脑操作（终端、文件、浏览器）|
| **规划方式** | 隐式（模型黑盒）| 显式 Loop（Think→Plan→Act→Observe）|
| **渠道接入** | 无（CLI 测试）| 10+ 渠道（WhatsApp/Telegram/Slack...）|
| **记忆** | SqliteSaver（会话级）| Markdown 文件（跨会话、学习习惯）|
| **安全** | 无沙箱 | Docker 隔离 + DM 配对 + 权限控制 |
| **主动性** | 被动响应 | 主动（cron/webhook/后台守护）|
| **多 Agent** | 单 Agent | Gateway 路由到多个隔离 Agent |

**下一步学习目标**：逐步填补这些能力差距

---

## 五、文件结构

```
aiagent/
├── agent/               # 正式源码包
│   ├── core.py          # LLM 配置 + 图构建
│   ├── tools.py         # 工具定义（calculate / time / weather）
│   └── cli.py           # CLI 交互循环 + SqliteSaver 持久化
├── tests/
│   ├── test_limits.py   # 5 个回归测试场景
│   └── llm_base_test.py # 大模型连通性测试
├── archive/             # 历史教学代码（Phase 1-3，仅供参考）
│   ├── hello_agent_v1.py
│   └── hello_agent_v2.py
├── main.py              # 启动入口（3 行完成组装）
├── CLAUDE.md / AGENTS.md / agent-context.md / notebook.md
├── .env
└── data/
    └── checkpoints/     # SQLite 持久化存储
        ├── checkpoints.db
        └── test_checkpoints.db
```

**依赖关系**（从底层到顶层）：
```
agent/tools.py  ←  被 agent/core、main、tests/ 引用
agent/core.py   ←  被 main、tests/ 引用
agent/cli.py    ←  被 main 引用
```

**启动方式**：
```bash
# 交互式对话
env -u HTTPS_PROXY -u HTTP_PROXY -u ALL_PROXY -u https_proxy -u http_proxy -u all_proxy \
  python main.py

# 回归测试
env -u HTTPS_PROXY -u HTTP_PROXY -u ALL_PROXY -u https_proxy -u http_proxy -u all_proxy \
  python tests/test_limits.py
```

---

## 六、协作规则（给 AI 助手）

### Claude 角色（导师 + 工程师合一）

**必读**：本文件（agent-context.md），了解当前进度、技术栈、核心结论。

**导师模式**（用户问概念 / 架构 / 方向时）：
- 讲清「为什么」，并联系 OpenClaw 真实做法
- 不直接给完整代码，引导用户自己推导
- 每次回答末尾说明下一步方向

**工程师模式**（用户要写代码 / 调试 / 重构时）：
- 优先点评问题，不整体重写
- 改动最小化，代码可运行、可理解、可扩展
- 关注 Agent 执行循环、Tool 抽象、Memory 扩展性

### 高效上下文使用原则
1. **必读**：本文件（agent-context.md）
2. **按需读**：
   - 如果讨论学习路径/概念 → 读 notebook.md
   - 如果讨论当前实现 → 读 main.py
   - 如果讨论测试结果 → 读 test_limits.py
3. **不要每次都读所有文件**

---

## 八、快速定位指南

| 我想... | 应该读哪个文件 |
|---------|---------------|
| 了解项目进度和技术栈 | 本文件（agent-context.md）|
| 查看详细学习过程 | notebook.md |
| 看当前可运行的代码 | main.py |
| 了解系统局限性 | 本文件第四节 + tests/test_limits.py |
| 查看工具定义 | agent/tools.py |
| 理解图结构 | 本文件 3.2 节 + agent/core.py |
| 查看配置 | .env + 本文件 3.4 节 |
| 运行回归测试 | `python tests/test_limits.py` |

---

## 九、后续阶段概览（Phase 7-10）

### Phase 7：显式规划循环

**目标**：把 Think → Plan → Act → Observe 变成独立的图节点

**当前问题**：
- 模型在隐式黑盒里做决策，我们无法看到"推理过程"
- 无法插入自定义规划逻辑（如：优先级排序、资源预估）

**OpenClaw 做法**：
- Think 节点：分析任务 + 查询记忆
- Plan 节点：拆解成可执行步骤（返回结构化计划）
- Act 节点：执行工具
- Observe 节点：解析结果 + 决定是否继续

**我们要做**：
- 把当前的 `agent` 节点拆成 4 个独立节点
- Plan 节点输出 JSON 格式的执行计划
- Observe 节点判断"任务完成"或"需要继续"

---

### Phase 8：电脑操作工具

**目标**：实现 `bash`、`file.read`、`file.write` 三个工具

**安全策略**（必须）：
1. 所有操作前必须经过 Phase 6 的 interrupt 确认
2. `bash` 工具禁止执行的命令：`rm -rf /`、`:(){ :|:& };:`（fork 炸弹）等
3. `file.write` 工具禁止写入系统目录（`/etc`、`/sys`、`/bin` 等）
4. 所有操作限制在 `~/.openclaw/workspace` 内

**OpenClaw 对比**：
- OpenClaw 用 Docker 沙箱隔离
- 我们用简单的路径检查 + 命令黑名单
- 重点是理解「电脑操作 Agent」的原理，而非生产级安全

**实现顺序**：
1. 先做 `file.read`（只读，最安全）
2. 再做 `bash`（执行简单命令，如 `ls`、`pwd`）
3. 最后做 `file.write`（可修改文件，最危险）

---

### Phase 9：持久记忆优化

**目标**：从"会话级记忆"升级到"跨会话知识库"

**当前问题**：
- SqliteSaver 只保存对话历史
- 重启后，Agent 不记得"用户偏好"（如：常用城市、回复风格）

**OpenClaw 做法**：
- Markdown 文件存储用户信息（`~/.openclaw/workspace/USER.md`）
- Agent 启动时读取 USER.md，注入到 SYSTEM_PROMPT
- Agent 可以调用 `memory.update` 工具更新 USER.md

**我们要做**：
1. 创建 `workspace/USER.md` 文件（用户偏好）
2. 创建 `workspace/FACTS.md` 文件（学到的知识）
3. Agent 启动时读取这些文件
4. 加 `memory.update` 工具，让 Agent 能写入 Markdown

---

### Phase 10：Telegram Bot 接入（可选）

**目标**：让 Agent 能在 Telegram 里使用（而不是 CLI）

**为什么选 Telegram**：
- SDK 简单（python-telegram-bot）
- 不需要手机号认证（WhatsApp 需要）
- 免费、无限制

**实现要点**：
1. 注册 Telegram Bot（通过 @BotFather）
2. 用 `python-telegram-bot` 监听消息
3. 把消息转成 HumanMessage 传给 Agent
4. 把 Agent 回复转成 Telegram 消息发送
5. 支持图片、文件上传

**OpenClaw 对比**：
- OpenClaw 用 Gateway WebSocket 统一管理多渠道
- 我们直接在主进程里集成 Telegram SDK
- 目的是理解"渠道接入"的原理，而非架构复杂度

---

**最后更新**：2026-03-09（Phase 6 代码重构 + 精简）
**下次更新时机**：Phase 7 完成后
