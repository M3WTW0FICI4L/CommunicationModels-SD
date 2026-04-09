#!/usr/bin/env bash
# Test runner script

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Normalize path to repository root (script location is scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR" || exit 1

echo -e "${YELLOW}Running Unit Tests from $ROOT_DIR ...${NC}"
echo "======================================"

# Ensure local venv exists (if possible)
if [ -d ".venv" ] && [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
    if [ -x ".venv/bin/pip" ]; then
        PIP=".venv/bin/pip"
    else
        # Fall back to python -m pip if pip binary missing
        if ${PYTHON} -m pip --version &> /dev/null; then
            PIP="${PYTHON} -m pip"
        else
            echo -e "${YELLOW}No pip in .venv; using system pip3 (as fallback).${NC}"
            PIP="python3 -m pip"
        fi
    fi
else
    echo -e "${YELLOW}.venv not found. Attempting to create virtualenv...${NC}"
    if python3 -m venv .venv 2>/dev/null; then
        echo -e "${GREEN}Virtualenv .venv created successfully.${NC}"
        PYTHON=".venv/bin/python"
        if [ -x ".venv/bin/pip" ]; then
            PIP=".venv/bin/pip"
        else
            if ${PYTHON} -m pip --version &> /dev/null; then
                PIP="${PYTHON} -m pip"
            else
                echo -e "${YELLOW}pip module not available in .venv and ensurepip may be missing.${NC}"
                PIP="python3 -m pip"
            fi
        fi
    else
        echo -e "${RED}Cannot create virtualenv (.venv) automatically.${NC}"
        echo -e "${YELLOW}Please install python3-venv and rerun: sudo apt install python3.12-venv${NC}"
        echo -e "${YELLOW}Falling back to system python3/pip${NC}"
        PYTHON="python3"
        PIP="python3 -m pip"
    fi
fi

# Determine pytest command (venv first, then PATH)
if ${PYTHON} -m pytest --version > /dev/null 2>&1; then
    PYTEST_CMD="${PYTHON} -m pytest"
elif command -v pytest > /dev/null 2>&1; then
    PYTEST_CMD="pytest"
else
    echo -e "${YELLOW}pytest not found. Installing into venv...${NC}"
    INSTALL_OUT=$(${PIP} install pytest pytest-cov 2>&1 || true)
    if echo "${INSTALL_OUT}" | grep -qi "externally-managed-environment"; then
        echo -e "${RED}Error: pip operation blocked by Debian 'externally-managed-environment'.${NC}"
        echo "Please do one of the following:"
        echo "  1) sudo apt install python3-pytest python3-pytest-cov"
        echo "  2) python3 -m pip install --user --break-system-packages pytest pytest-cov"
        echo "  3) pipx install pytest pytest-cov" 
        echo "  4) enable venv with apt: sudo apt install python3.12-venv, then python3 -m venv .venv"
        echo "  5) run tests in an environment where package installs are trusted (not PEP668-managed)."
        exit 1
    fi

    if ${PYTHON} -m pytest --version > /dev/null 2>&1; then
        PYTEST_CMD="${PYTHON} -m pytest"
    else
        echo -e "${RED}pytest still not available after install attempt.${NC}"
        echo "Install pytest manually in your environment and retry."
        exit 1
    fi
fi

# Run tests with coverage
echo -e "${YELLOW}Running tests with coverage...${NC}"
${PYTEST_CMD} tests/ -v --cov=src --cov-report=term-missing --cov-report=html

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed!${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Test Summary:${NC}"
echo "======================================"
echo "- Models tests: tests/test_models.py"
echo "- Config tests: tests/test_config.py"
echo "- Metrics tests: tests/test_metrics.py"
echo "- Storage tests: tests/test_storage.py"
echo "- TicketManager tests: tests/test_ticket_manager.py"
echo "- Benchmark tests: tests/test_benchmark.py"
echo ""
echo "Coverage report: coverage_html/index.html"
