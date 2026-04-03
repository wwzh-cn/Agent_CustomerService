import os
import asyncio
import yaml
import json
import re
from typing import Dict, Any, Optional
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from langchain_mcp_adapters.client import MultiServerMCPClient
from utils.logger_handler import logger
from utils.config_handler import agent_conf


class GaodeMCPClient:
    """高德MCP客户端"""

    def __init__(self):
        # 从现有配置文件读取API Key
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "agent.yml")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            self.api_key = config["gaodekey"]

        # 初始化MCP客户端
        self.client = MultiServerMCPClient({
            "amap-amap-sse": {
                "url": f"https://mcp.amap.com/sse?key={self.api_key}",
                "transport": "sse"
            }
        })

        # 工具缓存
        self._tool_map = None
        self._tools_loaded = False

        # IP地址验证正则表达式
        self._IPV4_RE = re.compile(
            r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
            r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
            r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
            r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$"
        )

    def _is_valid_ipv4(self, ip: str) -> bool:
        """检查IP地址是否有效"""
        return bool(self._IPV4_RE.match(ip or ""))

    def _get_public_ip(self) -> str:
        """获取用户公网IP地址（复用现有逻辑）"""
        # 可在agent.yml里覆盖
        ip_sources = agent_conf.get("public_ip_sources", [
            "https://api.ipify.org",
            "https://ipv4.icanhazip.com",
            "https://checkip.amazonaws.com",
        ])
        try:
            timeout = float(agent_conf.get("public_ip_timeout", 5))
        except (ValueError, TypeError):
            timeout = 5.0
            logger.warning(f"[MCP location]无效的public_ip_timeout配置，使用默认值5秒")


        for i, source in enumerate(ip_sources, 1):
            try:
                with urlopen(source, timeout=timeout) as resp:
                    ip = resp.read().decode("utf-8").strip()
                    if self._is_valid_ipv4(ip):
                        logger.info(f"[MCP location]成功获取公网IP: {ip} (来自 {source})")
                        return ip
                    else:
                        logger.warning(f"[MCP location]源 {source} 返回无效IP格式: {ip}")
            except Exception as e:
                continue

        logger.warning(f"[MCP location]所有{len(ip_sources)}个IP源均失败，无法获取公网IP")
        return ""

    async def get_tools(self):
        """获取所有MCP工具"""
        return await self.client.get_tools()

    async def _ensure_tools_loaded(self):
        """确保工具已加载到缓存中"""
        if not self._tools_loaded:
            tools = await self.client.get_tools()
            self._tool_map = {tool.name: tool for tool in tools}
            self._tools_loaded = True

    async def _call_mcp_tool(self, tool_name: str, args: dict) -> dict:
        """调用MCP工具并解析结果"""
        await self._ensure_tools_loaded()

        if tool_name not in self._tool_map:
            raise ValueError(f"工具 {tool_name} 不存在")

        tool = self._tool_map[tool_name]

        # 调用工具
        result = await tool.ainvoke(args)

        # 解析结果 - 工具返回的是包含text字段的列表
        if not result or not isinstance(result, list):
            raise ValueError(f"工具 {tool_name} 返回无效结果: {result}")

        # 查找text内容
        for item in result:
            if isinstance(item, dict) and item.get("type") == "text":
                text_content = item.get("text", "")
                if text_content:
                    try:
                        return json.loads(text_content)
                    except json.JSONDecodeError:
                        # 如果无法解析为JSON，可能直接返回了字符串
                        return {"raw_text": text_content}

        # 如果没有找到text内容，尝试直接解析
        if len(result) == 1 and isinstance(result[0], dict):
            return result[0]

        raise ValueError(f"无法解析工具 {tool_name} 返回结果: {result}")

    async def call_weather(self, city: str) -> str:
        """调用高德MCP天气工具

        Args:
            city: 城市名称

        Returns:
            格式化的天气信息字符串，与现有get_weather函数保持一致
        """
        if not city or not city.strip():
            return "未提供城市名称，无法查询天气"

        try:
            # 调用maps_weather工具
            result = await self._call_mcp_tool("maps_weather", {"city": city.strip()})

            # 根据测试，返回格式是包含forecasts数组的JSON
            # 示例: {"city":"北京","forecasts":[{"date":"2026-03-29","week":"7","dayweather":"晴","nightweather":"晴",...}]}

            # 检查是否有错误状态字段（高德API通常有status字段）
            if result.get("status") and result.get("status") != "1":
                error_info = result.get("info", "查询失败")
                return f"城市{city}天气查询失败：{error_info}"

            # 提取城市名称
            resolved_city = result.get("city", city)

            # 获取天气预报数据（第一个预报）
            forecasts = result.get("forecasts", [])
            if not forecasts:
                return f"城市{city}天气查询失败：未找到天气数据"

            forecast = forecasts[0]

            # 提取天气信息
            condition = forecast.get("dayweather", "未知")
            temperature = forecast.get("daytemp", "未知")
            wind_direction = forecast.get("daywind", "未知")
            wind_power = forecast.get("daypower", "未知")
            report_time = forecast.get("date", "未知")

            # 注意：MCP返回可能没有湿度和报告时间，使用默认值
            humidity = "未知"

            # 保持与现有函数相同的格式（尽量匹配）
            return (
                f"城市{resolved_city}天气为{condition}，气温{temperature}摄氏度，"
                f"空气湿度{humidity}%，{wind_direction}风{wind_power}级，"
                f"数据发布时间{report_time}。"
            )

        except Exception as e:
            logger.error(f"[MCP weather]天气查询失败 city={city} err={str(e)}")
            # 保持原有错误消息格式
            return f"城市{city}天气查询失败，请稍后重试"

    async def call_location(self) -> str:
        """调用高德MCP定位工具

        Returns:
            城市名称字符串，与现有get_user_location函数保持一致
        """
        try:
            # 获取用户IP（使用内部方法）
            public_ip = self._get_public_ip()

            if not public_ip:
                logger.warning("[MCP location]无法获取用户IP地址")
                return "未知城市"

            # 调用maps_ip_location工具
            result = await self._call_mcp_tool("maps_ip_location", {"ip": public_ip})

            # 解析返回的JSON
            if result.get("status") and result.get("status") != "1":
                error_info = result.get("info", "定位失败")
                logger.warning(f"[MCP location]定位失败 info={error_info} ip={public_ip}")
                return "未知城市"

            # 提取城市信息
            # 高德IP定位API返回格式可能有不同，尝试多种字段
            city = result.get("city", "")
            if not city:
                city = result.get("City", "")
            if not city:
                city = result.get("adcode", "")

            province = result.get("province", "")
            if not province:
                province = result.get("Province", "")

            # 处理可能的列表类型
            if isinstance(city, list):
                city = "".join(city)
            if isinstance(province, list):
                province = "".join(province)

            city = str(city).strip()
            province = str(province).strip()

            if city:
                # 如果城市名称包含"市"字，去掉
                if city.endswith("市"):
                    city = city[:-1]
                return city
            if province:
                return province

            logger.warning(
                f"[MCP location]空城市信息 ip={public_ip} raw={result}"
            )
            return "未知城市"

        except Exception as e:
            logger.error(f"[MCP location]定位失败 err={str(e)}")
            return "未知城市"

    async def close(self):
        """关闭MCP连接（如果客户端支持）"""
        # MultiServerMCPClient可能没有close方法
        if hasattr(self.client, 'close') and callable(self.client.close):
            await self.client.close()