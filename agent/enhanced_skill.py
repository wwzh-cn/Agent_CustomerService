"""
EnhancedSkill - 增强技能描述类

通过提供更丰富的描述信息（分类、示例、参数说明、使用限制）帮助 LLM 更准确、快速地选择工具，
减少思考步骤和试错调用，从而节约 Token 消耗。

保持最小代码变更原则：仅包装现有的 @tool 装饰函数，不改变原有调用逻辑。
"""

from typing import List, Dict, Callable, Any
from dataclasses import dataclass, field
from langchain_core.tools import Tool


@dataclass
class EnhancedSkill:
    """增强技能描述类

    封装现有 @tool 装饰函数，提供丰富的描述信息以优化 LLM 工具选择。

    Attributes:
        name: 工具名称（与 @tool 函数名一致）
        description: 详细功能描述（何时调用、解决什么问题）
        category: 技能分类，如：查询类、计算类、数据类、通信类
        examples: 调用示例列表（自然语言格式）
        parameters: 参数说明字典，格式为 {参数名: 参数说明}
        constraints: 使用限制列表
        func: 原有的 @tool 装饰函数（可调用对象）
    """
    name: str
    description: str
    category: str
    examples: List[str] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    func: Callable = None

    def to_langchain_tool(self) -> Tool:
        """转换为 LangChain Tool 对象

        生成优化后的结构化描述，包含详细的参数说明和使用场景信息。
        如果 self.func 已经是 Tool 对象，提取其原始函数或创建包装函数。

        Returns:
            LangChain Tool 对象，可直接用于 Agent 工具列表
        """
        # 构建增强后的工具描述
        enhanced_description = f"""{self.description}

分类: {self.category}
参数说明: {self._format_parameters()}
使用示例: {self._format_examples()}
使用限制: {self._format_constraints()}
        """.strip()

        # 获取原始函数（处理 func 已经是 Tool 对象的情况）
        func_to_use = self.func

        def create_adapted_function(original_func, func_name=None):
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
                        print(f"[EnhancedSkill.adapted_func] 无参数函数 {func_name or 'unknown'}，忽略参数调用")
                        try:
                            return original_func()
                        except Exception as e2:
                            # 如果仍然失败，重新抛出原始异常或新异常
                            raise e2 from e

                    # 其他类型的参数错误，尝试从第一个参数提取（如果是字典）
                    if args and isinstance(args[0], dict):
                        print(f"[EnhancedSkill.adapted_func] 从字典参数提取调用 {func_name or 'unknown'}")
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

        # 检查 func 是否是 Tool 实例
        try:
            # 尝试导入 Tool 类进行类型检查
            from langchain_core.tools import BaseTool

            if isinstance(func_to_use, BaseTool):
                # 如果是 Tool 对象，尝试提取其原始函数
                # StructuredTool 通常有 _func 或 func 属性
                extracted_func = None

                if hasattr(func_to_use, '_func'):
                    extracted_func = func_to_use._func
                    print(f"[EnhancedSkill.to_langchain_tool] 从 _func 提取原始函数: {self.name}")
                elif hasattr(func_to_use, 'func'):
                    extracted_func = func_to_use.func
                    print(f"[EnhancedSkill.to_langchain_tool] 从 func 提取原始函数: {self.name}")
                elif hasattr(func_to_use, 'function'):
                    extracted_func = func_to_use.function
                    print(f"[EnhancedSkill.to_langchain_tool] 从 function 提取原始函数: {self.name}")

                if extracted_func is not None:
                    # 为提取的函数创建适配器
                    func_to_use = create_adapted_function(extracted_func, self.name)
                else:
                    # 如果没有原始函数属性，创建包装函数调用 invoke
                    print(f"[EnhancedSkill.to_langchain_tool] 为 {self.name} 创建 invoke 包装函数")
                    original_tool = func_to_use
                    def tool_wrapper(*args, **kwargs):
                        # 调用原 Tool 的 invoke 方法，并处理参数不匹配
                        try:
                            return original_tool.invoke(*args, **kwargs)
                        except TypeError as e:
                            error_msg = str(e)
                            # 检查是否是无参数函数被传递了参数
                            if "takes 0 positional arguments" in error_msg or "missing 1 required positional argument" in error_msg:
                                # 无参数函数：忽略所有参数，传递空字典
                                print(f"[EnhancedSkill.tool_wrapper] 无参数函数 {self.name}，忽略参数调用 invoke({{}})")
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
                                print(f"[EnhancedSkill.tool_wrapper] 从字典参数提取调用 {self.name}")
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
                    func_to_use = tool_wrapper
        except ImportError:
            # 如果无法导入 BaseTool，跳过类型检查
            pass

        # 确保 func_to_use 是适配后的函数（即使不是 Tool 对象也创建适配器）
        if not hasattr(func_to_use, '_is_adapted'):
            func_to_use = create_adapted_function(func_to_use, self.name)
            # 标记为已适配（避免无限递归）
            func_to_use._is_adapted = True

        # 创建 LangChain Tool 对象
        return Tool(
            name=self.name,
            description=enhanced_description,
            func=func_to_use,
        )

    def to_markdown(self) -> str:
        """生成 skill.md 格式的 markdown 片段

        Returns:
            格式化的技能描述，符合 skill.md 文档规范
        """
        # 生成 skill.md 格式的 markdown 片段
        return f"""
## {self.name}

**分类**: {self.category}
**描述**: {self.description}
**参数**: {self._format_parameters()}
**示例**: {self._format_examples()}
**限制**: {self._format_constraints()}
        """.strip()

    def _format_parameters(self) -> str:
        """格式化参数说明

        Returns:
            格式化后的参数说明文本
        """
        if not self.parameters:
            return "无参数"

        items = []
        for param_name, param_desc in self.parameters.items():
            items.append(f"  - {param_name}: {param_desc}")

        return "\n".join(items)

    def _format_examples(self) -> str:
        """格式化示例说明

        Returns:
            格式化后的示例说明文本
        """
        if not self.examples:
            return "暂无示例"

        items = []
        for i, example in enumerate(self.examples, 1):
            items.append(f"  - \"{example}\"")

        return "\n".join(items)

    def _format_constraints(self) -> str:
        """格式化使用限制

        Returns:
            格式化后的使用限制文本
        """
        if not self.constraints:
            return "无特殊限制"

        items = []
        for constraint in self.constraints:
            items.append(f"  - {constraint}")

        return "\n".join(items)

    def __str__(self) -> str:
        return f"EnhancedSkill(name={self.name}, category={self.category})"

    def __repr__(self) -> str:
        return self.__str__()


def generate_skill_markdown(skills: List[EnhancedSkill]) -> str:
    """生成完整的技能清单 markdown 文档

    Args:
        skills: EnhancedSkill 对象列表

    Returns:
        完整的 skill.md 文档内容
    """
    content = "# 技能清单 (Skills Directory)\n\n"
    for skill in skills:
        content += skill.to_markdown() + "\n\n"
    return content.strip()