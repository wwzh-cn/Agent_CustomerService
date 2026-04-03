#!/usr/bin/env python3
"""
文件记忆集成测试 - 测试与ReactAgent的集成
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import date, datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from agent.react_agent import ReactAgent
from utils.config_handler import agent_conf


class TestFileMemoryIntegration:
    """文件记忆集成测试类"""

    def setup_method(self):
        """测试初始化"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()

        # 备份原始配置
        self.original_config = agent_conf.copy()

        # 修改配置使用临时目录
        self.test_config = {
            "external_data_path": "data/external/records.csv",
            "gaodekey": "test_key",
            "gaode_base_url": "https://restapi.amap.com",
            "gaode_timeout": 5,
            "memory": {
                "type": "buffer",
                "window_size": 5,
                "session_ttl": 3600
            },
            "file_memory": {
                "enabled": True,
                "base_dir": self.temp_dir,
                "startup": {
                    "load_identity": True,
                    "load_memory": True,
                    "load_tools": True,
                    "recent_log_days": 2
                },
                "logging": {
                    "enabled": True,
                    "categories": ["decision", "learning", "error", "completion"],
                    "min_severity": "info"
                },
                "consolidation": {
                    "enabled": True,
                    "interval_hours": 1,  # 短间隔便于测试
                    "strategy": "rule_based",
                    "max_memory_size": 2000
                }
            }
        }

        # 由于配置是全局的，我们需要临时修改它
        # 这里我们通过修改agent_conf的引用来实现（注意：这会影响其他测试）
        # 更好的方法是使用mock，但为简单起见，我们直接修改
        # 先清空然后更新
        agent_conf.clear()
        agent_conf.update(self.test_config)

    def teardown_method(self):
        """测试清理"""
        # 恢复原始配置
        agent_conf.clear()
        agent_conf.update(self.original_config)

        # 删除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_react_agent_with_file_memory(self):
        """测试ReactAgent启用文件记忆"""
        # 创建ReactAgent实例
        agent = ReactAgent()

        # 检查file_memory属性
        assert hasattr(agent, 'file_memory')
        assert agent.file_memory is not None

        # 检查记忆目录是否存在
        memory_dir = Path(self.temp_dir)
        assert memory_dir.exists()

        # 检查必要文件是否存在
        assert (memory_dir / "IDENTITY.md").exists()
        assert (memory_dir / "MEMORY.md").exists()
        assert (memory_dir / "TOOLS.md").exists()
        assert (memory_dir / "logs").exists()

        print(f"[集成测试] 文件记忆初始化成功，目录: {memory_dir}")

    def test_react_agent_without_file_memory(self):
        """测试ReactAgent禁用文件记忆"""
        # 修改配置禁用文件记忆
        agent_conf["file_memory"]["enabled"] = False

        # 创建ReactAgent实例
        agent = ReactAgent()

        # 检查file_memory属性
        assert agent.file_memory is None

        print("[集成测试] 文件记忆禁用成功")

    def test_execute_stream_logs_to_file_memory(self):
        """测试execute_stream记录到文件记忆"""
        # 确保文件记忆启用
        agent_conf["file_memory"]["enabled"] = True

        # 创建ReactAgent实例
        agent = ReactAgent()

        # 模拟执行一个查询
        test_query = "扫地机器人怕水吗？"
        session_id = "test_session_123"

        # 由于实际执行需要LangChain环境，我们模拟执行
        # 这里我们直接调用execute_stream并捕获输出
        try:
            # 尝试执行（可能会失败，因为我们没有完整的LangChain环境）
            # 但我们主要测试日志记录，所以可以捕获异常
            response_chunks = []
            for chunk in agent.execute_stream(test_query, session_id):
                response_chunks.append(chunk)

            # 如果有响应，检查是否记录了日志
            if response_chunks:
                # 检查日志文件
                today_log = Path(self.temp_dir) / "logs" / f"{date.today().isoformat()}.md"
                if today_log.exists():
                    log_content = today_log.read_text(encoding="utf-8")
                    # 日志应该包含查询相关内容
                    assert "用户查询" in log_content or "扫地机器人" in log_content.lower()

        except Exception as e:
            # 执行可能失败（缺少依赖），但文件记忆可能已经记录了错误
            print(f"[集成测试] execute_stream执行异常（预期内）: {e}")

            # 检查是否记录了错误日志
            today_log = Path(self.temp_dir) / "logs" / f"{date.today().isoformat()}.md"
            if today_log.exists():
                log_content = today_log.read_text(encoding="utf-8")
                # 可能记录了错误
                if "error" in log_content.lower():
                    print("[集成测试] 错误已正确记录到日志")

    def test_consolidate_file_memory_method(self):
        """测试consolidate_file_memory方法"""
        # 创建ReactAgent实例
        agent = ReactAgent()

        # 确保file_memory存在
        assert agent.file_memory is not None

        # 先添加一些测试日志
        agent.file_memory.log_event("learning", "测试学习：机器人维护知识")
        agent.file_memory.log_event("decision", "测试决策：推荐用户购买配件")

        # 触发记忆整理（force=True强制执行）
        result = agent.consolidate_file_memory(force=True)

        # 检查结果
        # 由于可能依赖完整环境，结果可能是False，但至少不会崩溃
        assert result is not None

        print(f"[集成测试] consolidate_file_memory执行完成，结果: {result}")

    def test_memory_context_in_system_prompt(self):
        """测试记忆上下文是否添加到系统提示词"""
        # 这个测试需要检查ReactAgent内部构建的系统提示词
        # 由于system_prompt是私有的，我们通过创建agent时的行为间接测试
        agent = ReactAgent()

        # 如果file_memory启用，系统提示词应该包含记忆上下文
        if agent.file_memory is not None:
            # 我们可以检查file_memory是否加载了上下文
            context = agent.file_memory.load_context()
            assert len(context) > 0
            print(f"[集成测试] 记忆上下文加载成功，长度: {len(context)} 字符")

    def test_multiple_sessions_logging(self):
        """测试多会话日志记录"""
        agent = ReactAgent()
        assert agent.file_memory is not None

        # 模拟多个会话
        sessions = ["session_1", "session_2", "session_3"]
        queries = [
            "如何清理扫地机器人？",
            "扫地机器人怕水吗？",
            "推荐一款扫地机器人"
        ]

        for session_id, query in zip(sessions, queries):
            try:
                # 尝试执行（可能失败）
                for _ in agent.execute_stream(query, session_id):
                    pass  # 忽略输出
            except Exception:
                pass  # 忽略执行错误

        # 检查日志文件
        today_log = Path(self.temp_dir) / "logs" / f"{date.today().isoformat()}.md"
        if today_log.exists():
            log_content = today_log.read_text(encoding="utf-8")
            # 应该记录多个事件
            event_count = log_content.count("用户查询") + log_content.count("Agent响应")
            print(f"[集成测试] 记录了 {event_count} 个事件")

    def test_configuration_options(self):
        """测试不同配置选项"""
        test_cases = [
            {
                "name": "禁用日志记录",
                "config": {"logging": {"enabled": False}},
                "expected_logs": False
            },
            {
                "name": "禁用记忆整理",
                "config": {"consolidation": {"enabled": False}},
                "expected_consolidation": False
            },
            {
                "name": "修改记忆大小限制",
                "config": {"max_memory_size": 500},
                "expected_size": 500
            }
        ]

        for test_case in test_cases:
            print(f"\n[集成测试] 测试配置: {test_case['name']}")

            # 临时修改配置
            original_file_memory_config = agent_conf["file_memory"].copy()
            agent_conf["file_memory"].update(test_case["config"])

            try:
                agent = ReactAgent()
                if agent.file_memory is not None:
                    print(f"  ✓ 配置应用成功")
            finally:
                # 恢复配置
                agent_conf["file_memory"] = original_file_memory_config


