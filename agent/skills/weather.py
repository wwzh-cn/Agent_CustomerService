"""
Weather Skill - 天气查询技能

包装现有的 get_weather 工具函数，通过 MCP 客户端查询城市天气。
"""

from agent.skills.base import Skill
from agent.tools.agent_tools import get_weather


class WeatherSkill(Skill):
    """天气查询技能

    继承自 Skill 基类，包装现有的 get_weather 函数。
    通过 MCP 客户端调用高德天气 API。
    """

    name = "get_weather"
    description = "获取指定城市的天气，以消息字符串的形式返回"

    def execute(self, city: str) -> str:
        """执行天气查询

        Args:
            city: 城市名称，例如 "北京"、"上海"

        Returns:
            str: 天气查询结果的文本描述
        """
        # 直接调用现有的 get_weather 函数，保持原有逻辑和错误处理
        return get_weather(city)