"""
Load balancer configuration and utilities.
Contains NGINX configuration generator and a client-side round-robin balancer.
"""

import threading
from typing import List, Optional

# ---------------------------------------------------------------------------
# NGINX configuration generator
# ---------------------------------------------------------------------------

NGINX_CONFIG_TEMPLATE = """\
upstream ticket_api {{
    # Round-robin is the default NGINX strategy
{server_lines}
    keepalive 64;
}}

server {{
    listen 80;
    server_name _;

    location / {{
        proxy_pass         http://ticket_api;
        proxy_http_version 1.1;
        proxy_set_header   Connection        "";
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        proxy_connect_timeout 30s;
        proxy_send_timeout    30s;
        proxy_read_timeout    30s;
    }}

    location /nginx_status {{
        stub_status on;
        access_log  off;
        allow       127.0.0.1;
        deny        all;
    }}
}}
"""


class LoadBalancerConfig:
    """Helpers to generate and persist NGINX configuration."""

    @staticmethod
    def generate_nginx_config(backend_servers: List[str]) -> str:
        """
        Generate an NGINX upstream config for the given backend servers.

        Args:
            backend_servers: e.g. ["10.0.0.1:8001", "10.0.0.2:8001"]

        Returns:
            NGINX configuration string.
        """
        server_lines = "\n".join(
            f"    server {s};" for s in backend_servers
        )
        return NGINX_CONFIG_TEMPLATE.format(server_lines=server_lines)

    @staticmethod
    def write_nginx_config(config_str: str, output_path: str) -> None:
        """Write the NGINX configuration string to *output_path*."""
        with open(output_path, "w") as fh:
            fh.write(config_str)


# ---------------------------------------------------------------------------
# Client-side round-robin balancer
# ---------------------------------------------------------------------------

class ClientSideLoadBalancer:
    """
    Thread-safe round-robin load balancer.

    Used when deploying without NGINX: each client picks the next server
    in the list on every request.
    """

    def __init__(self, servers: List[str]):
        if not servers:
            raise ValueError("At least one server URL is required")
        self.servers = servers
        self._idx = 0
        self._lock = threading.Lock()

    def get_next_server(self) -> str:
        """Return the next server URL (thread-safe round-robin)."""
        with self._lock:
            url = self.servers[self._idx % len(self.servers)]
            self._idx += 1
        return url

    def get_server_for_request(self, request_id: str) -> str:
        """
        Deterministically map a request_id to a server (hash-based).

        Useful for sticky routing if needed; otherwise just use
        get_next_server() for true round-robin.
        """
        idx = hash(request_id) % len(self.servers)
        return self.servers[idx]
