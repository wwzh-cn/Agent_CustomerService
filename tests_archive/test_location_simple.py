#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test():
    from agent.mcp.mcp_client import GaodeMCPClient
    client = GaodeMCPClient()
    result = await client.call_location()
    print(f"Result repr: {repr(result)}")
    print(f"Result: {result}")
    print(f"Result == '未知城市': {result == '未知城市'}")
    await client.close()

if __name__ == "__main__":
    asyncio.run(test())