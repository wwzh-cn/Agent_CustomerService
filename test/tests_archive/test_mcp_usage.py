#!/usr/bin/env python3
"""
测试MultiServerMCPClient的正确用法
"""

import asyncio
import os
import yaml
import json
from langchain_mcp_adapters.client import MultiServerMCPClient

async def test_mcp_client():
    # 加载API Key
    config_path = os.path.join("config", "agent.yml")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        api_key = config["gaodekey"]

    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")

    # 创建客户端
    client = MultiServerMCPClient({
        "amap-amap-sse": {
            "url": f"https://mcp.amap.com/sse?key={api_key}",
            "transport": "sse"
        }
    })

    print(f"Client created: {client}")
    print(f"Client attributes: {[attr for attr in dir(client) if not attr.startswith('_')]}")

    # 获取工具
    tools = await client.get_tools()
    print(f"Got {len(tools)} tools")

    if tools:
        tool = tools[0]
        print(f"First tool: {tool.name}")
        print(f"Tool type: {type(tool)}")
        print(f"Tool attributes: {[attr for attr in dir(tool) if not attr.startswith('_')][:10]}")

        # 检查session
        print(f"\nClient session: {client.session}")
        print(f"Session type: {type(client.session)}")
        if hasattr(client.session, '__dict__'):
            print(f"Session attributes: {list(client.session.__dict__.keys())}")

    # 尝试调用工具（如果有工具）
    for tool in tools:
        if tool.name == "maps_weather":
            print(f"\nTrying to call tool: {tool.name}")
            try:
                # 尝试直接调用工具
                result = await tool.ainvoke({"city": "北京"})
                print(f"Weather tool result: {result}")
                print(f"Result type: {type(result)}")
                if hasattr(result, 'content'):
                    print(f"Result content: {result.content}")
            except Exception as e:
                print(f"Error calling tool: {e}")
                import traceback
                traceback.print_exc()
            break

    # 检查是否有其他调用方式
    print("\nChecking for other invocation methods...")

if __name__ == "__main__":
    asyncio.run(test_mcp_client())