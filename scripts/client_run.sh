#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CLIENT RUN SCRIPT
# Executa a la màquina CLIENT (la que NO té Docker).
# Envia el benchmark contra el servidor remot.
#
# Ús:
#   chmod +x scripts/client_run.sh
#   ./scripts/client_run.sh <IP_SERVIDOR> [all|direct|indirect|contention]
#
# Exemples:
#   ./scripts/client_run.sh 192.168.1.10             # tot: direct + indirect
#   ./scripts/client_run.sh 192.168.1.10 direct      # només directa
#   ./scripts/client_run.sh 192.168.1.10 indirect    # només indirecta
#   ./scripts/client_run.sh 192.168.1.10 contention  # alta contenció
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $*${NC}"; }
info() { echo -e "${BLUE}▶ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }
err()  { echo -e "${RED}✗ $*${NC}"; exit 1; }

SERVER_IP="${1:-}"
MODE="${2:-all}"

if [ -z "$SERVER_IP" ]; then
    err "Cal indicar la IP del servidor.\nÚs: $0 <IP_SERVIDOR> [all|direct|indirect|contention]"
fi

API_URL="http://${SERVER_IP}:80"
export RABBITMQ_HOST="$SERVER_IP"
export RABBITMQ_PORT="${RABBITMQ_PORT:-5672}"
export RABBITMQ_USER="${RABBITMQ_USER:-guest}"
export RABBITMQ_PASS="${RABBITMQ_PASS:-guest}"
export RABBITMQ_VHOST="${RABBITMQ_VHOST:-/}"
# Redis no s'exposa al client; els workers del servidor s'hi connecten internament.

CONCURRENCIES=(1 2 4 8 16 32 50)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p results/direct/unnumbered results/direct/numbered \
         results/indirect/unnumbered results/indirect/numbered \
         results/direct/numbered/contention results/indirect/numbered/contention \
         results/plots

# ─── Detectar Python ─────────────────────────────────────────────────────────

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    PYTHON="$ROOT_DIR/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
elif command -v python &>/dev/null; then
    PYTHON="$(command -v python)"
else
    err "No s'ha trobat cap intèrpret Python."
fi

# ─── Instal·lar dependències si cal ──────────────────────────────────────────

ensure_deps() {
    if ! "$PYTHON" -c "import requests, pika, fastapi" &>/dev/null; then
        warn "Instal·lant dependències Python..."
        "$PYTHON" -m pip install -r requirements.txt -q
        ok "Dependències instal·lades"
    fi
}

# ─── Verificar connectivitat ─────────────────────────────────────────────────

check_direct() {
    info "Verificant API directa a ${API_URL}..."
    if ! curl -fsS "${API_URL}/health" >/dev/null; then
        err "No es pot connectar a ${API_URL}/health\nAssegura't que el servidor té ./scripts/server_start.sh direct en execució."
    fi
    ok "API directa accessible"
}

check_indirect() {
    info "Verificant RabbitMQ a ${SERVER_IP}:${RABBITMQ_PORT}..."
    if ! timeout 3 bash -c "</dev/tcp/${SERVER_IP}/${RABBITMQ_PORT}" 2>/dev/null; then
        err "No es pot connectar a RabbitMQ ${SERVER_IP}:${RABBITMQ_PORT}\nAssegura't que el servidor té ./scripts/server_start.sh indirect en execució."
    fi
    ok "RabbitMQ accessible"
}

# ─── Reset estat remot ────────────────────────────────────────────────────────

reset_direct() {
    curl -fsS -X POST "${API_URL}/reset" >/dev/null 2>&1 || warn "Reset de l'API ha fallat (no crític)"
}

reset_indirect() {
    "$PYTHON" - <<PY
import os, urllib.parse, pika, time

host  = os.environ["RABBITMQ_HOST"]
port  = int(os.environ.get("RABBITMQ_PORT", 5672))
user  = os.environ.get("RABBITMQ_USER", "guest")
pw    = os.environ.get("RABBITMQ_PASS", "guest")
vhost = urllib.parse.quote(os.environ.get("RABBITMQ_VHOST", "/"), safe="")

url = f"amqp://{user}:{pw}@{host}:{port}/{vhost}"
try:
    conn = pika.BlockingConnection(pika.URLParameters(url))
    ch = conn.channel()
    for q in ("ticket_purchases", "ticket_responses"):
        ch.queue_declare(queue=q, durable=True)
        ch.queue_purge(queue=q)
    conn.close()
    print("Cues RabbitMQ purgades")
except Exception as e:
    print(f"Avís: no s'han pogut purgar les cues: {e}")
PY
}

# ─── Execució benchmarks ──────────────────────────────────────────────────────

run_direct_matrix() {
    check_direct
    info "Benchmark DIRECTE — matriu completa"
    echo "Concurrències: ${CONCURRENCIES[*]}"
    echo ""

    for TICKET_TYPE in unnumbered numbered; do
        if [ "$TICKET_TYPE" = "unnumbered" ]; then
            WORKLOAD="benchmarks/benchmark_unnumbered_20000.txt"
        else
            WORKLOAD="benchmarks/benchmark_numbered_60000.txt"
        fi

        for C in "${CONCURRENCIES[@]}"; do
            OUTPUT="results/direct/${TICKET_TYPE}/c${C}_${TIMESTAMP}.json"
            info "  Direct | ${TICKET_TYPE} | concurrència=${C}"

            reset_direct

            "$PYTHON" -m src.main \
                --mode benchmark-direct \
                --ticket-type "$TICKET_TYPE" \
                --workload "$WORKLOAD" \
                --concurrent-clients "$C" \
                --api-url "$API_URL" \
                --output "$OUTPUT" && ok "    → $OUTPUT" || warn "    ✗ Ha fallat (continua)"
        done
    done
    ok "Benchmark directe completat"
}

run_indirect_matrix() {
    check_indirect
    info "Benchmark INDIRECTE — matriu completa"
    echo "Concurrències: ${CONCURRENCIES[*]}"
    echo ""

    for TICKET_TYPE in unnumbered numbered; do
        if [ "$TICKET_TYPE" = "unnumbered" ]; then
            WORKLOAD="benchmarks/benchmark_unnumbered_20000.txt"
        else
            WORKLOAD="benchmarks/benchmark_numbered_60000.txt"
        fi

        for C in "${CONCURRENCIES[@]}"; do
            OUTPUT="results/indirect/${TICKET_TYPE}/c${C}_${TIMESTAMP}.json"
            info "  Indirect | ${TICKET_TYPE} | concurrència=${C}"

            reset_indirect

            "$PYTHON" -m src.main \
                --mode benchmark-indirect \
                --ticket-type "$TICKET_TYPE" \
                --workload "$WORKLOAD" \
                --concurrent-clients "$C" \
                --output "$OUTPUT" && ok "    → $OUTPUT" || warn "    ✗ Ha fallat (continua)"
        done
    done
    ok "Benchmark indirecte completat"
}

run_contention() {
    WORKLOAD="benchmarks/benchmark_numbered_contention.txt"
    if [ ! -f "$WORKLOAD" ]; then
        warn "Generant workload de contenció..."
        "$PYTHON" scripts/generate_contention_benchmark.py --output "$WORKLOAD"
    fi

    info "Benchmark ALTA CONTENCIÓ — directa + indirecta"

    for C in "${CONCURRENCIES[@]}"; do
        if curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
            OUTPUT="results/direct/numbered/contention/c${C}_${TIMESTAMP}.json"
            info "  Contention Direct | concurrència=${C}"
            reset_direct
            "$PYTHON" -m src.main \
                --mode benchmark-direct \
                --ticket-type numbered \
                --workload "$WORKLOAD" \
                --concurrent-clients "$C" \
                --api-url "$API_URL" \
                --output "$OUTPUT" && ok "    → $OUTPUT" || warn "    ✗ Ha fallat"
        fi

        if timeout 3 bash -c "</dev/tcp/${SERVER_IP}/${RABBITMQ_PORT}" 2>/dev/null; then
            OUTPUT="results/indirect/numbered/contention/c${C}_${TIMESTAMP}.json"
            info "  Contention Indirect | concurrència=${C}"
            reset_indirect
            "$PYTHON" -m src.main \
                --mode benchmark-indirect \
                --ticket-type numbered \
                --workload "$WORKLOAD" \
                --concurrent-clients "$C" \
                --output "$OUTPUT" && ok "    → $OUTPUT" || warn "    ✗ Ha fallat"
        fi
    done
    ok "Benchmark de contenció completat"
}

generate_plots() {
    info "Generant gràfiques..."
    "$PYTHON" scripts/plot_results.py && ok "Gràfiques a results/plots/"
}

# ─── Main ─────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Ticket System – Client Benchmark Run  ║"
echo "╚══════════════════════════════════════════╝"
echo ""
info "Servidor: ${SERVER_IP}"
info "Mode:     ${MODE}"
echo ""

ensure_deps

case "$MODE" in
    all)
        run_direct_matrix
        echo ""
        run_indirect_matrix
        echo ""
        run_contention
        ;;
    direct)
        run_direct_matrix ;;
    indirect)
        run_indirect_matrix ;;
    contention)
        run_contention ;;
    plots)
        generate_plots; exit 0 ;;
    *)
        err "Mode desconegut: ${MODE}\nOpcions: all | direct | indirect | contention | plots"
        ;;
esac

echo ""
generate_plots

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Tots els benchmarks completats!"
echo "  Resultats: results/direct/  i  results/indirect/"
echo "  Gràfiques: results/plots/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
