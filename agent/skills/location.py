"""
Location Skill - 用户定位技能

包装现有的 get_user_location 工具函数，通过 MCP 客户端获取用户所在城市。
"""

from agent.skills.base import Skill
from agent.tools.agent_tools import get_user_location


class LocationSkill(Skill):
    """用户定位技能

    继承自 Skill 基类，包装现有的 get_user_location 函数。
    通过 MCP 客户端调用高德定位 API。
    """

    name = "get_user_location"
    description = "获取用户所在城市的名称，以纯字符串形式返回"

    def execute(self) -> str:
        """执行用户定位

        Returns:
            str: 用户所在城市名称，例如 "北京市"、"上海市"
        """
        # 直接调用现有的 get_user_location 函数，保持原有逻辑和错误处理
        return get_user_location()