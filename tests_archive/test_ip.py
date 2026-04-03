#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from agent.mcp.mcp_client import GaodeMCPClient

client = GaodeMCPClient()
print("Testing _get_public_ip()")
ip = client._get_public_ip()
print(f"IP: {ip}")
if ip:
    print(f"Is valid: {client._is_valid_ipv4(ip)}")
else:
    print("No IP returned")
    # Try to see what's in agent_conf
    from utils.config_handler import agent_conf
    print("agent_conf keys:", list(agent_conf.keys()))
    print("public_ip_sources:", agent_conf.get('public_ip_sources', 'default'))
    print("public_ip_timeout:", agent_conf.get('public_ip_timeout', 'default'))