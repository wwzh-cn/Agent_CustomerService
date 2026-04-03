"""
记忆管理器模块 - 管理多会话短期记忆

本模块提供 MemoryManager 类，用于存储和管理对话历史，支持多会话隔离。
基于内存字典存储，未来可扩展 Redis 等持久化后端。
"""

from typing import Dict, List, Optional, Any
import uuid
import time
import threading
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class MemoryConfig:
    """记忆配置类"""
    memory_type: str = "buffer"  # buffer 或 buffer_window
    max_tokens: Optional[int] = 2000  # 最大token限制（可选）
    window_size: int = 10  # 窗口模式下的消息数量
    session_ttl: int = 3600  # 会话过期时间（秒）


@dataclass
class SessionMemory:
    """会话记忆数据结构"""
    session_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    message_count: int = 0

    def add_message(self, role: str, content: str):
        """添加消息到会话历史"""
        self.messages.append({
            "role": role,
            "content": content
        })
        self.message_count += 1
        self.last_accessed = time.time()

    def get_messages(self, max_messages: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取消息历史，可限制数量"""
        self.last_accessed = time.time()
        if max_messages is not None and max_messages > 0:
            return self.messages[-max_messages:]
        return self.messages.copy()

    def clear(self):
        """清空会话记忆"""
        self.messages.clear()
        self.message_count = 0
        self.last_accessed = time.time()

    def is_expired(self, ttl: int) -> bool:
        """检查会话是否过期"""
        return (time.time() - self.last_accessed) > ttl


class MemoryManager:
    """记忆管理器类，管理多会话记忆"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化记忆管理器

        Args:
            config: 配置字典，支持以下键：
                - type: "buffer" 或 "buffer_window" (默认: "buffer")
                - max_tokens: 最大token限制 (默认: None)
                - window_size: 窗口大小，仅type="buffer_window"时有效 (默认: 10)
                - session_ttl: 会话过期时间（秒）(默认: 3600)
        """
        # 解析配置
        self.config = MemoryConfig()
        if config:
            if "type" in config:
                self.config.memory_type = config["type"]
            if "max_tokens" in config:
                self.config.max_tokens = config["max_tokens"]
            if "window_size" in config:
                self.config.window_size = config["window_size"]
            if "session_ttl" in config:
                self.config.session_ttl = config["session_ttl"]

        # 会话存储
        self._sessions: Dict[str, SessionMemory] = {}
        self._lock = threading.RLock()  # 可重入锁，用于线程安全

    def get_memory(self, session_id: Optional[str] = None) -> SessionMemory:
        """获取或创建会话记忆

        Args:
            session_id: 会话ID，如果为None则自动生成

        Returns:
            SessionMemory 对象
        """
        # 生成会话ID（如果未提供）
        if session_id is None:
            session_id = str(uuid.uuid4())

        # 清理过期会话
        self._cleanup_expired_sessions()

        with self._lock:
            # 获取或创建会话
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionMemory(session_id=session_id)

            return self._sessions[session_id]

    def save_context(self, session_id: str, input_str: str, output_str: str):
        """保存对话上下文到指定会话

        Args:
            session_id: 会话ID
            input_str: 用户输入
            output_str: AI响应
        """
        with self._lock:
            memory = self.get_memory(session_id)

            # 根据记忆类型处理消息限制
            if self.config.memory_type == "buffer_window":
                # 窗口模式：限制消息数量
                max_messages = self.config.window_size * 2  # 用户和AI消息各占一个
                if len(memory.messages) >= max_messages:
                    # 保留最近的消息
                    memory.messages = memory.messages[-(max_messages - 2):]

            # 添加用户消息和AI响应
            memory.add_message("user", input_str)
            memory.add_message("assistant", output_str)

    def clear_memory(self, session_id: str):
        """清空指定会话的记忆

        Args:
            session_id: 会话ID
        """
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].clear()

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取指定会话的历史消息

        Args:
            session_id: 会话ID

        Returns:
            消息字典列表，每个字典包含 role 和 content 键
        """
        with self._lock:
            memory = self.get_memory(session_id)

            # 根据记忆类型返回历史
            if self.config.memory_type == "buffer_window":
                # 窗口模式：限制消息数量
                max_messages = self.config.window_size * 2
                return memory.get_messages(max_messages)
            else:
                # 缓冲模式：返回所有消息
                return memory.get_messages()

    def get_session_ids(self) -> List[str]:
        """获取所有活跃会话ID

        Returns:
            会话ID列表
        """
        with self._lock:
            # 清理过期会话
            self._cleanup_expired_sessions()
            return list(self._sessions.keys())

    def cleanup(self):
        """清理所有过期会话"""
        with self._lock:
            self._cleanup_expired_sessions()

    def _cleanup_expired_sessions(self):
        """内部方法：清理过期会话"""
        expired_sessions = []
        for session_id, memory in self._sessions.items():
            if memory.is_expired(self.config.session_ttl):
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self._sessions[session_id]

        if expired_sessions:
            print(f"[MemoryManager] 清理了 {len(expired_sessions)} 个过期会话")

    def __len__(self) -> int:
        """返回活跃会话数量"""
        with self._lock:
            self._cleanup_expired_sessions()
            return len(self._sessions)


# 全局记忆管理器实例（可选）
_global_memory_manager: Optional[MemoryManager] = None


def get_global_memory_manager(config: Optional[Dict[str, Any]] = None) -> MemoryManager:
    """获取全局记忆管理器实例（单例模式）

    Args:
        config: 配置字典，仅在第一次调用时有效

    Returns:
        MemoryManager 实例
    """
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = MemoryManager(config)
    return _global_memory_manager


if __name__ == "__main__":
    """模块测试"""
    print("=== MemoryManager 模块测试 ===")

    # 创建记忆管理器
    manager = MemoryManager({
        "type": "buffer_window",
        "window_size": 3,
        "session_ttl": 300
    })

    # 测试会话管理
    session1 = "test_session_1"
    manager.save_context(session1, "你好", "你好，我是助手")
    manager.save_context(session1, "今天天气怎么样", "今天天气晴朗，25度")

    history = manager.get_history(session1)
    print(f"会话 {session1} 的历史消息:")
    for msg in history:
        print(f"  {msg['role']}: {msg['content']}")

    print(f"活跃会话数量: {len(manager)}")
    print(f"会话ID列表: {manager.get_session_ids()}")

    # 测试会话清理
    manager.clear_memory(session1)
    print(f"清空后消息数量: {len(manager.get_history(session1))}")

    print("测试完成！")