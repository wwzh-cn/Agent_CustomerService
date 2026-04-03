#!/usr/bin/env python3
"""
ReactAgent Memory Integration Tests
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")


def test_import_and_initialization():
    """Test that ReactAgent can be imported and initialized"""
    print("=== Testing ReactAgent import and initialization ===")

    try:
        from agent.react_agent import ReactAgent
        print("PASS: ReactAgent imported successfully")
    except ImportError as e:
        print(f"FAIL: Failed to import ReactAgent: {e}")
        return False

    try:
        # Test initialization with default config
        agent = ReactAgent()
        print("PASS: ReactAgent initialized successfully")

        # Check memory manager attribute exists
        assert hasattr(agent, 'memory_manager'), "memory_manager attribute missing"
        print("PASS: memory_manager attribute exists")

        # Check methods exist
        assert hasattr(agent, 'clear_session_memory'), "clear_session_memory method missing"
        assert hasattr(agent, 'get_session_history'), "get_session_history method missing"
        assert hasattr(agent, 'get_active_sessions'), "get_active_sessions method missing"
        print("PASS: Memory management methods exist")

        return True

    except Exception as e:
        print(f"FAIL: ReactAgent initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_methods():
    """Test memory management methods"""
    print("\n=== Testing ReactAgent memory methods ===")

    try:
        from agent.react_agent import ReactAgent
        agent = ReactAgent()

        # Test session management
        session_id = "test_session_123"

        # Clear memory (should not crash)
        agent.clear_session_memory(session_id)
        print("PASS: clear_session_memory executed without error")

        # Get history (should return empty list)
        history = agent.get_session_history(session_id)
        assert isinstance(history, list), f"Expected list, got {type(history)}"
        assert len(history) == 0, f"Expected empty history, got {len(history)} items"
        print("PASS: get_session_history returns empty list for new session")

        # Get active sessions
        sessions = agent.get_active_sessions()
        assert isinstance(sessions, list), f"Expected list, got {type(sessions)}"
        print("PASS: get_active_sessions returns list")

        return True

    except Exception as e:
        print(f"FAIL: Memory methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_execute_stream_signature():
    """Test that execute_stream accepts session_id parameter"""
    print("\n=== Testing execute_stream signature ===")

    try:
        from agent.react_agent import ReactAgent
        import inspect

        agent = ReactAgent()

        # Check method signature
        sig = inspect.signature(agent.execute_stream)
        params = list(sig.parameters.keys())

        # Should have at least 'query' and optionally 'session_id'
        assert 'query' in params, "execute_stream missing 'query' parameter"

        # Check if session_id is present (positional or keyword)
        # In our implementation, it should be 'session_id' with default None
        assert 'session_id' in params, "execute_stream missing 'session_id' parameter"

        # Check default value
        param = sig.parameters['session_id']
        assert param.default is None, f"session_id should default to None, got {param.default}"

        print("PASS: execute_stream has correct signature with session_id parameter")
        return True

    except Exception as e:
        print(f"FAIL: execute_stream signature test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_loading():
    """Test that memory config is loaded from agent.yml"""
    print("\n=== Testing memory config loading ===")

    try:
        from agent.react_agent import ReactAgent
        from utils.config_handler import agent_conf

        # Check that memory config exists in agent_conf
        assert "memory" in agent_conf, "memory config not found in agent.yml"

        memory_config = agent_conf["memory"]
        assert isinstance(memory_config, dict), f"memory config should be dict, got {type(memory_config)}"

        # Check required fields
        assert "type" in memory_config, "memory.type not found in config"
        assert "window_size" in memory_config, "memory.window_size not found in config"
        assert "session_ttl" in memory_config, "memory.session_ttl not found in config"

        print(f"PASS: Memory config loaded: type={memory_config['type']}, "
              f"window_size={memory_config['window_size']}, "
              f"session_ttl={memory_config['session_ttl']}")

        # Test agent initialization with config
        agent = ReactAgent()
        # Just check it initializes without error
        print("PASS: ReactAgent initialized with config from agent.yml")

        return True

    except Exception as e:
        print(f"FAIL: Config loading test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("Starting ReactAgent Memory Integration Tests")
    print("=" * 50)

    tests = [
        test_import_and_initialization,
        test_memory_methods,
        test_execute_stream_signature,
        test_config_loading,
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
        print("SUCCESS: All ReactAgent memory integration tests passed!")
        return True
    else:
        print("WARNING: Some ReactAgent memory integration tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)