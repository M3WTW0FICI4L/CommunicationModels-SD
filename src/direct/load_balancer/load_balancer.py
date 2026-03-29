"""
Load balancer configuration and utilities.
Contains NGINX configuration examples and helper functions.
"""

from typing import List, Dict, Any
import json


# NGINX configuration template for reverse proxy load balancing
NGINX_CONFIG_TEMPLATE = """
upstream ticket_api {{
    # Round-robin load balancing
    server {servers};
}}

server {{
    listen 80;
    server_name _;
    
    location / {{
        proxy_pass http://ticket_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }}
    
    # Stats endpoint for monitoring
    location /nginx_status {{
        stub_status on;
        access_log off;
        allow 127.0.0.1;
        deny all;
    }}
}}
"""


class LoadBalancerConfig:
    """Load balancer configuration helper."""
    
    @staticmethod
    def generate_nginx_config(backend_servers: List[str]) -> str:
        """
        Generate NGINX configuration for given backend servers.
        
        Args:
            backend_servers: List of backend server URLs (e.g., ["localhost:8001", "localhost:8002"])
        
        Returns:
            NGINX configuration string
        """
        servers_str = "; ".join([f"server {server}" for server in backend_servers])
        return NGINX_CONFIG_TEMPLATE.format(servers=servers_str)
    
    @staticmethod
    def write_nginx_config(config_str: str, output_path: str) -> None:
        """
        Write NGINX configuration to file.
        
        Args:
            config_str: Configuration string
            output_path: Path where to write the config file
        """
        # TODO: Implement file writing with proper error handling
        pass


class ClientSideLoadBalancer:
    """
    Client-side load balancer using round-robin strategy.
    Alternative to server-side load balancing (NGINX).
    """
    
    def __init__(self, servers: List[str]):
        """
        Initialize client-side load balancer.
        
        Args:
            servers: List of backend server URLs
        """
        self.servers = servers
        self.current_idx = 0
    
    def get_next_server(self) -> str:
        """
        Get next server using round-robin.
        
        Returns:
            Next server URL
        """
        # TODO: Implement thread-safe round-robin selection
        pass
    
    def get_server_for_request(self, request_id: str) -> str:
        """
        Get server for a specific request (sticky sessions optional).
        
        Args:
            request_id: Request ID
        
        Returns:
            Server URL
        """
        # TODO: Implement request mapping to server
        pass
