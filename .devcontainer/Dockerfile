FROM mcr.microsoft.com/devcontainers/python:3-3.12-trixie

ARG DEBIAN_MIRROR=mirrors.tuna.tsinghua.edu.cn
ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PYPI_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

# 切换 Debian 源到国内镜像，后续 apt 安装都会走国内。
RUN set -eux; \
    find /etc/apt -type f \( -name '*.sources' -o -name 'sources.list' \) -print0 \
    | xargs -0 -r sed -i \
    -e "s|http://deb.debian.org/debian|https://${DEBIAN_MIRROR}/debian|g" \
    -e "s|http://security.debian.org/debian-security|https://${DEBIAN_MIRROR}/debian-security|g" \
    -e "s|http://deb.debian.org/debian-security|https://${DEBIAN_MIRROR}/debian-security|g" \
    -e "s|https://deb.debian.org/debian|https://${DEBIAN_MIRROR}/debian|g" \
    -e "s|https://security.debian.org/debian-security|https://${DEBIAN_MIRROR}/debian-security|g" \
    -e "s|https://deb.debian.org/debian-security|https://${DEBIAN_MIRROR}/debian-security|g"

# 安装 Node.js（用阿里云镜像，绕开 nodejs.org 网络问题）
RUN curl -fsSL https://mirrors.aliyun.com/nodejs-release/v20.19.0/node-v20.19.0-linux-x64.tar.xz \
    | tar -xJ -C /usr/local --strip-components=1

# 配置 pip 国内镜像 + 升级 pip
RUN pip config set global.index-url ${PYPI_INDEX_URL} \
    && pip config set global.trusted-host ${PYPI_TRUSTED_HOST} \
    && pip install --upgrade pip

# 将 npm 镜像与 Claude Code CLI 安装放到镜像构建层，利用 Docker 缓存。
RUN npm config set registry ${NPM_REGISTRY} \
    && npm install -g @anthropic-ai/claude-code

# 单独 COPY requirements.txt，内容不变则跳过安装（利用层缓存）
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt