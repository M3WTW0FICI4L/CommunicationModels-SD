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

detect_docker_run_mode || exit 1

# ---------------------------------------------------------------------------
# Direct Architecture Benchmark
# ---------------------------------------------------------------------------

if [ "$SKIP_DIRECT" != "true" ]; then
    log_section "Step 2: Direct Architecture (REST + Redis)"
    
    log_warning "Launching direct architecture..."
    if DIRECT_UP_OUTPUT=$(run_docker_cmd "docker compose -f docker/docker-compose.direct.yml up -d --build" 2>&1); then
        printf '%s\n' "$DIRECT_UP_OUTPUT" | head -20
        sleep 5
        log_success "Direct architecture running"
        
        log_warning "Running direct benchmarks..."
        "./scripts/run_direct_benchmark.sh" unnumbered 50 http://localhost:80 || {
            log_warning "Direct benchmark (unnumbered) encountered issues but may have partial results"
        }
        
        sleep 2
        
        "./scripts/run_direct_benchmark.sh" numbered 50 http://localhost:80 || {
            log_warning "Direct benchmark (numbered) encountered issues but may have partial results"
        }
        
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
        
        log_warning "Running indirect benchmarks..."
        "./scripts/run_indirect_benchmark.sh" unnumbered 50 || {
            log_warning "Indirect benchmark (unnumbered) encountered issues but may have partial results"
        }
        
        sleep 2
        
        "./scripts/run_indirect_benchmark.sh" numbered 50 || {
            log_warning "Indirect benchmark (numbered) encountered issues but may have partial results"
        }
        
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
echo "  3. Analyze JSON: jq '.summary' results/direct/unnumbered/*.json"
echo ""
