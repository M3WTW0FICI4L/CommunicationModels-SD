#!/usr/bin/env bash
# Docker setup and health check script
# Ensures Docker and Docker Compose are installed and running
# Installs them if missing; restarts service if needed

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

log_success() {
    echo -e "${GREEN}✓${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $*"
}

log_error() {
    echo -e "${RED}✗${NC} $*"
}

# ---------------------------------------------------------------------------
# Detect OS
# ---------------------------------------------------------------------------

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    elif command -v lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
    else
        log_error "Cannot detect OS"
        exit 1
    fi
    echo "$OS"
}

# ---------------------------------------------------------------------------
# Docker installation
# ---------------------------------------------------------------------------

install_docker() {
    log_info "Installing Docker..."
    local OS=$(detect_os)
    
    case "$OS" in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y \
                apt-transport-https \
                ca-certificates \
                curl \
                gnupg \
                lsb-release
            
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
                sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io
            ;;
        fedora)
            sudo dnf install -y \
                dnf-plugins-core
            sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
            sudo dnf install -y docker-ce docker-ce-cli containerd.io
            ;;
        centos|rhel)
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install -y docker-ce docker-ce-cli containerd.io
            ;;
        *)
            log_error "Unsupported OS: $OS"
            exit 1
            ;;
    esac
    
    log_success "Docker installed"
}

install_docker_compose() {
    log_info "Installing Docker Compose..."
    
    # Try to install via apt/yum first
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get install -y docker-compose-plugin
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y docker-compose-plugin
    else
        # Fallback: download binary
        local DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d'"' -f4)
        sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
            -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi
    
    log_success "Docker Compose installed"
}

# ---------------------------------------------------------------------------
# Permission setup
# ---------------------------------------------------------------------------

setup_docker_permissions() {
    log_info "Setting up Docker permissions..."
    
    if ! groups | grep -q docker; then
        log_warning "User not in docker group. Adding..."
        sudo usermod -aG docker "$USER"
        log_warning "⚠ You must logout and login for group changes to take effect"
        log_warning "⚠ Or run: newgrp docker"
    else
        log_success "User already in docker group"
    fi
}

# ---------------------------------------------------------------------------
# Service management
# ---------------------------------------------------------------------------

start_docker_daemon() {
    log_info "Ensuring Docker daemon is running..."
    
    if command -v systemctl >/dev/null 2>&1; then
        sudo systemctl start docker
        sudo systemctl enable docker
        log_success "Docker daemon started and enabled"
    else
        log_warning "systemctl not available; Docker daemon management may differ"
    fi
}

restart_docker() {
    log_info "Restarting Docker..."
    
    if command -v systemctl >/dev/null 2>&1; then
        sudo systemctl restart docker
        sleep 2
        log_success "Docker restarted"
    else
        log_error "Cannot restart Docker without systemctl"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

check_docker_install() {
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker not installed"
        return 1
    fi
    log_success "Docker is installed"
    return 0
}

check_docker_compose_install() {
    if ! docker compose version >/dev/null 2>&1; then
        log_error "Docker Compose not available"
        return 1
    fi
    log_success "Docker Compose is available"
    return 0
}

check_docker_daemon() {
    if ! docker ps >/dev/null 2>&1; then
        log_error "Docker daemon not accessible (permission denied or not running)"
        return 1
    fi
    log_success "Docker daemon is accessible"
    return 0
}

check_docker_socket_permissions() {
    if [ -S /var/run/docker.sock ]; then
        if [ -r /var/run/docker.sock ] && [ -w /var/run/docker.sock ]; then
            log_success "Docker socket has correct permissions"
            return 0
        else
            log_warning "Docker socket exists but insufficient permissions"
            return 1
        fi
    else
        log_error "Docker socket not found"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

main() {
    echo ""
    echo "=========================================="
    echo "  Docker Setup & Health Check"
    echo "=========================================="
    echo ""
    
    # Check Docker installation
    if ! check_docker_install; then
        log_info "Installing Docker..."
        install_docker
    fi
    
    # Check Docker Compose
    if ! check_docker_compose_install; then
        log_info "Installing Docker Compose..."
        install_docker_compose
    fi
    
    # Setup permissions
    setup_docker_permissions
    
    # Start Docker daemon
    start_docker_daemon
    
    # Check daemon access
    if ! check_docker_daemon; then
        log_warning "Docker daemon not accessible; restarting..."
        restart_docker
        
        if ! check_docker_daemon; then
            log_error "Failed to access Docker daemon after restart"
            exit 1
        fi
    fi
    
    # Check socket permissions
    if ! check_docker_socket_permissions; then
        log_warning "Restarting Docker to fix socket permissions..."
        restart_docker
    fi
    
    # Final validation
    echo ""
    echo "=========================================="
    echo "  Final Validation"
    echo "=========================================="
    docker --version
    docker compose version
    docker ps
    
    echo ""
    log_success "Docker setup complete and healthy!"
    echo ""
    echo "Next steps:"
    echo "  1. Direct architecture:  docker compose -f docker/docker-compose.direct.yml up -d --build"
    echo "  2. Indirect architecture: docker compose -f docker/docker-compose.indirect.yml up -d --build --scale worker=4"
    echo ""
}

# Run main
main "$@"
