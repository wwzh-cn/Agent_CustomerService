"""
ReAct 智能体主模块。

本模块定义了 ReactAgent 类，它是智扫通机器人智能客服系统的核心智能体。
基于 LangChain 的 ReAct Agent 框架，集成了多种工具和中间件，支持流式响应。

主要功能：
- 创建配置了工具和中间件的 LangChain 智能体
- 提供流式执行接口，支持实时对话
- 支持上下文管理，实现动态提示词切换

三层记忆系统：
- 短期记忆（MemoryManager）：会话层，实时上下文
- 中期记忆（FileMemory）：文件层，结构化摘要
- 长期记忆（SemanticMemory）：语义检索层，向量化检索
"""

from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
# 原有工具导入（已注释，可随时恢复）
# from agent.tools.agent_tools import (rag_summarize, get_weather, get_user_location, get_user_id,
#                                      get_current_month, fetch_external_data, fill_context_for_report)
# 增强技能导入
from agent.skills.integrate_enhanced_skills import get_enhanced_tools
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch

# 记忆管理器导入
from agent.memory.memory_manager import MemoryManager
from agent.memory.file_memory import FileMemory
# 阶段二：语义记忆（长期记忆）导入
from agent.memory.semantic_memory import SemanticMemory
from utils.config_handler import agent_conf


