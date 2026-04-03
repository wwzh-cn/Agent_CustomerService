#!/usr/bin/env python3
"""
Simple Memory Integration Test
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")


def test_memory_manager_integration():
    """Test that memory manager works with ReactAgent"""
    print("=== Testing memory manager integration ===")

    # Test that memory manager can be imported and used
    from agent.memory.memory_manager import MemoryManager

    manager = MemoryManager()
    session_id = "integration_test_session"

    # Save some context
    manager.save_context(session_id, "Test query", "Test response")

    # Retrieve history
    history = manager.get_history(session_id)
    assert len(history) == 2
    assert history[0]["content"] == "Test query"
    assert history[1]["content"] == "Test response"

    print("PASS: Memory manager integration test passed")
    return True


def test_react_agent_memory_api():
    """Test ReactAgent memory API without initializing full agent"""
    print("\n=== Testing ReactAgent memory API ===")

    # Mock the dependencies to avoid external API calls
    import unittest.mock as mock

    with mock.patch('agent.react_agent.chat_model'), \
         mock.patch('agent.react_agent.load_system_prompts'), \
         mock.patch('agent.react_agent.get_enhanced_tools'), \
         mock.patch('langchain.agents.create_agent'):

        from agent.react_agent import ReactAgent

        # Create agent instance
        agent = ReactAgent()

        # Test memory API methods exist
        assert hasattr(agent, 'clear_session_memory')
        assert hasattr(agent, 'get_session_history')
        assert hasattr(agent, 'get_active_sessions')

        # Test with a session
        session_id = "api_test_session"
        agent.clear_session_memory(session_id)

        # Get history should return empty list
        history = agent.get_session_history(session_id)
        assert isinstance(history, list)
        assert len(history) == 0

        # Get active sessions
        sessions = agent.get_active_sessions()
        assert isinstance(sessions, list)

        print("PASS: ReactAgent memory API test passed")
        return True


def test_config_integration():
    """Test that config is properly integrated"""
    print("\n=== Testing config integration ===")

    from utils.config_handler import agent_conf

    # Check memory config exists
    assert "memory" in agent_conf, "memory config missing in agent.yml"

    memory_config = agent_conf["memory"]
    required_keys = ["type", "window_size", "session_ttl"]
    for key in required_keys:
        assert key in memory_config, f"memory.{key} missing in config"

    print(f"PASS: Config integration test passed. Memory config: {memory_config}")
    return True


def main():
    """Run simple integration tests"""
    print("Starting Simple Memory Integration Tests")
    print("=" * 50)

    tests = [
        test_memory_manager_integration,
        test_react_agent_memory_api,
        test_config_integration,
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
            print(f"FAIL: {test_func.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 50)
    print(f"Tests completed: {passed} passed, {failed} failed")

    if failed == 0:
        print("SUCCESS: All simple integration tests passed!")
        return True
    else:
        print("WARNING: Some simple integration tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)