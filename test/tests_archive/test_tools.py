#!/usr/bin/env python3
"""
测试工具函数的简单脚本
避免RAG依赖问题，直接导入需要的函数
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接导入工具函数，避免RAG依赖
import asyncio

async def test_weather():
    """测试天气查询函数"""
    print("测试天气查询...")
    try:
        # 导入相关模块，避免RAG依赖
        import json
        import yaml
        from langchain_mcp_adapters.client import MultiServerMCPClient

        # 直接创建MCP客户端测试
        config_path = os.path.join("config", "agent.yml")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            api_key = config["gaodekey"]

        client = MultiServerMCPClient({
            "amap-amap-sse": {
                "url": f"https://mcp.amap.com/sse?key={api_key}",
                "transport": "sse"
            }
        })

        # 获取工具
        tools = await client.get_tools()
        weather_tool = None
        for tool in tools:
            if tool.name == "maps_weather":
                weather_tool = tool
                break

        if not weather_tool:
            print("❌ 未找到天气工具")
            return False

        # 调用工具
        result = await weather_tool.ainvoke({"city": "北京"})
        print(f"✅ 天气查询成功")
        print(f"返回结果类型: {type(result)}")

        # 解析结果
        if isinstance(result, list) and len(result) > 0:
            first_item = result[0]
            if isinstance(first_item, dict) and first_item.get("type") == "text":
                text_content = first_item.get("text", "")
                print(f"返回内容预览: {text_content[:100]}...")

                try:
                    data = json.loads(text_content)
                    if "forecasts" in data:
                        print(f"✅ 天气数据解析成功，包含 {len(data['forecasts'])} 天预报")
                        return True
                except json.JSONDecodeError:
                    print(f"❌ 无法解析JSON: {text_content[:100]}...")

        print(f"❓ 返回结果格式异常: {result}")
        return False

    except Exception as e:
        print(f"❌ 天气查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_location():
    """测试定位查询函数"""
    print("\n测试定位查询...")
    try:
        # 导入相关模块
        import json
        import yaml
        import re
        from urllib.parse import urlencode
        from urllib.request import urlopen
        from urllib.error import URLError, HTTPError
        from langchain_mcp_adapters.client import MultiServerMCPClient

        # IP验证正则
        IPV4_RE = re.compile(
            r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
            r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
            r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
            r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$"
        )

        # 获取公网IP（简化版）
        def get_public_ip():
            ip_sources = ["https://ipv4.icanhazip.com"]
            for source in ip_sources:
                try:
                    with urlopen(source, timeout=3) as resp:
                        ip = resp.read().decode("utf-8").strip()
                        if IPV4_RE.match(ip):
                            return ip
                except Exception:
                    continue
            return ""

        # 创建MCP客户端
        config_path = os.path.join("config", "agent.yml")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            api_key = config["gaodekey"]

        client = MultiServerMCPClient({
            "amap-amap-sse": {
                "url": f"https://mcp.amap.com/sse?key={api_key}",
                "transport": "sse"
            }
        })

        # 获取工具
        tools = await client.get_tools()
        location_tool = None
        for tool in tools:
            if tool.name == "maps_ip_location":
                location_tool = tool
                break

        if not location_tool:
            print("❌ 未找到定位工具")
            return False

        # 获取IP
        public_ip = get_public_ip()
        if not public_ip:
            print("⚠  无法获取公网IP，使用空IP测试")
            public_ip = ""

        # 调用工具
        result = await location_tool.ainvoke({"ip": public_ip})
        print(f"✅ 定位查询成功 (IP: {public_ip or 'auto'})")
        print(f"返回结果类型: {type(result)}")

        # 解析结果
        if isinstance(result, list) and len(result) > 0:
            first_item = result[0]
            if isinstance(first_item, dict) and first_item.get("type") == "text":
                text_content = first_item.get("text", "")
                print(f"返回内容预览: {text_content[:100]}...")

                try:
                    data = json.loads(text_content)
                    city = data.get("city") or data.get("City") or data.get("adcode", "")
                    province = data.get("province") or data.get("Province", "")
                    if city or province:
                        print(f"✅ 定位数据解析成功: 城市={city}, 省份={province}")
                        return True
                except json.JSONDecodeError:
                    print(f"❌ 无法解析JSON: {text_content[:100]}...")

        print(f"❓ 返回结果格式异常: {result}")
        return False

    except Exception as e:
        print(f"❌ 定位查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("=" * 60)
    print("测试MCP工具函数")
    print("=" * 60)

    success = True

    # 测试天气查询
    if not await test_weather():
        success = False

    # 测试定位查询
    if not await test_location():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("✅ 所有工具函数测试通过")
    else:
        print("❌ 部分工具函数测试失败")
    print("=" * 60)

    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)