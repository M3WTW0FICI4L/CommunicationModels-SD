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

    # When run with sudo, SUDO_USER is the real user; otherwise use $USER
    local REAL_USER="${SUDO_USER:-$USER}"

    # Create the docker group if it does not exist
    if ! getent group docker >/dev/null 2>&1; then
        log_warning "docker group does not exist. Creating..."
        sudo groupadd docker
        log_success "docker group created"
    else
        log_success "docker group already exists"
    fi

    # Add real user to docker group
    if id -nG "$REAL_USER" 2>/dev/null | grep -qw docker; then
        log_success "User '$REAL_USER' already in docker group"
    else
        log_warning "Adding '$REAL_USER' to docker group..."
        sudo usermod -aG docker "$REAL_USER"
        log_success "User '$REAL_USER' added to docker group"
        log_warning "Group takes effect in new sessions. For this session run: newgrp docker"
    fi

    # Fix socket group ownership so current session can use Docker now
    if [ -S /var/run/docker.sock ]; then
        local SOCK_GID
        SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
        local DOCKER_GID
        DOCKER_GID=$(getent group docker | cut -d: -f3)

        if [ "$SOCK_GID" != "$DOCKER_GID" ]; then
            log_warning "Socket group mismatch (sock GID=$SOCK_GID, docker GID=$DOCKER_GID). Fixing..."
            sudo chown root:docker /var/run/docker.sock
            log_success "Docker socket group fixed"
        else
            log_success "Docker socket group is correct"
        fi
    fi
}

# ---------------------------------------------------------------------------
# Service management
# ---------------------------------------------------------------------------

# Detect whether Docker was installed via Snap or via systemd package
_docker_is_snap() {
    snap list docker >/dev/null 2>&1
}

start_docker_daemon() {
    log_info "Ensuring Docker daemon is running..."

    if _docker_is_snap; then
        log_info "Docker is installed via Snap."
        if ! snap services docker.dockerd 2>/dev/null | grep -q 'active'; then
            log_warning "Starting Snap docker.dockerd service..."
            sudo snap start docker.dockerd
            sleep 3
        fi
        # Snap daemon already runs with --group docker; no daemon.json needed
        log_success "Docker (Snap) daemon is running"

    elif command -v systemctl >/dev/null 2>&1; then
        if ! systemctl is-active --quiet docker 2>/dev/null; then
            log_warning "Starting Docker daemon via systemctl..."
            sudo systemctl start docker
        fi
        sudo systemctl enable docker 2>/dev/null || true

        # Configure daemon socket group if not already set
        local DAEMON_JSON="/etc/docker/daemon.json"
        if [ ! -f "$DAEMON_JSON" ] || ! grep -q '"group"' "$DAEMON_JSON" 2>/dev/null; then
            log_info "Configuring Docker daemon socket group in $DAEMON_JSON..."
            if [ -f "$DAEMON_JSON" ]; then
                sudo python3 -c "
import json
with open('$DAEMON_JSON') as f: d=json.load(f)
d['group']='docker'
with open('$DAEMON_JSON','w') as f: json.dump(d,f,indent=2)
"
            else
                echo '{"group":"docker"}' | sudo tee "$DAEMON_JSON" >/dev/null
            fi
            sudo systemctl restart docker
            sleep 2
        fi
        log_success "Docker daemon started and enabled"
    else
        log_warning "Neither Snap nor systemctl detected; Docker daemon management may differ"
    fi
}

restart_docker() {
    log_info "Restarting Docker..."

    if _docker_is_snap; then
        sudo snap restart docker
        sleep 3
        log_success "Docker (Snap) restarted"
    elif command -v systemctl >/dev/null 2>&1; then
        sudo systemctl restart docker
        sleep 2
        log_success "Docker restarted"
    else
        log_error "Cannot restart Docker: neither Snap nor systemctl available"
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
    if docker ps >/dev/null 2>&1; then
        log_success "Docker daemon is accessible"
        return 0
    fi

    if sg docker -c "docker ps" >/dev/null 2>&1; then
        log_warning "Docker daemon is accessible via 'sg docker'; current shell has not reloaded docker group yet"
        return 0
    fi

    log_error "Docker daemon not accessible (daemon down or session lacks valid permissions)"
    return 1
}

check_docker_socket_permissions() {
    if [ -S /var/run/docker.sock ]; then
        local SOCK_GID
        SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
        local USER_GROUPS
        USER_GROUPS=$(id -G "$USER")

        if echo "$USER_GROUPS" | grep -qw "$SOCK_GID"; then
            log_success "Docker socket has correct permissions"
            return 0
        elif sg docker -c "docker ps" >/dev/null 2>&1; then
            log_warning "Docker socket is usable via 'sg docker'; current shell groups are stale until re-login/newgrp"
            return 0
        else
            log_warning "Docker socket group GID=$SOCK_GID not in current session's groups: $USER_GROUPS"
            return 1
        fi
    else
        log_error "Docker socket not found at /var/run/docker.sock"
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
        log_warning "Docker socket still not usable in this session. Use: sg docker -c 'bash' or log out/in."
    fi
    
    # Final validation
    echo ""
    echo "=========================================="
    echo "  Final Validation"
    echo "=========================================="
    docker --version
    docker compose version

    # Run docker ps - use sg docker if needed for current session
    if docker ps >/dev/null 2>&1; then
        docker ps
    elif sg docker -c "docker ps" >/dev/null 2>&1; then
        log_warning "Docker group active via 'sg docker' (re-login for permanent access)"
        sg docker -c "docker ps"
    else
        log_warning "Cannot list containers yet. Re-login or run: sg docker -c 'docker ps'"
    fi

    echo ""
    log_success "Docker setup complete and healthy!"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  IMPORTANT: Apply docker group to current session"
    echo "  Run: sg docker -c 'bash'   (temporary, this terminal)"
    echo "  Or:  newgrp docker          (replace current shell)"
    echo "  Or:  logout and login again (permanent)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Next steps:"
    echo "  1. Direct architecture:   sg docker -c 'docker compose -f docker/docker-compose.direct.yml up -d --build'"
    echo "  2. Indirect architecture: sg docker -c 'docker compose -f docker/docker-compose.indirect.yml up -d --build --scale worker=4'"
    echo "  3. Run benchmarks:        sg docker -c './scripts/run_all_benchmarks.sh true'"
    echo ""
}

# Run main
main "$@"
