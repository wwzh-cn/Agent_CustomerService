#!/usr/bin/env python3
"""
测试MCP客户端修复
"""
import sys
import os
sys.path.insert(0, '.')

try:
    from agent.mcp.mcp_client import GaodeMCPClient
    print('导入MCP客户端成功')
    client = GaodeMCPClient()
    print('MCP客户端初始化成功')
    print(f'API Key: {client.api_key[:10]}...')
    print('测试通过！')
except Exception as e:
    print(f'错误: {e}')
    import traceback
    traceback.print_exc()