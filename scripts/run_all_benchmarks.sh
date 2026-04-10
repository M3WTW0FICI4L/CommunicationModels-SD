#!/usr/bin/env bash
# Complete benchmark orchestration script
# Sets up Docker, launches both architectures, runs benchmarks, and collects results

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log_section() {
    echo ""
    echo -e "${BLUE}===== $* =====${NC}"
    echo ""
}

log_success() {
    echo -e "${GREEN}✓ $*${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠ $*${NC}"
}

log_error() {
    echo -e "${RED}✗ $*${NC}"
}

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    log_error "No Python interpreter found (.venv/bin/python, python3, python)"
    exit 1
fi

if [ -x "$ROOT_DIR/.venv/bin/pip" ]; then
    PIP_BIN="$ROOT_DIR/.venv/bin/pip"
else
    PIP_BIN="$PYTHON_BIN -m pip"
fi

CONCURRENCY_LEVELS=(1 2 4 8 16 32 50)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR_DIRECT="results/direct"
RESULTS_DIR_INDIRECT="results/indirect"
CONTENTION_RUNNER="$SCRIPT_DIR/run_contention_benchmark.sh"

mkdir -p "$RESULTS_DIR_DIRECT/unnumbered" "$RESULTS_DIR_DIRECT/numbered"
mkdir -p "$RESULTS_DIR_INDIRECT/unnumbered" "$RESULTS_DIR_INDIRECT/numbered"

DOCKER_RUN_MODE="direct"

detect_docker_run_mode() {
    if docker ps >/dev/null 2>&1; then
        DOCKER_RUN_MODE="direct"
        return 0
    fi

    if sg docker -c "docker ps" >/dev/null 2>&1; then
        DOCKER_RUN_MODE="sg"
        log_warning "Using 'sg docker -c' for Docker commands in this session"
        return 0
    fi

    log_error "Docker is not accessible in the current session"
    log_error "Run './scripts/setup_docker.sh' and then either 'sg docker -c bash' or re-login"
    return 1
}

run_docker_cmd() {
    local cmd="$1"

    if [ "$DOCKER_RUN_MODE" = "sg" ]; then
        sg docker -c "cd '$ROOT_DIR' && $cmd"
    else
        (
            cd "$ROOT_DIR"
            eval "$cmd"
        )
    fi
}

ensure_runtime_dependencies() {
    # Required modules for benchmark runners + reset helpers.
    if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import requests  # noqa: F401
import pika      # noqa: F401
import fastapi   # noqa: F401
import uvicorn   # noqa: F401
PY
    then
        return 0
    fi

    log_warning "Python dependencies missing. Installing requirements.txt..."
    if ! sh -c "$PIP_BIN install -r '$ROOT_DIR/requirements.txt'"; then
        log_error "Failed to install Python dependencies"
        exit 1
    fi

    if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import requests  # noqa: F401
import pika      # noqa: F401
import fastapi   # noqa: F401
import uvicorn   # noqa: F401
PY
    then
        log_error "Python dependencies are still missing after installation"
        exit 1
    fi

    log_success "Python dependencies ready"
}

direct_workload_for_type() {
    if [ "$1" = "unnumbered" ]; then
        echo "benchmarks/benchmark_unnumbered_20000.txt"
    else
        echo "benchmarks/benchmark_numbered_60000.txt"
    fi
}

reset_direct_state() {
    local api_url="$1"

    # Best-effort reset via API endpoint.
    for retry in 1 2 3; do
        if curl -fsS -X POST "${api_url}/reset" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.5
    done

    # Fallback: flush Redis directly if endpoint reset fails.
    run_docker_cmd "docker compose -f docker/docker-compose.direct.yml exec -T redis redis-cli FLUSHDB" >/dev/null 2>&1 || true
}

reset_indirect_state() {
    # Clear Redis state used by workers.
    run_docker_cmd "docker compose -f docker/docker-compose.indirect.yml exec -T redis redis-cli FLUSHDB" >/dev/null

    # Purge RabbitMQ purchase/response queues to avoid cross-run contamination.
    "$PYTHON_BIN" - <<'PY'
import pika

conn = pika.BlockingConnection(pika.URLParameters("amqp://guest:guest@localhost:5672/%2F"))
ch = conn.channel()
for q in ("ticket_purchase_queue", "ticket_response_queue"):
    ch.queue_declare(queue=q, durable=True)
    ch.queue_purge(queue=q)
conn.close()
PY

    # Restart workers so in-memory idempotency cache is cleared between runs.
    run_docker_cmd "docker compose -f docker/docker-compose.indirect.yml restart worker" >/dev/null
    sleep 2
}

# Parse arguments
SKIP_DOCKER_SETUP="${1:-false}"
SKIP_DIRECT="${2:-false}"
SKIP_INDIRECT="${3:-false}"

# ---------------------------------------------------------------------------
# Docker Setup
# ---------------------------------------------------------------------------

if [ "$SKIP_DOCKER_SETUP" != "true" ]; then
    log_section "Step 1: Docker Setup"
    bash "$SCRIPT_DIR/setup_docker.sh" || {
        log_error "Docker setup failed"
        exit 1
    }
fi

ensure_runtime_dependencies

if [ ! -x "$CONTENTION_RUNNER" ]; then
    chmod +x "$CONTENTION_RUNNER"
fi

detect_docker_run_mode || exit 1

# ---------------------------------------------------------------------------
# Direct Architecture Benchmark
# ---------------------------------------------------------------------------

