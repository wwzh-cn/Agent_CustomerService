"""
集成增强技能 - 为所有工具创建EnhancedSkill实例

此模块为agent/tools/agent_tools.py中的所有工具创建EnhancedSkill实例，
用于在ReactAgent中替换原始工具列表。

注意：保持最小代码变更原则，仅包装现有@tool装饰函数。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_skill import EnhancedSkill

# 尝试导入真实工具函数，如果失败则使用模拟函数（用于测试）
try:
    from tools.agent_tools import (
        rag_summarize, get_weather, get_user_location,
        get_user_id, get_current_month, fetch_external_data, fill_context_for_report
    )
    USE_REAL_TOOLS = True
    print("[integrate_enhanced_skills] 使用真实工具函数")

    # 检查导入的对象是否是 Tool 实例，如果是则提取原始函数
    try:
        from langchain_core.tools import BaseTool

        def extract_raw_function(tool_obj):
            """从 Tool 对象中提取原始函数，并创建适配器处理参数不匹配"""
            def create_adapted_function(original_func, tool_name=None):
                """创建适配器函数，处理参数不匹配问题"""
                def adapted_func(*args, **kwargs):
                    try:
                        # 尝试直接调用原始函数
                        return original_func(*args, **kwargs)
                    except TypeError as e:
                        # 如果参数不匹配，尝试不同的调用方式
                        error_msg = str(e)

                        # 检查是否是无参数函数被传递了参数
                        if "takes 0 positional arguments" in error_msg or "missing 1 required positional argument" in error_msg:
                            # 无参数函数：忽略所有参数
                            print(f"[integrate_enhanced_skills] 适配器: 无参数函数 {tool_name or 'unknown'}，忽略参数调用")
                            try:
                                return original_func()
                            except Exception as e2:
                                # 如果仍然失败，重新抛出原始异常或新异常
                                raise e2 from e

                        # 其他类型的参数错误，尝试从第一个参数提取（如果是字典）
                        if args and isinstance(args[0], dict):
                            print(f"[integrate_enhanced_skills] 适配器: 从字典参数提取调用 {tool_name or 'unknown'}")
                            try:
                                # 如果是字典参数，将其展开为关键字参数
                                return original_func(**args[0])
                            except Exception as e2:
                                # 如果失败，尝试作为位置参数传递
                                try:
                                    return original_func(*args, **kwargs)
                                except Exception as e3:
                                    # 如果仍然失败，重新抛出异常
                                    raise e3 from e2

                        # 其他TypeError，重新抛出
                        raise
                    # 注意：不捕获其他异常，让它们正常传播

                return adapted_func

            if isinstance(tool_obj, BaseTool):
                # StructuredTool 通常有 _func 或 func 属性
                extracted_func = None
                tool_name = getattr(tool_obj, 'name', None) or type(tool_obj).__name__

                if hasattr(tool_obj, '_func'):
                    print(f"[integrate_enhanced_skills] 从 _func 提取原始函数: {tool_name}")
                    extracted_func = tool_obj._func
                elif hasattr(tool_obj, 'func'):
                    print(f"[integrate_enhanced_skills] 从 func 提取原始函数: {tool_name}")
                    extracted_func = tool_obj.func
                elif hasattr(tool_obj, 'function'):
                    print(f"[integrate_enhanced_skills] 从 function 提取原始函数: {tool_name}")
                    extracted_func = tool_obj.function

                if extracted_func is not None:
                    # 为提取的函数创建适配器
                    return create_adapted_function(extracted_func, tool_name)
                else:
                    # 如果没有找到原始函数属性，创建包装函数调用 invoke
                    print(f"[integrate_enhanced_skills] 为 {tool_name} 创建 invoke 包装函数")
                    original_tool = tool_obj
                    def tool_wrapper(*args, **kwargs):
                        # 调用原 Tool 的 invoke 方法，并处理参数不匹配
                        try:
                            return original_tool.invoke(*args, **kwargs)
                        except TypeError as e:
                            error_msg = str(e)
                            # 检查是否是无参数函数被传递了参数
                            if "takes 0 positional arguments" in error_msg or "missing 1 required positional argument" in error_msg:
                                # 无参数函数：忽略所有参数，传递空字典
                                print(f"[integrate_enhanced_skills.tool_wrapper] 无参数函数 {tool_name or 'unknown'}，忽略参数调用 invoke({{}})")
                                try:
                                    return original_tool.invoke({})
                                except Exception as e2:
                                    # 如果仍然失败，尝试传递空字典给 invoke
                                    try:
                                        return original_tool.invoke(*args, **kwargs)
                                    except Exception as e3:
                                        raise e3 from e2
                            # 其他类型的参数错误，尝试从第一个参数提取（如果是字典）
                            if args and isinstance(args[0], dict):
                                print(f"[integrate_enhanced_skills.tool_wrapper] 从字典参数提取调用 {tool_name or 'unknown'}")
                                try:
                                    # 如果是字典参数，将其展开为关键字参数（但 invoke 期望字典）
                                    return original_tool.invoke(args[0])
                                except Exception as e2:
                                    # 如果失败，尝试作为位置参数传递
                                    try:
                                        return original_tool.invoke(*args, **kwargs)
                                    except Exception as e3:
                                        raise e3 from e2
                            # 其他TypeError，重新抛出
                            raise
                    return tool_wrapper
            else:
                # 如果不是 Tool 对象，也创建适配器以防万一
                print(f"[integrate_enhanced_skills] 为非Tool对象创建适配器")
                return create_adapted_function(tool_obj)

        # 提取所有工具的原始函数
        rag_summarize_func = extract_raw_function(rag_summarize)
        get_weather_func = extract_raw_function(get_weather)
        get_user_location_func = extract_raw_function(get_user_location)
        get_user_id_func = extract_raw_function(get_user_id)
        get_current_month_func = extract_raw_function(get_current_month)
        fetch_external_data_func = extract_raw_function(fetch_external_data)
        fill_context_for_report_func = extract_raw_function(fill_context_for_report)

        print("[integrate_enhanced_skills] 已提取工具原始函数")

    except ImportError:
        # 如果无法导入 BaseTool，直接使用原对象
        rag_summarize_func = rag_summarize
        get_weather_func = get_weather
        get_user_location_func = get_user_location
        get_user_id_func = get_user_id
        get_current_month_func = get_current_month
        fetch_external_data_func = fetch_external_data
        fill_context_for_report_func = fill_context_for_report
        print("[integrate_enhanced_skills] 无法导入 BaseTool，直接使用原对象")
        rag_summarize_func = rag_summarize
        get_weather_func = get_weather
        get_user_location_func = get_user_location
        get_user_id_func = get_user_id
        get_current_month_func = get_current_month
        fetch_external_data_func = fetch_external_data
        fill_context_for_report_func = fill_context_for_report

except ImportError as e:
    print(f"[integrate_enhanced_skills] 导入真实工具失败: {e}，使用模拟函数")
    USE_REAL_TOOLS = False

    # 模拟函数定义
    def rag_summarize_func(query: str) -> str:
        return f"模拟RAG检索结果: {query}"

    def get_weather_func(city: str) -> str:
        return f"模拟天气查询结果: {city} 25°C，晴朗"

    def get_user_location_func() -> str:
        return "模拟定位结果: 北京市"

    def get_user_id_func() -> str:
        return "1001"

    def get_current_month_func() -> str:
        return "2025-01"

    def fetch_external_data_func(user_id: str, month: str) -> str:
        return f"模拟外部数据: 用户{user_id}在{month}的使用记录"

    def fill_context_for_report_func() -> str:
        return "fill_context_for_report已调用"


def create_all_enhanced_skills() -> list[EnhancedSkill]:
    """为所有工具创建EnhancedSkill实例

    Returns:
        EnhancedSkill对象列表，包含所有7个工具的增强描述
    """
    skills = []

    # 1. rag_summarize - RAG检索技能
    skills.append(EnhancedSkill(
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
        func=rag_summarize_func
    ))

    # 2. get_weather - 天气查询技能
    skills.append(EnhancedSkill(
        name="get_weather",
        description="查询中国城市实时天气信息，包括温度、湿度、风力、天气状况和数据发布时间。适用于用户询问天气情况时调用。如果对话历史中已有城市信息，请优先使用历史中的城市名称。",
        category="查询类",
        examples=[
            "查询北京的天气",
            "上海今天天气怎么样",
            "get_weather(city='广州')"
        ],
        parameters={
            "city": "必填参数，中文城市名称，如'北京'、'上海市'。可以从对话历史中获取城市名称。"
        },
        constraints=[
            "仅支持中国城市",
            "需要网络连接",
            "数据来自高德天气API",
            "城市名称需准确，否则可能查询失败",
            "重要：如果历史对话中已提及城市名称，请直接使用历史信息中的城市，不要重复调用定位工具获取城市"
        ],
        func=get_weather_func
    ))

    # 3. get_user_location - 用户定位技能
    skills.append(EnhancedSkill(
        name="get_user_location",
        description="根据用户公网IP地址自动定位所在城市。适用于需要知道用户当前位置的场景。如果对话历史中已有位置信息，请优先使用历史信息，避免重复定位。",
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
            "如果IP定位失败返回'未知城市'",
            "重要：如果历史对话中已提及城市位置，请直接使用历史信息，不要重复调用本工具"
        ],
        func=get_user_location_func
    ))

    # 4. get_user_id - 用户ID获取技能
    skills.append(EnhancedSkill(
        name="get_user_id",
        description="获取用户的唯一标识符ID，用于用户识别和数据关联。如果对话历史中已有用户ID信息，请优先使用历史信息，避免重复获取。",
        category="数据类",
        examples=[
            "获取我的用户ID",
            "用户标识是什么",
            "get_user_id()"
        ],
        parameters={},  # 无参数
        constraints=[
            "返回随机选择的用户ID",
            "ID来自预定义列表",
            "用于测试和演示目的",
            "重要：如果历史对话中已提及用户ID，请直接使用历史信息，不要重复调用本工具"
        ],
        func=get_user_id_func
    ))

    # 5. get_current_month - 当前月份获取技能
    skills.append(EnhancedSkill(
        name="get_current_month",
        description="获取当前月份信息，用于时间相关的数据查询和报告生成。如果对话历史中已有月份信息，请优先使用历史信息，避免重复获取。",
        category="数据类",
        examples=[
            "现在是几月份",
            "获取当前月份",
            "get_current_month()"
        ],
        parameters={},  # 无参数
        constraints=[
            "返回随机选择的月份",
            "月份来自预定义列表",
            "用于测试和演示目的",
            "重要：如果历史对话中已提及月份信息，请直接使用历史信息，不要重复调用本工具"
        ],
        func=get_current_month_func
    ))

    # 6. fetch_external_data - 外部数据获取技能
    skills.append(EnhancedSkill(
        name="fetch_external_data",
        description="从外部系统中获取指定用户在指定月份的使用记录数据。适用于生成用户使用报告的场景。如果对话历史中已有用户ID或月份信息，请优先使用历史信息。",
        category="数据类",
        examples=[
            "获取用户1001在2025-01的使用记录",
            "fetch_external_data(user_id='1002', month='2025-02')"
        ],
        parameters={
            "user_id": "必填参数，用户ID，如'1001'、'1002'。可以从对话历史中获取用户ID。",
            "month": "必填参数，月份，格式为'YYYY-MM'，如'2025-01'。可以从对话历史中获取月份信息。"
        },
        constraints=[
            "依赖外部数据文件",
            "如果用户或月份不存在返回空字符串",
            "数据文件路径在agent.yml中配置",
            "重要：如果历史对话中已提及用户ID或月份信息，请直接使用历史信息，不要重复调用获取用户ID或月份的工具"
        ],
        func=fetch_external_data_func
    ))

    # 7. fill_context_for_report - 报告上下文填充技能
    skills.append(EnhancedSkill(
        name="fill_context_for_report",
        description="触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文。",
        category="控制类",
        examples=[
            "准备生成报告",
            "填充报告上下文",
            "fill_context_for_report()"
        ],
        parameters={},  # 无参数
        constraints=[
            "无返回值，仅触发中间件操作",
            "用于报告生成前的上下文准备",
            "与报告提示词切换中间件配合使用"
        ],
        func=fill_context_for_report_func
    ))

    return skills


def get_enhanced_tools():
    """获取增强后的LangChain工具列表

    Returns:
        list: LangChain Tool对象列表，可直接用于ReactAgent
    """
    skills = create_all_enhanced_skills()
    tools = []

    for skill in skills:
        try:
            tool = skill.to_langchain_tool()
            tools.append(tool)
            print(f"[integrate_enhanced_skills] 创建增强工具: {skill.name}")
        except Exception as e:
            print(f"[integrate_enhanced_skills] 创建工具失败 {skill.name}: {e}")

    return tools


if __name__ == "__main__":
    # 测试函数
    print("=== 测试所有EnhancedSkill实例创建 ===")
    skills = create_all_enhanced_skills()

    print(f"创建了 {len(skills)} 个技能实例:")
    for i, skill in enumerate(skills, 1):
        print(f"{i}. {skill.name} ({skill.category})")

    print("\n=== 测试LangChain工具转换 ===")
    tools = get_enhanced_tools()
    print(f"成功创建 {len(tools)} 个LangChain工具")

    if tools:
        print(f"第一个工具描述长度: {len(tools[0].description)} 字符")