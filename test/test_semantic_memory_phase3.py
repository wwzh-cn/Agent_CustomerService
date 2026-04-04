#!/usr/bin/env python3
"""
阶段三：语义记忆集成测试

测试ReactAgent与语义记忆的集成功能。
"""

import sys
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")


class TestReactAgentSemanticMemoryIntegration:
    """测试ReactAgent与语义记忆的集成"""

    def test_reactagent_init_with_semantic_memory_enabled(self):
        """测试ReactAgent初始化时启用语义记忆"""
        print("=== 测试ReactAgent初始化时启用语义记忆 ===")

        # Mock配置
        mock_config = {
            "memory": {"type": "buffer"},
            "file_memory": {"enabled": False},
            "semantic_memory": {
                "enabled": True,
                "vector_db": {"path": "./test_vectordb", "collection_name": "test"},
                "embedding": {"model_name": "test-model", "device": "cpu"}
            }
        }

        # Mock agent_conf
        with patch('agent.react_agent.agent_conf', mock_config), \
             patch('agent.react_agent.chat_model') as mock_chat_model, \
             patch('agent.react_agent.load_system_prompts') as mock_load_prompts, \
             patch('agent.react_agent.get_enhanced_tools') as mock_get_tools, \
             patch('langchain.agents.create_agent') as mock_create_agent, \
             patch('agent.memory.semantic_memory.SemanticMemory') as MockSemanticMemory:

            # 设置mock
            mock_load_prompts.return_value = "Test system prompt"
            mock_get_tools.return_value = []
            mock_agent_instance = Mock()
            mock_create_agent.return_value = mock_agent_instance

            # Mock SemanticMemory实例
            mock_semantic_memory = Mock()
            mock_semantic_memory.vector_store = Mock()
            mock_semantic_memory.vector_store.persist_directory = "./test_vectordb"
            MockSemanticMemory.return_value = mock_semantic_memory

            # 导入并创建ReactAgent
            from agent.react_agent import ReactAgent

            agent = ReactAgent(semantic_memory_config=mock_config["semantic_memory"])

            # 验证语义记忆已初始化
            assert agent.semantic_memory is not None
            print("PASS: 语义记忆已初始化")

            # 验证SemanticMemory被正确调用
            MockSemanticMemory.assert_called_once_with(mock_config["semantic_memory"])
            print("PASS: SemanticMemory使用正确配置初始化")

            return True

    def test_reactagent_init_with_semantic_memory_disabled(self):
        """测试ReactAgent初始化时禁用语义记忆"""
        print("\n=== 测试ReactAgent初始化时禁用语义记忆 ===")

        # Mock配置
        mock_config = {
            "memory": {"type": "buffer"},
            "file_memory": {"enabled": False},
            "semantic_memory": {"enabled": False}
        }

        with patch('agent.react_agent.agent_conf', mock_config), \
             patch('agent.react_agent.chat_model'), \
             patch('agent.react_agent.load_system_prompts'), \
             patch('agent.react_agent.get_enhanced_tools'), \
             patch('langchain.agents.create_agent'):

            from agent.react_agent import ReactAgent

            agent = ReactAgent()

            # 验证语义记忆未初始化
            assert agent.semantic_memory is None
            print("PASS: 语义记忆未初始化（禁用状态）")

            return True

    def test_recall_from_memory_with_semantic_memory(self):
        """测试recall_from_memory方法使用语义记忆"""
        print("\n=== 测试recall_from_memory方法使用语义记忆 ===")

        # Mock配置
        mock_config = {
            "memory": {"type": "buffer"},
            "file_memory": {"enabled": False},
            "semantic_memory": {"enabled": True}
        }

        with patch('agent.react_agent.agent_conf', mock_config), \
             patch('agent.react_agent.chat_model'), \
             patch('agent.react_agent.load_system_prompts'), \
             patch('agent.react_agent.get_enhanced_tools'), \
             patch('langchain.agents.create_agent'), \
             patch('agent.memory.semantic_memory.SemanticMemory') as MockSemanticMemory:

            # 创建mock语义记忆
            mock_semantic_memory = Mock()
            mock_semantic_memory.search_with_context.return_value = [
                "2026-04-03: 用户咨询扫地机器人异响问题，建议检查滚轮和刷毛",
                "2026-04-02: 用户学习如何使用定时清洁功能"
            ]

            MockSemanticMemory.return_value = mock_semantic_memory

            from agent.react_agent import ReactAgent

            agent = ReactAgent(semantic_memory_config=mock_config["semantic_memory"])
            agent.semantic_memory = mock_semantic_memory

            # 调用recall_from_memory
            query = "扫地机器人异响"
            result = agent.recall_from_memory(query, session_id="test_session")

            # 验证结果包含语义记忆内容
            assert "语义记忆" in result
            assert "扫地机器人异响" in result
            print(f"PASS: recall_from_memory返回语义记忆结果")
            print(f"结果预览: {result[:200]}...")

            # 验证search_with_context被调用
            mock_semantic_memory.search_with_context.assert_called_once()
            print("PASS: search_with_context被正确调用")

            return True

    def test_recall_from_memory_without_semantic_memory(self):
        """测试recall_from_memory方法在没有语义记忆时的行为"""
        print("\n=== 测试recall_from_memory方法在没有语义记忆时的行为 ===")

        # Mock配置
        mock_config = {
            "memory": {"type": "buffer"},
            "file_memory": {"enabled": False},
            "semantic_memory": {"enabled": False}
        }

        with patch('agent.react_agent.agent_conf', mock_config), \
             patch('agent.react_agent.chat_model'), \
             patch('agent.react_agent.load_system_prompts'), \
             patch('agent.react_agent.get_enhanced_tools'), \
             patch('langchain.agents.create_agent'):

            from agent.react_agent import ReactAgent

            agent = ReactAgent()

            # 调用recall_from_memory
            query = "测试查询"
            result = agent.recall_from_memory(query, session_id="test_session")

            # 验证返回未找到相关记忆
            assert "未找到相关记忆" in result
            print(f"PASS: 无记忆时返回'未找到相关记忆'")

            return True

    def test_auto_index_on_startup(self):
        """测试启动时自动索引功能"""
        print("\n=== 测试启动时自动索引功能 ===")

        # Mock配置
        mock_config = {
            "memory": {"type": "buffer"},
            "file_memory": {"enabled": False},
            "semantic_memory": {
                "enabled": True,
                "indexing": {"auto_index": True}
            }
        }

        with patch('agent.react_agent.agent_conf', mock_config), \
             patch('agent.react_agent.chat_model'), \
             patch('agent.react_agent.load_system_prompts'), \
             patch('agent.react_agent.get_enhanced_tools'), \
             patch('langchain.agents.create_agent'), \
             patch('agent.memory.semantic_memory.SemanticMemory') as MockSemanticMemory, \
             patch('threading.Timer') as MockTimer, \
             patch('pathlib.Path.exists') as mock_exists:

            # 设置mock
            mock_exists.return_value = True
            mock_semantic_memory = Mock()
            mock_semantic_memory.index_logs_directory.return_value = {
                "indexed_files": 5,
                "total_chunks": 42
            }
            MockSemanticMemory.return_value = mock_semantic_memory

            # Mock Timer以便我们可以检查是否被调度
            timer_instance = Mock()
            MockTimer.return_value = timer_instance

            from agent.react_agent import ReactAgent

            agent = ReactAgent(semantic_memory_config=mock_config["semantic_memory"])
            agent.semantic_memory = mock_semantic_memory

            # 验证Timer被调度
            assert MockTimer.called
            print(f"PASS: 自动索引Timer已调度")

            # 验证Timer参数
            call_args = MockTimer.call_args
            assert call_args[0][0] == 5.0  # 延迟5秒
            assert call_args[1]['daemon'] is True
            print(f"PASS: Timer参数正确: 延迟{call_args[0][0]}秒，daemon={call_args[1]['daemon']}")

            # 手动调用定时器函数以测试索引逻辑
            timer_func = call_args[0][1]  # 定时器函数

            # 调用定时器函数
            timer_func()

            # 验证index_logs_directory被调用
            mock_semantic_memory.index_logs_directory.assert_called_once()
            print("PASS: index_logs_directory被调用")

            return True


def run_all_tests():
    """运行所有测试"""
    print("开始阶段三集成测试")
    print("=" * 60)

    tests = [
        TestReactAgentSemanticMemoryIntegration().test_reactagent_init_with_semantic_memory_enabled,
        TestReactAgentSemanticMemoryIntegration().test_reactagent_init_with_semantic_memory_disabled,
        TestReactAgentSemanticMemoryIntegration().test_recall_from_memory_with_semantic_memory,
        TestReactAgentSemanticMemoryIntegration().test_recall_from_memory_without_semantic_memory,
        TestReactAgentSemanticMemoryIntegration().test_auto_index_on_startup,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"FAIL: {test_func.__name__} 抛出异常: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("✅ 所有阶段三集成测试通过!")
        return True
    else:
        print("❌ 部分阶段三集成测试失败")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)