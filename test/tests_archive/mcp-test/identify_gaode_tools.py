#!/usr/bin/env python3
"""
高德MCP工具识别脚本

获取高德MCP服务器提供的所有工具，识别可用于天气查询和用户定位的工具。
"""

import os
import asyncio
import yaml
import json
from typing import Dict, Any, List
from langchain_mcp_adapters.client import MultiServerMCPClient

def load_gaode_key() -> str:
    """从agent.yml加载高德API Key"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "agent.yml")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        return config["gaodekey"]

def safe_get(obj, key, default=None):
    """安全获取字典值"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default

def analyze_tool_for_weather(tool_name: str, description: str) -> bool:
    """分析工具是否与天气相关"""
    weather_keywords = ['weather', '天气', 'climate', 'temperature', '湿度', 'wind']
    tool_lower = tool_name.lower()
    desc_lower = description.lower()

    for keyword in weather_keywords:
        if keyword in tool_lower or keyword in desc_lower:
            return True
    return False

def analyze_tool_for_location(tool_name: str, description: str) -> bool:
    """分析工具是否与定位相关"""
    location_keywords = ['location', '定位', 'ip', 'geocode', 'geo', '地址', 'city', '城市', 'position']
    tool_lower = tool_name.lower()
    desc_lower = description.lower()

    for keyword in location_keywords:
        if keyword in tool_lower or keyword in desc_lower:
            return True
    return False

def format_args_schema(args_schema):
    """格式化参数schema，安全处理不同类型"""
    if not args_schema:
        return "无参数"

    if isinstance(args_schema, dict):
        try:
            if "properties" in args_schema:
                # JSON Schema格式
                properties = args_schema.get("properties", {})
                required = args_schema.get("required", [])
                params = []
                for param_name, param_schema in properties.items():
                    param_type = safe_get(param_schema, "type", "any")
                    param_desc = safe_get(param_schema, "description", "")
                    required_flag = "✓" if param_name in required else ""
                    params.append(f"{param_name}: {param_type} {required_flag} ({param_desc})")
                return f"{len(properties)}个参数:\n    " + "\n    ".join(params)
            else:
                # 简单字典格式
                params = []
                for param_name, param_schema in args_schema.items():
                    if isinstance(param_schema, dict):
                        param_type = safe_get(param_schema, "type", "any")
                        param_desc = safe_get(param_schema, "description", "")
                        params.append(f"{param_name}: {param_type} ({param_desc})")
                    else:
                        params.append(f"{param_name}: {param_schema}")
                return f"{len(args_schema)}个参数:\n    " + "\n    ".join(params)
        except Exception as e:
            return f"参数解析失败: {e}"
    elif isinstance(args_schema, str):
        return f"参数schema为字符串: {args_schema[:100]}..."
    else:
        return f"参数schema类型: {type(args_schema)}"

