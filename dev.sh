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
  test)
    docker compose run --rm app python tests/test_limits.py
    ;;
  clean)
    docker compose down --rmi local
    ;;
  *)
    echo "用法: ./dev.sh [build|run|bash|test|clean]"
    echo ""
    echo "  build  构建镜像"
    echo "  run    启动交互式对话"
    echo "  bash   进入容器 bash"
    echo "  test   跑回归测试"
    echo "  clean  删除镜像和容器"
    ;;
esac
