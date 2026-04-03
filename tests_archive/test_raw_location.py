#!/usr/bin/env python3
import asyncio
import sys
import os
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_raw_location():
    config_path = os.path.join("config", "agent.yml")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        api_key = config["gaodekey"]

    from langchain_mcp_adapters.client import MultiServerMCPClient
    client = MultiServerMCPClient({
        "amap-amap-sse": {
            "url": f"https://mcp.amap.com/sse?key={api_key}",
            "transport": "sse"
        }
    })

    # 获取工具列表
    tools = await client.get_tools()
    print(f"Total tools: {len(tools)}")
    for tool in tools:
        if tool.name == "maps_ip_location":
            print(f"Found tool: {tool.name}")
            # 获取IP
            import re
            from urllib.request import urlopen
            IPV4_RE = re.compile(
                r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
                r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
                r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
                r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$"
            )
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
            public_ip = get_public_ip()
            print(f"Public IP: {public_ip}")
            # 调用工具
            result = await tool.ainvoke({"ip": public_ip})
            print(f"Raw result type: {type(result)}")
            print(f"Raw result: {result}")
            # 尝试解析
            if isinstance(result, list) and len(result) > 0:
                for i, item in enumerate(result):
                    print(f"Item {i}: type={type(item)}, value={item}")
                    if isinstance(item, dict):
                        for k, v in item.items():
                            print(f"  {k}: {v}")
            break
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_raw_location())