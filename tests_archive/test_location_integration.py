#!/usr/bin/env python3
"""
测试定位功能集成
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_location():
    from agent.mcp.mcp_client import GaodeMCPClient
    print("Testing GaodeMCPClient location...")
    client = GaodeMCPClient()
    try:
        result = await client.call_location()
        print(f"Location result: {result}")
        if result == "未知城市":
            print("WARNING: Returned unknown city")
            # 检查IP获取情况
            ip = client._get_public_ip()
            print(f"Public IP: {ip}")
            # 检查工具列表
            tools = await client.get_tools()
            tool_names = [tool.name for tool in tools]
            print(f"Available tools ({len(tools)}): {tool_names}")
            if "maps_ip_location" in tool_names:
                print("maps_ip_location tool exists")
            else:
                print("maps_ip_location tool NOT found")
        else:
            print(f"SUCCESS: Got city: {result}")
        await client.close()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_location())