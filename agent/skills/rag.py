"""
RAG Skill - 知识库检索技能

包装现有的 rag_summarize 工具函数，从向量库检索参考资料并生成总结。
"""

from agent.skills.base import Skill
from agent.tools.agent_tools import rag_summarize


class RagSkill(Skill):
    """RAG 检索技能

    继承自 Skill 基类，包装现有的 rag_summarize 函数。
    通过 RAG 服务从向量库检索相关文档并生成总结回答。
    """

    name = "rag_summarize"
    description = "从向量存储中检索参考资料"

    def execute(self, query: str) -> str:
        """执行 RAG 检索

        Args:
            query: 用户查询文本，例如 "扫地机器人推荐"

        Returns:
            str: 基于检索资料的总结回答
        """
        # 直接调用现有的 rag_summarize 函数，保持原有逻辑
        return rag_summarize(query)