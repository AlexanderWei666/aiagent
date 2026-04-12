# Dev Container 开发环境配置教程

> 适用系统：Windows 11 + WSL2 + Docker Desktop + VS Code  
> 针对中国大陆网络环境优化  
> 当前方案：**单文件 devcontainer.json**，无 Dockerfile、无 docker-compose

---

## 概览

```
宿主机（Windows）
└── Docker Desktop（Engine 运行在 docker-desktop WSL2 虚拟机里）
    └── Dev Container（python:3.12-trixie 镜像）
        ├── 项目代码（bind mount，实时同步）
        ├── ~/.claude（bind mount，Claude Code 登录态持久化）
        └── VS Code Server（在容器内运行）
```

---

## Step 1 — 安装 Docker Desktop

1. 下载安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. 打开 Docker Desktop → **Settings → Resources → WSL Integration**
3. 勾选你的 Ubuntu 发行版（如 Ubuntu-22.04）→ Apply & Restart
4. 在 WSL 中验证：

```bash
docker --version
```

> Docker Desktop 在 Windows 侧管理，Engine 运行在它托管的虚拟机里。你的 Ubuntu 通过 WSL Integration 共享 socket，无需在 Ubuntu 内安装任何 Docker 组件，也无需处理 sudo 免密。

---

## Step 2 — 配置 Docker 镜像加速

在 Docker Desktop → **Settings → Docker Engine**，加入国内镜像源：

```json
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
```

Apply & Restart 后验证：

```bash
docker info | grep -A5 "Registry Mirrors"
```

> 国内镜像源可能随时失效，失效时搜索「docker 镜像加速」获取最新地址，更新后重启 Docker Desktop 即可。

---

## Step 3 — 安装 VS Code 扩展

安装 **Dev Containers**（`ms-vscode-remote.remote-containers`）扩展。

---

## Step 4 — 打开 Dev Container

1. VS Code 打开项目根目录（`aiagent/`）
2. `F1` → **Dev Containers: Reopen in Container**
3. 首次启动会拉取镜像并执行 `postCreateCommand`，约 2-5 分钟

**自动完成的事情**（`postCreateCommand` 里已配好）：
- pip 切换阿里云镜像源
- npm 切换 npmmirror 源
- 安装 `requirements.txt` 中的 Python 依赖
- 安装 Claude Code CLI（`@anthropic-ai/claude-code`）

**自动挂载的内容**（`devcontainer.json` 里已配好）：
- 项目代码（`workspaceMount`）→ 与宿主机实时同步，改代码不需要重建容器
- `~/.claude` → Claude Code 登录态跨容器重建持久保留

---

## Step 5 — 配置环境变量

容器内项目根目录下创建 `.env`（已在 `.gitignore` 里，不会提交）：

```bash
cp .env.example .env
# 然后填入你的 API Key
```

`.env` 内容示例：

```bash
LLM_PROVIDER=openai
LLM_MODEL=qwen-flash
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=<your-key>
LLM_TEMPERATURE=0.6
MAX_HISTORY=20
```

---

## Step 6 — 验证环境

```bash
# 验证 Python 依赖
python -c "import langgraph; print('OK')"

# 验证 Claude Code
claude --version

# 运行项目
env -u HTTPS_PROXY -u HTTP_PROXY -u ALL_PROXY -u https_proxy -u http_proxy -u all_proxy \
  python main.py

# 运行测试
env -u HTTPS_PROXY -u HTTP_PROXY -u ALL_PROXY -u https_proxy -u http_proxy -u all_proxy \
  python tests/test_limits.py
```

> `env -u` 临时取消代理变量，避免代理干扰 LLM API 请求。

---

## 常见操作

| 操作 | 方式 |
|------|------|
| 进入 Dev Container | VS Code `F1` → Dev Containers: Reopen in Container |
| 回到本地 WSL | VS Code `F1` → Dev Containers: Reopen Folder Locally |
| 重建容器（改了 devcontainer.json）| VS Code `F1` → Dev Containers: Rebuild Container |
| 重建并清缓存 | VS Code `F1` → Dev Containers: Rebuild Container Without Cache |
| 查看容器日志 | Docker Desktop → Containers → 找到对应容器 |
| 手动进入容器 shell | `docker exec -it <container-id> bash` |

---

## 当前 devcontainer.json 说明

```
.devcontainer/devcontainer.json
```

关键字段：

| 字段 | 值 | 含义 |
|------|-----|------|
| `image` | `mcr.microsoft.com/devcontainers/python:3-3.12-trixie` | 直接用预构建镜像，不需要 Dockerfile |
| `workspaceMount` | 与宿主机同路径 bind mount | 代码实时同步，路径一致 |
| `features` | node:1 | 注入 Node.js，用于运行 Claude Code CLI |
| `postCreateCommand` | pip/npm 换源 + 安装依赖 | 容器首次创建后自动执行 |
| `mounts` | `~/.claude` bind mount | Claude Code 登录态持久化 |

---

## 故障排查

**镜像拉不下来**
→ 检查 Docker Desktop 是否配了镜像加速（Step 2），或换一个可用的镜像源。

**pip 安装失败**
→ 容器内手动运行：`pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/`

**Claude Code 未登录**
→ 容器内运行 `claude`，按提示完成认证。认证信息存在 `~/.claude`（已 bind mount，下次重建容器无需重新登录）。

**代理干扰 API 请求**
→ 运行命令前加 `env -u HTTPS_PROXY -u HTTP_PROXY -u ALL_PROXY -u https_proxy -u http_proxy -u all_proxy`（见 Step 6）。
