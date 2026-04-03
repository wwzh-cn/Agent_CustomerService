"""
Skill 基类定义

定义所有技能必须实现的接口，提供统一的技能抽象层。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class Skill(ABC):
    """技能抽象基类

    所有技能必须继承此类并实现 execute 方法。
    技能通过 SkillManager 注册，由 Agent 统一调用。
    """

    name: str = ""
    """技能名称（唯一标识），用于技能注册和查找"""

    description: str = ""
    """技能的自然语言描述，用于 Agent 理解技能功能"""

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """执行技能的核心方法

        Args:
            **kwargs: 技能执行所需的参数

        Returns:
            str: 技能执行结果的文本描述
        """
        pass

    def __str__(self) -> str:
        return f"Skill(name={self.name}, description={self.description})"

    def __repr__(self) -> str:
        return self.__str__()