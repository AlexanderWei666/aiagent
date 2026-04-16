FROM mcr.microsoft.com/devcontainers/python:3-3.12-trixie

ARG DEBIAN_MIRROR=mirrors.tuna.tsinghua.edu.cn
ARG PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PYPI_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

# 切换 Debian 源到国内镜像
RUN set -eux; \
    find /etc/apt -type f \( -name '*.sources' -o -name 'sources.list' \) -print0 \
    | xargs -0 -r sed -i \
    -e "s|http://deb.debian.org/debian|https://${DEBIAN_MIRROR}/debian|g" \
    -e "s|http://security.debian.org/debian-security|https://${DEBIAN_MIRROR}/debian-security|g" \
    -e "s|http://deb.debian.org/debian-security|https://${DEBIAN_MIRROR}/debian-security|g" \
    -e "s|https://deb.debian.org/debian|https://${DEBIAN_MIRROR}/debian|g" \
    -e "s|https://security.debian.org/debian-security|https://${DEBIAN_MIRROR}/debian-security|g" \
    -e "s|https://deb.debian.org/debian-security|https://${DEBIAN_MIRROR}/debian-security|g"

# 配置 pip 国内镜像 + 升级 pip
RUN pip config --global set global.index-url ${PYPI_INDEX_URL} \
    && pip config --global set global.trusted-host ${PYPI_TRUSTED_HOST} \
    && pip install --upgrade pip

# 安装 Node.js / npm（Codex CLI 需要）
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm bubblewrap\
    && rm -rf /var/lib/apt/lists/*

# 安装 Claude Code CLI（native installer，需先设 WORKDIR 否则 root 下会卡死）
WORKDIR /tmp
RUN curl -fsSL https://claude.ai/install.sh | bash -s -- 2.1.104

# 安装 Codex CLI
RUN npm install -g @openai/codex@0.121.0

# 单独 COPY requirements.txt，内容不变则跳过安装（利用层缓存）
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