async def main():
    """主函数：连接高德MCP并分析工具"""
    print("=" * 70)
    print("高德MCP工具识别")
    print("=" * 70)

    # 加载API Key
    api_key = load_gaode_key()
    print(f"API Key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else ''}")

    # 连接到高德MCP
    client = MultiServerMCPClient({
        "amap-amap-sse": {
            "url": f"https://mcp.amap.com/sse?key={api_key}",
            "transport": "sse"
        }
    })

    try:
        print("\n正在连接高德MCP服务器...")
        tools = await client.get_tools()
        print(f"✅ 获取到 {len(tools)} 个工具")

        # 分类工具
        weather_tools = []
        location_tools = []
        other_tools = []

        for tool in tools:
            is_weather = analyze_tool_for_weather(tool.name, tool.description)
            is_location = analyze_tool_for_location(tool.name, tool.description)

            if is_weather:
                weather_tools.append(tool)
            elif is_location:
                location_tools.append(tool)
            else:
                other_tools.append(tool)

        # 打印天气相关工具
        print("\n" + "=" * 70)
        print("天气相关工具")
        print("=" * 70)
        if weather_tools:
            for i, tool in enumerate(weather_tools, 1):
                print(f"\n{i}. {tool.name}")
                print(f"   描述: {tool.description}")
                print(f"   参数: {format_args_schema(getattr(tool, 'args_schema', None))}")
        else:
            print("⚠ 未找到明显的天气相关工具")
            print("   建议检查以下可能包含天气功能的工具:")
            for tool in other_tools:
                if any(kw in tool.description.lower() for kw in ['查询', 'search', 'info', '信息']):
                    print(f"   - {tool.name}: {tool.description[:60]}...")

        # 打印定位相关工具
        print("\n" + "=" * 70)
        print("定位相关工具")
        print("=" * 70)
        if location_tools:
            for i, tool in enumerate(location_tools, 1):
                print(f"\n{i}. {tool.name}")
                print(f"   描述: {tool.description}")
                print(f"   参数: {format_args_schema(getattr(tool, 'args_schema', None))}")
        else:
            print("⚠ 未找到明显的定位相关工具")
            print("   建议检查以下可能包含定位功能的工具:")
            for tool in other_tools:
                if any(kw in tool.description.lower() for kw in ['ip', '地址', '位置', '坐标']):
                    print(f"   - {tool.name}: {tool.description[:60]}...")

        # 打印所有工具列表（简要）
        print("\n" + "=" * 70)
        print("所有工具列表（简要）")
        print("=" * 70)
        for i, tool in enumerate(tools, 1):
            category = ""
            if tool in weather_tools:
                category = "[天气]"
            elif tool in location_tools:
                category = "[定位]"

            print(f"{i:2d}. {category} {tool.name:30} - {tool.description[:50]}...")

        # 适配建议
        print("\n" + "=" * 70)
        print("适配建议")
        print("=" * 70)

        if weather_tools:
            print("✅ 天气工具适配:")
            for tool in weather_tools:
                print(f"   {tool.name} 可能用于替换 get_weather()")
                print(f"     需要验证参数: city -> {format_args_schema(getattr(tool, 'args_schema', None))}")
        else:
            print("❌ 未找到合适的天气工具，可能需要:")
            print("   1. 检查是否有隐藏的天气功能")
            print("   2. 使用其他工具组合实现")
            print("   3. 保留原有实现")

        if location_tools:
            print("\n✅ 定位工具适配:")
            for tool in location_tools:
                print(f"   {tool.name} 可能用于替换 get_user_location()")
                print(f"     需要验证参数: 无参数 -> {format_args_schema(getattr(tool, 'args_schema', None))}")
        else:
            print("\n❌ 未找到合适的定位工具，可能需要:")
            print("   1. 检查IP定位相关工具")
            print("   2. 使用地理编码工具反向实现")
            print("   3. 保留原有实现")

        # 保存工具信息到文件
        output_file = os.path.join(os.path.dirname(__file__), "gaode_tools.json")
        tools_data = []
        for tool in tools:
            tool_data = {
                "name": tool.name,
                "description": tool.description,
                "args_schema": getattr(tool, 'args_schema', None),
                "category": "weather" if tool in weather_tools else
                          "location" if tool in location_tools else "other"
            }
            tools_data.append(tool_data)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tools_data, f, ensure_ascii=False, indent=2)
        print(f"\n📁 工具信息已保存到: {output_file}")

        return True

    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        print("\n可能的原因:")
        print("1. API Key无效或没有MCP访问权限")
        print("2. 网络无法访问 https://mcp.amap.com")
        print("3. langchain_mcp_adapters库版本问题")
        print("4. 高德MCP服务器暂时不可用")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("\n" + "=" * 70)
        print("✅ 工具识别完成")
        print("下一步:")
        print("1. 根据上述分析选择合适工具")
        print("2. 创建适配层代码")
        print("3. 修改ReactAgent使用新工具")
    else:
        print("\n" + "=" * 70)
        print("❌ 工具识别失败")
        print("需要解决连接问题后才能继续")
    print("=" * 70)