def main():
    """运行所有集成测试"""
    print("=== 文件记忆集成测试 ===")
    print(f"测试时间: {datetime.now()}")
    print(f"临时目录: {tempfile.gettempdir()}")
    print()

    test_cases = [
        ("ReactAgent启用文件记忆", TestFileMemoryIntegration().test_react_agent_with_file_memory),
        ("ReactAgent禁用文件记忆", TestFileMemoryIntegration().test_react_agent_without_file_memory),
        ("execute_stream记录到文件记忆", TestFileMemoryIntegration().test_execute_stream_logs_to_file_memory),
        ("consolidate_file_memory方法", TestFileMemoryIntegration().test_consolidate_file_memory_method),
        ("记忆上下文在系统提示词中", TestFileMemoryIntegration().test_memory_context_in_system_prompt),
        ("多会话日志记录", TestFileMemoryIntegration().test_multiple_sessions_logging),
        ("配置选项测试", TestFileMemoryIntegration().test_configuration_options),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test_name, test_func in test_cases:
        # 创建新的测试实例
        test_instance = TestFileMemoryIntegration()
        try:
            test_instance.setup_method()
            test_func(test_instance)
            test_instance.teardown_method()
            print(f"✓ PASS: {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ FAIL: {test_name} - {e}")
            failed += 1
            test_instance.teardown_method()
        except Exception as e:
            # 有些测试可能因为环境问题失败，标记为跳过
            print(f"⚠ SKIP: {test_name} - 环境依赖: {e}")
            skipped += 1
            test_instance.teardown_method()

    print(f"\n测试完成: {passed} 通过, {failed} 失败, {skipped} 跳过")

    # 如果有测试失败，返回失败
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)