#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# SERVER SETUP SCRIPT
# Executa a la màquina SERVIDOR (la que té Docker).
#
# Ús:
#   chmod +x scripts/server_start.sh
#   ./scripts/server_start.sh [direct|indirect|both] [api_replicas] [workers]
#
# Exemples:
#   ./scripts/server_start.sh both          # direct(3 APIs) + indirect(4 workers)
#   ./scripts/server_start.sh direct 4      # direct amb 4 rèpliques FastAPI
#   ./scripts/server_start.sh indirect  2   # indirect amb 2 workers
#   ./scripts/server_start.sh stop          # atura tot
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $*${NC}"; }
info() { echo -e "${BLUE}▶ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }
err()  { echo -e "${RED}✗ $*${NC}"; }

MODE="${1:-both}"
API_REPLICAS="${2:-3}"
WORKERS="${3:-4}"

# ─── Helpers ─────────────────────────────────────────────────────────────────

docker_cmd() {
    if docker "$@" 2>/dev/null; then return 0; fi
    sg docker -c "cd '$ROOT_DIR' && docker $*"
}

compose_direct()   { docker_cmd compose -p ticket-direct   -f docker/docker-compose.direct.yml   "$@"; }
compose_indirect() { docker_cmd compose -p ticket-indirect -f docker/docker-compose.indirect.yml "$@"; }

wait_healthy() {
    local service="$1" url="$2" retries="${3:-30}"
    info "Esperant que $service estigui llest..."
    for i in $(seq 1 "$retries"); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            ok "$service llest"; return 0
        fi
        sleep 2
    done
    err "$service no respon a $url després de $((retries*2))s"
    return 1
}

show_ip() {
    local ip
    ip=$(hostname -I 2>/dev/null | awk '{print $1}') || ip="<IP_SERVIDOR>"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  IP d'aquest servidor: ${YELLOW}${ip}${NC}"
    echo ""
    if [ "$MODE" = "direct" ] || [ "$MODE" = "both" ]; then
        echo "  Direct API (NGINX):  http://${ip}:80"
        echo "  Health check:        curl http://${ip}/health"
    fi
    if [ "$MODE" = "indirect" ] || [ "$MODE" = "both" ]; then
        echo "  RabbitMQ AMQP:       ${ip}:5672"
        echo "  RabbitMQ Web UI:     http://${ip}:15672  (guest/guest)"
    fi
    echo ""
    echo "  Des del CLIENT executa:"
    if [ "$MODE" = "direct" ] || [ "$MODE" = "both" ]; then
        echo "    ./scripts/run_all_benchmarks.sh true false false ${ip}"
    else
        echo "    RABBITMQ_HOST=${ip} ./scripts/run_all_benchmarks.sh true true false ${ip}"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# ─── Verificar Docker ─────────────────────────────────────────────────────────

check_docker() {
    if ! command -v docker &>/dev/null; then
        err "Docker no instal·lat. Executa primer: ./scripts/setup_docker.sh"
        exit 1
    fi
    if ! docker ps &>/dev/null && ! sg docker -c "docker ps" &>/dev/null; then
        err "Docker daemon no accessible. Executa: ./scripts/setup_docker.sh"
        exit 1
    fi
    ok "Docker OK"
}

# ─── Accions ─────────────────────────────────────────────────────────────────

start_direct() {
    info "Arrencant arquitectura directa (${API_REPLICAS} rèpliques FastAPI + NGINX + Redis)..."
    compose_direct up -d --build --scale api="$API_REPLICAS"
    wait_healthy "NGINX/FastAPI" "http://localhost/health" 30
    ok "Arquitectura directa activa amb ${API_REPLICAS} rèpliques"
}

start_indirect() {
    info "Arrencant arquitectura indirecta (${WORKERS} workers + RabbitMQ + Redis)..."
    compose_indirect up -d --build --scale worker="$WORKERS"

    # Esperar RabbitMQ (port 5672 intern al contenidor, 5672 al host)
    info "Esperant RabbitMQ..."
    for i in $(seq 1 40); do
        if docker_cmd compose -f docker/docker-compose.indirect.yml exec -T rabbitmq \
            rabbitmq-diagnostics check_port_connectivity &>/dev/null; then
            ok "RabbitMQ llest"; break
        fi
        sleep 3
    done
    ok "Arquitectura indirecta activa amb ${WORKERS} workers"
}

stop_all() {
    info "Aturant arquitectura directa..."
    compose_direct down --remove-orphans 2>/dev/null || true
    info "Aturant arquitectura indirecta..."
    compose_indirect down --remove-orphans 2>/dev/null || true
    ok "Tots els serveis aturats"
    exit 0
}

status_all() {
    echo ""
    echo "═══ Directa ═══"
    compose_direct ps 2>/dev/null || echo "  (no en execució)"
    echo ""
    echo "═══ Indirecta ═══"
    compose_indirect ps 2>/dev/null || echo "  (no en execució)"
    echo ""
    exit 0
}

# ─── Main ────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Ticket System – Server Start Script    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

check_docker

case "$MODE" in
    direct)   start_direct ;;
    indirect) start_indirect ;;
    both)     start_direct; start_indirect ;;
    stop)     stop_all ;;
    status)   status_all ;;
    *)
        err "Mode desconegut: $MODE"
        echo "Ús: $0 [direct|indirect|both|stop|status] [api_replicas] [workers]"
        exit 1
        ;;
esac

show_ip
