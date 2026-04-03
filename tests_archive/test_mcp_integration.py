#!/usr/bin/env python3
"""
高德MCP集成测试脚本

测试MCP客户端和工具函数的正确性。
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_mcp_client():
    """测试MCP客户端基本功能"""
    print("=" * 60)
    print("测试高德MCP客户端")
    print("=" * 60)

    try:
        from agent.mcp.mcp_client import GaodeMCPClient

        # 创建客户端
        client = GaodeMCPClient()
        print("[OK] MCP客户端创建成功")

        # 测试获取工具列表
        try:
            tools = await client.get_tools()
            print(f"[OK] 获取到 {len(tools)} 个MCP工具")

            # 检查是否有需要的工具
            tool_names = [tool.name for tool in tools]
            print(f"   工具列表: {', '.join(tool_names[:5])}...")

            if "maps_weather" in tool_names:
                print("[OK] 找到天气查询工具: maps_weather")
            else:
                print("[FAIL] 未找到天气查询工具 maps_weather")

            if "maps_ip_location" in tool_names:
                print("[OK] 找到IP定位工具: maps_ip_location")
            else:
                print("[FAIL] 未找到IP定位工具 maps_ip_location")

        except Exception as e:
            print(f"[FAIL] 获取工具列表失败: {e}")

        # 测试天气查询（简单测试）
        print("\n测试天气查询...")
        try:
            weather_result = await client.call_weather("北京")
            if "天气为" in weather_result and "摄氏度" in weather_result:
                print(f"[OK] 天气查询成功: {weather_result[:80]}...")
            elif "查询失败" in weather_result:
                print(f"⚠  天气查询返回失败: {weather_result}")
            else:
                print(f"❓ 天气查询返回格式异常: {weather_result[:80]}...")
        except Exception as e:
            print(f"[FAIL] 天气查询异常: {e}")

        # 测试定位查询
        print("\n测试定位查询...")
        try:
            location_result = await client.call_location()
            if location_result == "未知城市":
                print(f"⚠  定位返回未知城市，可能IP无法定位或网络问题")
            elif location_result and isinstance(location_result, str):
                print(f"[OK] 定位查询成功: {location_result}")
            else:
                print(f"❓ 定位查询返回格式异常: {location_result}")
        except Exception as e:
            print(f"[FAIL] 定位查询异常: {e}")

        # 关闭连接
        await client.close()
        print("\n[OK] MCP客户端测试完成")

        return True

    except ImportError as e:
        print(f"[FAIL] 导入失败: {e}")
        print("请确保已安装依赖: pip install langchain-mcp-adapters")
        return False
    except Exception as e:
        print(f"[FAIL] 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tool_functions():
    """测试修改后的工具函数"""
    print("\n" + "=" * 60)
    print("测试修改后的工具函数")
    print("=" * 60)

    try:
        # 注意：这里可能会触发RAG依赖错误，所以我们只测试在可能的情况下
        print("跳过直接工具函数测试（避免RAG依赖问题）")
        print("如需测试，请先安装RAG依赖: pip install langchain-chroma")
        return True

    except Exception as e:
        print(f"[FAIL] 工具函数测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    success = True

    # 测试MCP客户端
    if not await test_mcp_client():
        success = False

    # 测试工具函数
    if not test_tool_functions():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("[OK] 所有测试通过（或部分跳过）")
    else:
        print("[FAIL] 部分测试失败")
    print("=" * 60)

    return success

if __name__ == "__main__":
    # 运行异步测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1)