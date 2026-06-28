#!/usr/bin/env bash
# Builds and runs the containerized app (backend + built frontend, one image,
# one port). Ctrl+C stops and removes the container, leaving no artifacts
# behind - mirrors the pattern in /home/clif/repositories/pgexplore/pgexplore.sh.
#
# Usage: ./docker.sh [mount_dir]
# mount_dir (default: $HOME) is bind-mounted into the container at the exact
# same absolute path, so paths typed into the app (script files, images,
# render output) resolve identically inside and outside the container. Only
# files under mount_dir are reachable from inside the container.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOUNT_DIR="${1:-$HOME}"

IMAGE="tutorial-video-pipeline:latest"
CONTAINER_NAME="tutorial-video-pipeline-$(date +%s)"
PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('', 0)); p=s.getsockname()[1]; s.close(); print(p)")

docker build -t "$IMAGE" -f "$ROOT_DIR/Dockerfile" "$ROOT_DIR"

cleanup() {
  echo ""
  echo "Stopping..."
  docker stop "$CONTAINER_NAME" 2>/dev/null || true
  docker rm "$CONTAINER_NAME" 2>/dev/null || true
  echo "Done. No artifacts left."
  exit 0
}

trap cleanup SIGINT SIGTERM

ENV_FILE_ARGS=()
if [[ -f "$ROOT_DIR/backend/.env" ]]; then
  ENV_FILE_ARGS=(--env-file "$ROOT_DIR/backend/.env")
fi

# The "${ENV_FILE_ARGS[@]+"${ENV_FILE_ARGS[@]}"}" form below (not plain
# "${ENV_FILE_ARGS[@]}") matters: bash before 4.3 treats expanding an *empty* array
# under `set -u` as an unbound-variable error - exactly the no-.env case, which is
# the common one. macOS still ships bash 3.2 by default.
docker run \
  --name "$CONTAINER_NAME" \
  --rm \
  --user "$(id -u):$(id -g)" \
  -p "${PORT}:8080" \
  -v "$MOUNT_DIR:$MOUNT_DIR" \
  "${ENV_FILE_ARGS[@]+"${ENV_FILE_ARGS[@]}"}" \
  "$IMAGE" &

DOCKER_PID=$!

echo ""
echo "tutorial_video_pipeline → http://localhost:$PORT"
echo "Mounted directory: $MOUNT_DIR"
echo "Press Ctrl+C to stop"
echo ""

until curl -sf "http://localhost:$PORT" &>/dev/null; do
  sleep 0.2
done

if command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:$PORT"
elif command -v open &>/dev/null; then
  open "http://localhost:$PORT"
else
  echo "Open in browser: http://localhost:$PORT"
fi

wait "$DOCKER_PID"
