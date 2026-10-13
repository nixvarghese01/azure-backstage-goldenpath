#!/bin/bash
# Start/stop the local platform inside Ubuntu (WSL2) with Docker Engine: Backstage, Azure discovery,
# the orchestrator API and worker, migrations and PostgreSQL, with mock Azure and GitHub.
# Nothing is provisioned in Azure and nothing is published to GitHub.
#
#   platform.sh up [--build]   start the stack (builds images the first time), wait until healthy
#   platform.sh down           stop the stack; data stays in the postgres volume
#   platform.sh restart        down, then up
#   platform.sh status         containers, health and the URLs
#   platform.sh logs [svc]     follow logs (all services, or one)
#   platform.sh reset          down and delete the postgres volume (asks first)
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
COMPOSE=(docker compose -f "$ROOT/deploy/local/docker-compose.yml")

need_docker() {
  if ! docker info >/dev/null 2>&1; then
    echo "== starting Docker"
    sudo systemctl start docker
  fi
}

wait_healthy() {
  local deadline=$((SECONDS + ${1:-600})) unhealthy
  echo "== waiting for the services to become healthy (first start builds the Backstage image)"
  while :; do
    unhealthy=$("${COMPOSE[@]}" ps --format '{{.Service}} {{.State}} {{.Health}}' |
      awk '$2 != "running" && $2 != "exited" || ($3 != "" && $3 != "healthy") {print $1"("$2" "$3")"}')
    # A one-shot job (migrations) exits; it must have exited cleanly.
    if "${COMPOSE[@]}" ps -a --format '{{.Service}} {{.State}} {{.ExitCode}}' | awk '$2 == "exited" && $3 != 0 {found=1} END {exit !found}'; then
      echo "a one-shot container failed:"; "${COMPOSE[@]}" ps -a; return 1
    fi
    [ -z "$unhealthy" ] && return 0
    if [ "$SECONDS" -ge "$deadline" ]; then echo "still not healthy: $unhealthy"; return 1; fi
    sleep 5
  done
}

urls() {
  cat <<'EOF'

Local platform is up (mock Azure and GitHub, guest sign-in):
  Backstage    http://localhost:7007   (Create -> Application starter)
  PostgreSQL   localhost:5432
Discovery and the orchestrator are internal to the Compose network; reach them through Backstage.
Stop it with: make down   (Windows: .\scripts\local\platform.ps1 down)
EOF
}

case "${1:-}" in
  up)
    need_docker
    build=(); [ "${2:-}" = "--build" ] && build=(--build)
    "${COMPOSE[@]}" up -d "${build[@]}"
    wait_healthy 900
    "${COMPOSE[@]}" ps --format 'table {{.Service}}\t{{.State}}\t{{.Health}}'
    urls ;;
  down)
    "${COMPOSE[@]}" down ;;
  restart)
    "$0" down; "$0" up "${@:2}" ;;
  status)
    need_docker
    "${COMPOSE[@]}" ps -a --format 'table {{.Service}}\t{{.State}}\t{{.Health}}\t{{.Ports}}'
    printf '  %-28s %s\n' "localhost:7007/healthcheck" "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:7007/healthcheck || true)" ;;
  logs)
    "${COMPOSE[@]}" logs -f --tail 100 ${2:+"$2"} ;;
  reset)
    read -r -p "Delete the local platform's database volume? [y/N] " answer
    [ "$answer" = "y" ] || { echo "kept"; exit 0; }
    "${COMPOSE[@]}" down -v ;;
  *)
    sed -n '2,13p' "$0"; exit 2 ;;
esac
