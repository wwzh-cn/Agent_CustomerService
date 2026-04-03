"""
创建增强技能实例

根据 EnhancedSkill 类定义，为关键工具创建增强描述实例。
保持最小代码变更原则，仅包装现有 @tool 装饰函数。

注意：此文件仅用于演示 EnhancedSkill 的创建，不直接集成到主项目。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_skill import EnhancedSkill

# 模拟函数（避免导入实际依赖）
def mock_get_weather(city: str) -> str:
    """模拟天气查询函数"""
    return f"模拟天气查询结果：{city} 25°C，晴朗"

def mock_get_user_location() -> str:
    """模拟用户定位函数"""
    return "模拟定位结果：北京市"

def mock_rag_summarize(query: str) -> str:
    """模拟RAG检索函数"""
    return f"模拟RAG检索结果：{query}"


def create_weather_enhanced_skill() -> EnhancedSkill:
    """创建天气查询增强技能实例"""
    return EnhancedSkill(
        name="get_weather",
        description="查询中国城市实时天气信息，包括温度、湿度、风力、天气状况和数据发布时间。适用于用户询问天气情况时调用。",
        category="查询类",
        examples=[
            "查询北京的天气",
            "上海今天天气怎么样",
            "get_weather(city='广州')"
        ],
        parameters={
            "city": "必填参数，中文城市名称，如'北京'、'上海市'"
        },
        constraints=[
            "仅支持中国城市",
            "需要网络连接",
            "数据来自高德天气API",
            "城市名称需准确，否则可能查询失败"
        ],
        func=mock_get_weather
    )


def create_location_enhanced_skill() -> EnhancedSkill:
    """创建用户定位增强技能实例"""
    return EnhancedSkill(
        name="get_user_location",
        description="根据用户公网IP地址自动定位所在城市。适用于需要知道用户当前位置的场景。",
        category="查询类",
        examples=[
            "我在哪个城市？",
            "获取我的位置",
            "定位用户所在城市"
        ],
        parameters={},  # 无参数
        constraints=[
            "依赖用户公网IP",
            "定位精度为城市级别",
            "需要网络连接",
            "如果IP定位失败返回'未知城市'"
        ],
        func=mock_get_user_location
    )


def create_rag_enhanced_skill() -> EnhancedSkill:
    """创建RAG检索增强技能实例"""
    return EnhancedSkill(
        name="rag_summarize",
        description="从知识库检索相关文档并生成总结回答。适用于用户询问特定知识领域的问题，如扫地机器人推荐、故障排除等。",
        category="检索类",
        examples=[
            "扫地机器人推荐",
            "小户型适合哪些扫地机器人",
            "rag_summarize(query='故障排除')"
        ],
        parameters={
            "query": "必填参数，用户查询文本，描述需要检索的知识主题"
        },
        constraints=[
            "依赖向量数据库中的知识库",
            "检索结果基于已有知识库，可能无法回答最新信息",
            "需要确保知识库已加载"
        ],
        func=mock_rag_summarize
    )


if __name__ == "__main__":
    # 创建增强技能实例
    weather_skill = create_weather_enhanced_skill()
    location_skill = create_location_enhanced_skill()
    rag_skill = create_rag_enhanced_skill()

    # 打印技能信息
    print("已创建增强技能实例:")
    print(f"1. {weather_skill}")
    print(f"2. {location_skill}")
    print(f"3. {rag_skill}")

    # 测试转换方法
    print("\n测试 LangChain Tool 转换:")
    weather_tool = weather_skill.to_langchain_tool()
    print(f"天气工具描述长度: {len(weather_tool.description)} 字符")

    print("\n测试 Markdown 生成:")
    md = weather_skill.to_markdown()
    print(md[:200] + "...")