class ReactAgent:
    """ReAct 智能体类，基于 LangChain 框架构建。

    该类封装了 LangChain ReAct Agent 的创建和执行逻辑，集成了 RAG 检索、天气查询、
    用户定位、外部数据获取等多种工具，并支持中间件监控和动态提示词切换。

    主要功能：
    - 初始化时创建智能体，配置模型、系统提示词、工具和中间件
    - 提供流式执行方法，支持实时返回 AI 响应
    - 支持上下文管理，实现报告模式的动态切换
    """
    def __init__(self, memory_config=None, file_memory_config=None, semantic_memory_config=None):
        """初始化 ReAct 智能体，配置模型、提示词、工具和中间件。

        Args:
            memory_config: 短期记忆配置字典，如果为None则从agent.yml加载
            file_memory_config: 文件记忆配置字典，如果为None则从agent.yml加载
            semantic_memory_config: 语义记忆配置字典，如果为None则从agent.yml加载
        """
        # 初始化短期记忆管理器
        if memory_config is None:
            # 从配置文件中加载短期记忆配置
            memory_config = agent_conf.get("memory", {})
        self.memory_manager = MemoryManager(memory_config)

        # 初始化文件记忆管理器（如果启用）
        self.file_memory = None
        if file_memory_config is None:
            # 从配置文件中加载文件记忆配置
            file_memory_config = agent_conf.get("file_memory", {})

        if file_memory_config.get("enabled", False):
            self.file_memory = FileMemory(file_memory_config)
            print(f"[ReactAgent] 文件记忆已启用，基础目录: {self.file_memory.base_dir}")

            # 启动时自动检查并执行记忆整理（异步，避免阻塞启动）
            import threading
            def auto_consolidate():
                try:
                    # 检查是否需要整理，如需要则执行
                    if self.file_memory:
                        print("[ReactAgent] 正在执行自动记忆整理...")
                        self.file_memory.consolidate_memory(force=False)
                except Exception as e:
                    print(f"[ReactAgent] 自动记忆整理失败: {e}")

            # 延迟2秒后执行，确保不影响启动速度
            timer = threading.Timer(2.0, auto_consolidate)
            timer.daemon = True  # 设置为守护线程，主程序退出时自动结束
            timer.start()

        # 初始化语义记忆管理器（如果启用）
        self.semantic_memory = None
        if semantic_memory_config is None:
            # 从配置文件中加载语义记忆配置
            semantic_memory_config = agent_conf.get("semantic_memory", {})

        if semantic_memory_config.get("enabled", False):
            try:
                self.semantic_memory = SemanticMemory(semantic_memory_config)
                print(f"[ReactAgent] 语义记忆已启用，向量库路径: {self.semantic_memory.vector_store.persist_directory}")

                # 启动时自动检查并执行增量索引（异步，避免阻塞启动）
                def auto_index():
                    try:
                        if self.semantic_memory:
                            print("[ReactAgent] 正在执行自动增量索引...")
                            # 索引memory/logs目录下的日志文件
                            from pathlib import Path
                            logs_dir = Path("./memory/logs")
                            if logs_dir.exists():
                                result = self.semantic_memory.index_logs_directory(logs_dir, pattern="*.md")
                                print(f"[ReactAgent] 自动索引完成: {result['indexed_files']}个文件，{result['total_chunks']}个块")
                            else:
                                print(f"[ReactAgent] 日志目录不存在: {logs_dir}")
                    except Exception as e:
                        print(f"[ReactAgent] 自动增量索引失败: {e}")

                # 延迟5秒后执行，确保不影响启动速度
                index_timer = threading.Timer(5.0, auto_index)
                index_timer.daemon = True
                index_timer.start()

            except Exception as e:
                print(f"[ReactAgent] 语义记忆初始化失败，已禁用: {e}")
                self.semantic_memory = None

            # 构建增强系统提示词（基础提示词 + 记忆上下文）
            base_prompt = load_system_prompts()
            memory_context = self.file_memory.load_context()
            print(f"[ReactAgent] 加载记忆上下文，原始长度: {len(memory_context)} 字符")

            # 简化记忆上下文，提取最关键部分
            simplified_memory = self._simplify_memory_context(memory_context)
            print(f"[ReactAgent] 简化记忆上下文，简化后长度: {len(simplified_memory)} 字符")

            # 检查是否包含用户查询历史
            query_count = sum(1 for line in simplified_memory.split('\n') if '用户查询:' in line)
            print(f"[ReactAgent] 记忆中包含 {query_count} 条用户查询历史记录")

            enhanced_prompt = f"""# 核心身份和准则
{base_prompt}

# 关键记忆信息（必须优先使用）
以下是从历史对话中提取的关键记忆信息。当用户询问历史信息时，**必须首先检查这些记忆**：

{simplified_memory}

## 记忆使用强制规则
**必须严格遵守以下规则：**
1. **首先检查记忆**：当用户询问任何历史信息（如"昨天问过什么"、"以前问过什么问题"、"历史对话"等）时，**必须首先检查上面的记忆信息**
2. **直接使用记忆回答**：如果记忆中有相关信息，**直接使用记忆内容回答**，无需调用任何工具
3. **引用记忆来源**：回答时应引用记忆的来源日期，例如"根据2026-04-01的记忆记录..."
4. **仅在记忆缺乏时调用工具**：只有当记忆中**完全没有**相关信息时，才考虑调用工具获取新信息
5. **特别注意查询历史**：对于"问过什么问题"、"历史对话"等问题，**必须**使用"用户查询历史"部分的记忆

**违反这些规则将导致回答错误！**
"""
            system_prompt = enhanced_prompt
            print(f"[ReactAgent] 最终系统提示词长度: {len(system_prompt)} 字符")
        else:
            # 使用基础系统提示词
            system_prompt = load_system_prompts()

        # 保存系统提示词供后续使用
        self.system_prompt = system_prompt

        # 使用 LangChain 的 create_agent 创建智能体实例
        self.agent = create_agent(
            # 模型实例，来自 model.factory 模块
            model=chat_model,
            # 系统提示词（可能已增强）
            system_prompt=system_prompt,
            # 工具列表：RAG 检索、天气查询、用户定位、用户ID获取、
            # 当前月份、外部数据获取、报告上下文填充
            # 原有工具列表（已注释，可随时恢复）
            # tools=[rag_summarize, get_weather, get_user_location, get_user_id,
            #        get_current_month, fetch_external_data, fill_context_for_report],
            # 增强技能工具列表（提供更丰富的描述信息）
            tools=get_enhanced_tools(),
            # 中间件列表：工具监控、模型调用前日志、报告提示词切换
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def _simplify_memory_context(self, memory_context: str) -> str:
        """简化记忆上下文，提取最关键信息

        Args:
            memory_context: 完整的记忆上下文

        Returns:
            简化的记忆上下文，重点关注用户查询历史和重要事实
        """
        lines = memory_context.split('\n')
        simplified_lines = []
 
        # 提取关键部分
        sections_to_include = ['用户查询历史', '重要事实', '用户偏好']
        current_section = None
        in_target_section = False

        for line in lines:
            # 检查是否是章节标题
            if line.startswith('## '):
                section_name = line[3:].strip()
                # 检查是否是需要包含的章节
                in_target_section = any(target in section_name for target in sections_to_include)
                current_section = section_name

                if in_target_section:
                    simplified_lines.append(f"## {section_name}")
                    simplified_lines.append("")

            # 如果在目标章节中，收集内容
            elif in_target_section and line.strip():
                # 只收集条目（以"- "开头）或重要内容
                if line.startswith('- ') or ('**' in line and '**' in line):
                    simplified_lines.append(line)

        # 如果没有提取到足够内容，返回原始内容的前1000字符
        if len('\n'.join(simplified_lines)) < 500:
            return memory_context[:1500] + "\n\n[记忆内容已截断，完整内容请查看记忆文件]"

        return '\n'.join(simplified_lines)

    def execute_stream(self, query: str, session_id: str = None):
        """流式执行用户查询，实时返回 AI 响应。

        Args:
            query (str): 用户输入的查询文本
            session_id (str, optional): 会话ID，用于记忆管理。如果为None，则自动生成。

        Yields:
            str: 流式返回的 AI 响应片段，每个片段以换行符结尾
        """
        # 获取或创建会话ID
        if session_id is None:
            # 生成默认会话ID（简单实现，实际可根据需要改进）
            import uuid
            session_id = f"session_{uuid.uuid4().hex[:8]}"

        # 从记忆管理器获取历史消息
        history_messages = self.memory_manager.get_history(session_id)

        # 构造包含历史消息的输入
        # 注意：LangChain期望的消息格式为 [{"role": "system/user/assistant", "content": "..."}, ...]
        # 首先添加系统提示词，然后添加历史消息，最后是当前用户查询
        input_messages = []

        # 添加系统提示词作为第一条消息
        if hasattr(self, 'system_prompt') and self.system_prompt:
            input_messages.append({"role": "system", "content": self.system_prompt})

        # 添加历史消息
        input_messages.extend(history_messages)

        # 添加当前用户查询
        input_messages.append({"role": "user", "content": query})

        input_dict = {
            "messages": input_messages
        }

        # 收集完整的AI响应
        full_response_chunks = []

        # 第三个参数 context 是运行时上下文信息，用于提示词切换标记
        # 初始设置 report=False，表示使用主 ReAct 提示词
        # stream_mode="values" 表示流式返回每个步骤的输出值
        for chunk in self.agent.stream(input_dict, stream_mode="values", context={"report": False}):
            # 获取最新的一条消息（通常是 AI 的响应）
            latest_message = chunk["messages"][-1]
            # 如果消息有内容，则去除首尾空格并添加换行符后返回
            if latest_message.content:
                response_chunk = latest_message.content.strip() + "\n"
                full_response_chunks.append(response_chunk)
                yield response_chunk

        # 保存对话上下文到记忆
        if full_response_chunks:
            full_response = "".join(full_response_chunks).strip()
            # 移除末尾的换行符
            if full_response.endswith("\n"):
                full_response = full_response.rstrip("\n")
            self.memory_manager.save_context(session_id, query, full_response)

            # 记录到文件记忆日志（如果启用）
            if self.file_memory is not None:
                # 判断对话重要性（简单实现：根据长度和内容）
                is_important = (
                    len(query) > 20 or
                    len(full_response) > 50 or
                    any(keyword in query.lower() for keyword in ["记住", "重要", "下次", "故障", "问题"])
                )

                category = "learning" if is_important else "completion"

                # 创建日志摘要
                log_content = f"用户查询: {query[:100]}... | Agent响应: {full_response[:200]}..."
                metadata = {
                    "session_id": session_id,
                    "query_length": len(query),
                    "response_length": len(full_response),
                    "is_important": is_important
                }

                self.file_memory.log_event(category, log_content, metadata)

    # 保留原有execute_stream方法，注释掉以便恢复
    # def execute_stream(self, query: str):
    #     """流式执行用户查询，实时返回 AI 响应。
    #
    #     Args:
    #         query (str): 用户输入的查询文本
    #
    #     Yields:
    #         str: 流式返回的 AI 响应片段，每个片段以换行符结尾
    #     """
    #     # 构造 LangChain 智能体所需的输入格式
    #     input_dict = {
    #         "messages": [
    #             {"role": "user", "content": query},
    #         ]
    #     }
    #
    #     # 第三个参数 context 是运行时上下文信息，用于提示词切换标记
    #     # 初始设置 report=False，表示使用主 ReAct 提示词
    #     # stream_mode="values" 表示流式返回每个步骤的输出值
    #     for chunk in self.agent.stream(input_dict, stream_mode="values", context={"report": False}):
    #         # 获取最新的一条消息（通常是 AI 的响应）
    #         latest_message = chunk["messages"][-1]
    #         # 如果消息有内容，则去除首尾空格并添加换行符后返回
    #         if latest_message.content:
    #             yield latest_message.content.strip() + "\n"

    def consolidate_file_memory(self, force: bool = False):
        """触发文件记忆整理

        Args:
            force: 是否强制整理（忽略时间间隔）

        Returns:
            bool: 整理是否成功执行
        """
        if self.file_memory is None:
            print("[ReactAgent] 文件记忆未启用，无法整理")
            return False

        try:
            # 从配置获取整理天数
            from utils.config_handler import agent_conf
            file_memory_config = agent_conf.get("file_memory", {})
            consolidation_config = file_memory_config.get("consolidation", {})
            days_to_review = consolidation_config.get("days_to_review", 7)

            return self.file_memory.consolidate_memory(days_to_review=days_to_review, force=force)
        except Exception as e:
            print(f"[ReactAgent] 文件记忆整理失败: {e}")
            return False

    def clear_session_memory(self, session_id: str):
        """清空指定会话的记忆

        Args:
            session_id: 会话ID
        """
        self.memory_manager.clear_memory(session_id)

    def get_session_history(self, session_id: str):
        """获取指定会话的历史消息

        Args:
            session_id: 会话ID

        Returns:
            消息字典列表，每个字典包含 role 和 content 键
        """
        return self.memory_manager.get_history(session_id)

    def get_active_sessions(self):
        """获取所有活跃会话ID

        Returns:
            会话ID列表
        """
        return self.memory_manager.get_session_ids()

    def recall_from_memory(self, query: str, session_id: str = None) -> str:
        """从三层记忆系统回忆信息

        查询顺序：
        1. 首先检查短期记忆（当前会话）
        2. 其次检查文件记忆（MEMORY.md）
        3. 最后使用语义检索（历史日志）

        Args:
            query: 查询文本
            session_id: 会话ID（用于短期记忆查询）

        Returns:
            综合记忆结果，格式化为文本
        """
        results = []

        # 1. 检查短期记忆（当前会话）
        if session_id is not None:
            history = self.get_session_history(session_id)
            if history:
                # 从历史中搜索相关对话
                for msg in history:
                    if query.lower() in msg["content"].lower():
                        results.append(f"[短期记忆] {msg['role']}: {msg['content'][:200]}...")
                        break

        # 2. 检查文件记忆（如果启用）
        if self.file_memory is not None:
            try:
                # 文件记忆已经加载到系统提示词中，这里可以查询特定内容
                # 简单实现：返回提示词中已存在的记忆
                memory_context = self.file_memory.load_context()
                if query.lower() in memory_context.lower():
                    # 提取相关行
                    lines = memory_context.split('\n')
                    for line in lines:
                        if query.lower() in line.lower() and line.strip():
                            results.append(f"[文件记忆] {line[:200]}...")
                            break
            except Exception as e:
                print(f"[ReactAgent] 文件记忆查询失败: {e}")

        # 3. 检查语义记忆（如果启用）
        if self.semantic_memory is not None:
            try:
                semantic_results = self.semantic_memory.search_with_context(query, top_k=3)
                if semantic_results:
                    results.append(f"[语义记忆] 找到{len(semantic_results)}条相关记录:")
                    for i, result in enumerate(semantic_results[:3], 1):
                        results.append(f"  {i}. {result[:200]}...")
            except Exception as e:
                print(f"[ReactAgent] 语义记忆查询失败: {e}")

        if not results:
            return "未找到相关记忆。"

        return "\n".join(results)


if __name__ == '__main__':
    """模块测试入口：创建智能体实例并测试报告生成功能。"""
    # 创建智能体实例
    agent = ReactAgent()

    # 测试流式执行：请求生成使用报告
    for chunk in agent.execute_stream("给我生成我的使用报告"):
        # 打印流式响应，不换行（end=""）并立即刷新缓冲区（flush=True）
        print(chunk, end="", flush=True)
