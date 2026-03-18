# WSL2 + Docker CE 开发环境配置教程

> 适用系统：Windows 11 + WSL2（Ubuntu 22.04）  
> 语言无关，针对中国大陆网络环境优化

---

## 前置条件

- Windows 11 已安装 WSL2
- VSCode 已安装 Remote - WSL 扩展

---

## Step 0 — 确认 Ubuntu 版本

```bash
lsb_release -cs
```

本教程以 `jammy`（Ubuntu 22.04）为例。其他版本将后续命令中的 `jammy` 替换为对应代号：

| 版本 | 代号 |
|------|------|
| 20.04 | focal |
| 22.04 | jammy |
| 24.04 | noble |

---

## Step 1 — WSL 换源

```bash
# 备份原始源
sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak

# 替换为阿里云源
sudo tee /etc/apt/sources.list > /dev/null <<'EOF'
deb https://mirrors.aliyun.com/ubuntu/ jammy main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ jammy-updates main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ jammy-backports main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ jammy-security main restricted universe multiverse
EOF

# 验证
sudo apt update && echo "换源成功"
```

---

## Step 2 — 安装 Docker CE

```bash
# 清理旧版本
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# 安装依赖
sudo apt install -y ca-certificates curl gnupg lsb-release

# 添加 Docker GPG 密钥（阿里云托管的 Docker 官方密钥，用于验证包来源）
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 添加 Docker APT 源（阿里云）
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://mirrors.aliyun.com/docker-ce/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 免 sudo 使用 docker
sudo usermod -aG docker $USER
newgrp docker

# 验证
docker --version && echo "Docker 安装成功"
```

---

## Step 3 — Docker 镜像加速 & 自启

```bash
# 配置镜像加速
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
EOF

# 启动 Docker
sudo service docker start

# WSL 每次启动自动拉起 Docker
grep -qxF 'sudo service docker start > /dev/null 2>&1' ~/.bashrc || \
  echo 'sudo service docker start > /dev/null 2>&1' >> ~/.bashrc

# 验证
docker info | grep -A5 "Registry Mirrors"
```

> 国内镜像源可能随时失效，失效时搜索"docker 镜像加速"获取最新地址，更新 `daemon.json` 后重启 Docker 即可。

---

## Step 4 — 免密启动 Docker

WSL 自启 Docker 时会反复要求输入 sudo 密码，通过以下方式解决：

```bash
# 写入免密规则
echo "$USER ALL=(ALL) NOPASSWD: /usr/sbin/service docker start" | \
  sudo tee /etc/sudoers.d/docker-service

# 验证语法（输出 parsed OK 才继续）
sudo visudo -c -f /etc/sudoers.d/docker-service

# 测试（不应再要求密码）
sudo service docker start
```

回退方案：

```bash
sudo rm /etc/sudoers.d/docker-service
```

> **可选**：开启 WSL2 systemd 后 Docker 会随系统自启，可替代以上方案：
> ```bash
> sudo tee /etc/wsl.conf > /dev/null <<'EOF'
> [boot]
> systemd=true
> EOF
> ```
> 在 Windows 执行 `wsl --shutdown` 重启 WSL 后生效。

---

## Step 5 — Dockerfile 模板

> 按你的语言选择对应模板，核心是**在构建阶段换源**，宿主机不安装任何运行时。

**Python**
```dockerfile
FROM python:3.12-slim

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
```

**Node.js**
```dockerfile
FROM node:20-slim

RUN npm config set registry https://registry.npmmirror.com

WORKDIR /app
COPY package*.json .
RUN npm ci

CMD ["node", "index.js"]
```

**Java（Maven）**
```dockerfile
FROM maven:3.9-eclipse-temurin-21-alpine

COPY settings.xml /root/.m2/settings.xml

WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline

COPY src ./src
RUN mvn package -DskipTests

CMD ["java", "-jar", "target/app.jar"]
```

`settings.xml`（Maven 阿里云镜像）：
```xml
<settings>
  <mirrors>
    <mirror>
      <id>aliyun</id>
      <mirrorOf>central</mirrorOf>
      <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
  </mirrors>
</settings>
```

---

## Step 6 — docker-compose.yml 模板

```yaml
services:
  app:
    build: .
    container_name: your-project
    volumes:
      - .:/app          # 代码实时挂载，改代码不需要重新 build
    working_dir: /app
    stdin_open: true
    tty: true
    command: <你的启动命令>
```

---

## Step 7 — 快捷脚本 dev.sh

```bash
cat > dev.sh <<'EOF'
#!/bin/bash

case "$1" in
  build)
    docker compose build
    ;;
  run)
    docker compose run --rm app
    ;;
  bash)
    docker compose run --rm app bash
    ;;
  clean)
    docker compose down --rmi local
    ;;
  *)
    echo "用法: ./dev.sh [build|run|bash|clean]"
    echo ""
    echo "  build  构建镜像（首次或修改依赖文件后执行）"
    echo "  run    启动容器"
    echo "  bash   进入容器调试"
    echo "  clean  删除镜像和容器"
    ;;
esac
EOF

chmod +x dev.sh
```

---

## 常用命令速查

| 操作 | 命令 |
|------|------|
| 构建镜像 | `docker compose build` |
| 构建（详细日志） | `docker compose build --progress=plain` |
| 启动容器 | `docker compose run --rm app` |
| 进入容器调试 | `docker compose run --rm app bash` |
| 查看运行中容器 | `docker ps` |
| 查看所有镜像 | `docker images` |
| 删除镜像 | `docker rmi <image-name>` |
| 清理悬空资源 | `docker system prune` |
