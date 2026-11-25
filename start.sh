#!/usr/bin/env bash
# One-click start for Git Bash / macOS / Linux
#   ./start.sh          # 默认 8000，占用则顺延
#   ./start.sh 9000     # 指定端口
#   ./start.sh dev      # 后端热重载
set -e
cd "$(dirname "$0")"

MODE="prod"; PORT=""
if [ "$1" = "dev" ]; then MODE="dev"; elif [ -n "$1" ]; then PORT="$1"; fi

command -v uv >/dev/null 2>&1 || { echo "[x] 未找到 uv，安装：curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }

if [ -x ".venv/Scripts/python.exe" ] || [ -x ".venv/bin/python" ]; then
  echo "[*] 同步依赖…"; uv sync --quiet
else
  echo "[*] 首次运行：创建虚拟环境…"; uv sync --python 3.13
fi

if [ ! -f "web/dist/index.html" ]; then
  echo "[*] 构建前端…"; (cd web && { [ -d node_modules ] || pnpm install; } && pnpm build)
fi

if [ -z "$PORT" ]; then
  PORT=8000
  while (command -v netstat >/dev/null && netstat -ano 2>/dev/null | grep -q ":$PORT .*LISTENING"); do
    PORT=$((PORT+1)); [ $PORT -gt 8020 ] && { echo "[x] 8000-8020 无空闲端口"; exit 1; }
  done
fi

echo "============================================================"
echo "  URL      http://127.0.0.1:$PORT/"
echo "  API      http://127.0.0.1:$PORT/api/overview"
echo "  MODE     $MODE"
echo "  Stop     Ctrl+C"
echo "============================================================"

( sleep 3; command -v start >/dev/null && start "" "http://127.0.0.1:$PORT/" || true ) >/dev/null 2>&1 &

if [ "$MODE" = "dev" ]; then
  exec uv run dash --port "$PORT" --reload
else
  exec uv run dash --port "$PORT"
fi
