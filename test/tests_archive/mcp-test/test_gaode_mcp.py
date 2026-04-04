#!/usr/bin/env python3
"""
高德MCP连接测试 - 简化版本
只测试连接和工具列表
"""
import os
import asyncio
import yaml
from langchain_mcp_adapters.client import MultiServerMCPClient

# 从配置文件读取API Key
with open("config/agent.yml") as f:
    config = yaml.safe_load(f)
    AMAP_API_KEY = config["gaodekey"]

async def main():
    print("=" * 60)
    print("测试高德MCP连接...")
    print("=" * 60)
    print(f"API Key: {AMAP_API_KEY[:8]}...{AMAP_API_KEY[-4:] if len(AMAP_API_KEY) > 12 else ''}")

    # 连接高德MCP服务器
    client = MultiServerMCPClient({
        "amap-amap-sse": {
            "url": f"https://mcp.amap.com/sse?key={AMAP_API_KEY}",
            "transport": "sse"
        }
    })

    try:
        print("正在连接高德MCP服务器...")
        tools = await client.get_tools()
        print(f"[SUCCESS] 连接成功！获取到 {len(tools)} 个工具")
        print("-" * 40)

        # 简化打印工具列表
        for i, tool in enumerate(tools, 1):
            print(f"\n工具 {i}: {tool.name}")
            print(f"  描述: {tool.description}")

            # 只显示是否有参数，不深入处理
            if hasattr(tool, 'args_schema') and tool.args_schema:
                if isinstance(tool.args_schema, dict):
                    print(f"  参数数量: {len(tool.args_schema)}")
                else:
                    print(f"  参数格式: {type(tool.args_schema)}")

        print("-" * 40)
        print(f"\n✅ 高德MCP连接测试完成")
        print(f"   总共获取到 {len(tools)} 个工具")

    except Exception as e:
        print(f"[ERROR] 连接失败: {e}")
        print("\n可能的原因:")
        print("1. API Key无效或没有MCP访问权限")
        print("2. 网络无法访问 https://mcp.amap.com")
        print("3. 高德MCP服务器暂时不可用")
        print("4. langchain_mcp_adapters库版本不兼容")
        return False

    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("\n🎉 高德MCP连接测试通过！")
        print("下一步: 可以进一步测试具体工具调用")
    else:
        print("\n⚠ 高德MCP连接测试失败")
        print("需要检查API Key和网络连接")
    print("=" * 60)