if [ "$SKIP_DIRECT" != "true" ]; then
    log_section "Step 2: Direct Architecture (REST + Redis)"

    API_URL="http://localhost:80"
    log_warning "Launching direct architecture..."
    if DIRECT_UP_OUTPUT=$(run_docker_cmd "docker compose -f docker/docker-compose.direct.yml up -d --build" 2>&1); then
        printf '%s\n' "$DIRECT_UP_OUTPUT" | head -20
        sleep 5
        log_success "Direct architecture running"

        log_warning "Running direct benchmark matrix (types x concurrencies)..."
        for TICKET_TYPE in unnumbered numbered; do
            WORKLOAD="$(direct_workload_for_type "$TICKET_TYPE")"

            for C in "${CONCURRENCY_LEVELS[@]}"; do
                OUTPUT="${RESULTS_DIR_DIRECT}/${TICKET_TYPE}/c${C}_${TIMESTAMP}.json"
                echo "Direct: type=${TICKET_TYPE} concurrency=${C} ..."

                reset_direct_state "$API_URL"

                "$PYTHON_BIN" -m src.main \
                    --mode benchmark-direct \
                    --ticket-type "$TICKET_TYPE" \
                    --workload "$WORKLOAD" \
                    --concurrent-clients "$C" \
                    --api-url "$API_URL" \
                    --output "$OUTPUT" || {
                        log_warning "Direct run failed: type=${TICKET_TYPE} concurrency=${C}"
                        continue
                    }

                echo "  → $OUTPUT"
            done
        done

        log_warning "Running direct HIGH-CONTENTION matrix (numbered only)..."
        for C in "${CONCURRENCY_LEVELS[@]}"; do
            echo "Direct contention: concurrency=${C} ..."

            reset_direct_state "$API_URL"

            "$CONTENTION_RUNNER" direct "$C" "$API_URL" || {
                log_warning "Direct contention run failed: concurrency=${C}"
                continue
            }
        done
        
        log_success "Direct benchmarks completed"
        
        log_warning "Stopping direct architecture..."
        run_docker_cmd "docker compose -f docker/docker-compose.direct.yml down" || true
        sleep 2
    else
        printf '%s\n' "$DIRECT_UP_OUTPUT" | head -20
        log_error "Failed to launch direct architecture"
    fi
fi

# ---------------------------------------------------------------------------
# Indirect Architecture Benchmark
# ---------------------------------------------------------------------------

if [ "$SKIP_INDIRECT" != "true" ]; then
    log_section "Step 3: Indirect Architecture (RabbitMQ + Redis + Workers)"

    log_warning "Launching indirect architecture with 4 workers..."
    if INDIRECT_UP_OUTPUT=$(run_docker_cmd "docker compose -f docker/docker-compose.indirect.yml up -d --build --scale worker=4" 2>&1); then
        printf '%s\n' "$INDIRECT_UP_OUTPUT" | head -20
        sleep 10  # Wait longer for RabbitMQ and workers to be healthy
        log_success "Indirect architecture running"

        log_warning "Running indirect benchmark matrix (types x concurrencies)..."
        for TICKET_TYPE in unnumbered numbered; do
            WORKLOAD="$(direct_workload_for_type "$TICKET_TYPE")"

            for C in "${CONCURRENCY_LEVELS[@]}"; do
                OUTPUT="${RESULTS_DIR_INDIRECT}/${TICKET_TYPE}/c${C}_${TIMESTAMP}.json"
                echo "Indirect: type=${TICKET_TYPE} concurrency=${C} ..."

                reset_indirect_state || {
                    log_warning "Could not reset indirect state before run"
                }

                "$PYTHON_BIN" -m src.main \
                    --mode benchmark-indirect \
                    --ticket-type "$TICKET_TYPE" \
                    --workload "$WORKLOAD" \
                    --concurrent-clients "$C" \
                    --output "$OUTPUT" || {
                        log_warning "Indirect run failed: type=${TICKET_TYPE} concurrency=${C}"
                        continue
                    }

                echo "  → $OUTPUT"
            done
        done

        log_warning "Running indirect HIGH-CONTENTION matrix (numbered only)..."
        for C in "${CONCURRENCY_LEVELS[@]}"; do
            echo "Indirect contention: concurrency=${C} ..."

            reset_indirect_state || {
                log_warning "Could not reset indirect state before contention run"
            }

            "$CONTENTION_RUNNER" indirect "$C" || {
                log_warning "Indirect contention run failed: concurrency=${C}"
                continue
            }
        done
        
        log_success "Indirect benchmarks completed"
        
        log_warning "Stopping indirect architecture..."
        run_docker_cmd "docker compose -f docker/docker-compose.indirect.yml down" || true
        sleep 2
    else
        printf '%s\n' "$INDIRECT_UP_OUTPUT" | head -20
        log_error "Failed to launch indirect architecture"
    fi
fi

# ---------------------------------------------------------------------------
# Results Summary
# ---------------------------------------------------------------------------

log_section "Benchmark Results Summary"

echo "Direct Architecture Results:"
find results/direct -type f -name "*.json" 2>/dev/null | sort | while read -r f; do
    size=$(du -h "$f" | awk '{print $1}')
    echo "  $f ($size)"
done

echo ""
echo "Indirect Architecture Results:"
find results/indirect -type f -name "*.json" 2>/dev/null | sort | while read -r f; do
    size=$(du -h "$f" | awk '{print $1}')
    echo "  $f ($size)"
done

echo ""
log_success "Benchmark orchestration complete!"
echo ""
echo "Next steps:"
echo "  1. View results: find results/direct results/indirect -type f -name '*.json'"
echo "  2. Plot results: python3 scripts/plot_results.py"
echo "  3. Analyze standard JSON: jq '.summary' results/direct/unnumbered/*.json"
echo "  4. Analyze contention JSON: jq '.summary' results/indirect/numbered/contention/*.json"
echo ""
