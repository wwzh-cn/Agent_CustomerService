#!/usr/bin/env python3
"""
Memory Manager Unit Tests
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from agent.memory.memory_manager import MemoryManager, MemoryConfig, SessionMemory


def test_session_memory():
    """Test SessionMemory class"""
    print("=== Testing SessionMemory ===")

    # Create session memory
    session = SessionMemory(session_id="test_session")

    # Add messages
    session.add_message("user", "Hello")
    session.add_message("assistant", "Hi there")

    # Verify messages
    messages = session.get_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi there"

    # Test message limit
    limited = session.get_messages(max_messages=1)
    assert len(limited) == 1
    assert limited[0]["role"] == "assistant"  # Should return last message

    # Test clear
    session.clear()
    assert len(session.messages) == 0
    assert session.message_count == 0

    print("PASS: SessionMemory test passed")


def test_memory_manager_basic():
    """Test MemoryManager basic functionality"""
    print("\n=== Testing MemoryManager basic functionality ===")

    # Create memory manager
    manager = MemoryManager()

    # Get or create session
    session1 = manager.get_memory("session1")
    assert session1.session_id == "session1"

    # Save context
    manager.save_context("session1", "What's the weather?", "It's sunny")

    # Get history
    history = manager.get_history("session1")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "What's the weather?"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "It's sunny"

    # Test multi-session isolation
    manager.save_context("session2", "Where am I?", "You're in Beijing")
    history1 = manager.get_history("session1")
    history2 = manager.get_history("session2")
    assert len(history1) == 2  # session1 unchanged
    assert len(history2) == 2  # session2 has its own messages
    assert history2[0]["content"] == "Where am I?"

    # Test clear session
    manager.clear_memory("session1")
    assert len(manager.get_history("session1")) == 0

    # Get session ID list
    session_ids = manager.get_session_ids()
    assert "session2" in session_ids

    print("PASS: MemoryManager basic functionality test passed")


def test_memory_manager_window_mode():
    """Test window mode"""
    print("\n=== Testing MemoryManager window mode ===")

    # Create window mode memory manager
    manager = MemoryManager({
        "type": "buffer_window",
        "window_size": 2  # Keep last 2 messages
    })

    # Add multiple rounds of conversation (each round: user + assistant)
    for i in range(5):
        manager.save_context("window_session", f"Message {i}", f"Response {i}")

    # Verify window size limit
    history = manager.get_history("window_session")
    # Window size 2, keep last 2 user messages and 2 assistant messages, total 4
    assert len(history) == 4, f"Expected 4 messages, got {len(history)}"

    # Verify recent messages are kept
    assert history[0]["content"] == "Message 3"
    assert history[1]["content"] == "Response 3"
    assert history[2]["content"] == "Message 4"
    assert history[3]["content"] == "Response 4"

    print("PASS: Window mode test passed")


def test_memory_manager_expiration():
    """Test session expiration"""
    print("\n=== Testing MemoryManager session expiration ===")

    # Create memory manager with short TTL
    manager = MemoryManager({
        "session_ttl": 1  # 1 second expiration
    })

    # Create session
    manager.save_context("expiring_session", "Hello", "Hi")

    # Check immediately, should exist
    assert len(manager.get_history("expiring_session")) == 2

    # Wait for expiration
    time.sleep(1.5)

    # Trigger cleanup (by getting session list)
    session_ids = manager.get_session_ids()

    # Verify session expired
    assert "expiring_session" not in session_ids
    assert len(manager) == 0

    print("PASS: Session expiration test passed")


def test_memory_manager_config():
    """Test configuration loading"""
    print("\n=== Testing MemoryManager configuration loading ===")

    # Test default config
    manager1 = MemoryManager()
    assert manager1.config.memory_type == "buffer"
    assert manager1.config.window_size == 10
    assert manager1.config.session_ttl == 3600

    # Test custom config
    manager2 = MemoryManager({
        "type": "buffer_window",
        "window_size": 5,
        "session_ttl": 600,
        "max_tokens": 1000
    })
    assert manager2.config.memory_type == "buffer_window"
    assert manager2.config.window_size == 5
    assert manager2.config.session_ttl == 600
    assert manager2.config.max_tokens == 1000

    print("PASS: Configuration loading test passed")


def test_concurrent_access():
    """Test concurrent access (simple simulation)"""
    print("\n=== Testing MemoryManager concurrent access ===")

    import threading

    manager = MemoryManager()
    errors = []

    def worker(thread_id):
        try:
            for i in range(10):
                manager.save_context(f"thread_{thread_id}", f"Message {i}", f"Response {i}")
                time.sleep(0.001)
                history = manager.get_history(f"thread_{thread_id}")
                assert len(history) == (i + 1) * 2
        except Exception as e:
            errors.append(f"Thread {thread_id} error: {e}")

    # Start multiple threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all threads
    for t in threads:
        t.join()

    # Verify no errors
    assert len(errors) == 0, f"Concurrency test found errors: {errors}"

    # Verify each thread's session is independent
    for i in range(5):
        history = manager.get_history(f"thread_{i}")
        assert len(history) == 20  # 10 rounds * 2 messages

    print("PASS: Concurrent access test passed")


def main():
    """Run all tests"""
    print("Starting Memory Manager Unit Tests")
    print("=" * 50)

    tests = [
        test_session_memory,
        test_memory_manager_basic,
        test_memory_manager_window_mode,
        test_memory_manager_expiration,
        test_memory_manager_config,
        test_concurrent_access,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"FAIL: {test_func.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            failed += 1
            print(f"FAIL: {test_func.__name__} error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 50)
    print(f"Tests completed: {passed} passed, {failed} failed")

    if failed == 0:
        print("SUCCESS: All tests passed!")
        return True
    else:
        print("WARNING: Some tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)