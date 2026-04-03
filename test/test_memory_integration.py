#!/usr/bin/env python3
"""
Memory Integration Test - Tests memory functionality with mocked agent
"""

import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")


def test_memory_integration_with_mocked_agent():
    """Test that ReactAgent uses memory correctly with mocked agent"""
    print("=== Testing memory integration with mocked agent ===")

    # Mock the dependencies that require external APIs
    with patch('agent.react_agent.chat_model') as mock_chat_model, \
         patch('agent.react_agent.load_system_prompts') as mock_load_prompts, \
         patch('agent.react_agent.get_enhanced_tools') as mock_get_tools, \
         patch('langchain.agents.create_agent') as mock_create_agent:

        # Setup mocks
        mock_load_prompts.return_value = "Test system prompt"
        mock_get_tools.return_value = []

        # Create a mock agent that returns predictable stream
        mock_agent_instance = Mock()
        mock_create_agent.return_value = mock_agent_instance

        # Import after mocking
        from agent.react_agent import ReactAgent

        # Create ReactAgent instance
        agent = ReactAgent()

        # Verify memory manager was created
        assert hasattr(agent, 'memory_manager')
        print("PASS: ReactAgent has memory_manager")

        # Setup mock stream response
        mock_chunk1 = {
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {"role": "assistant", "content": "It's sunny today."}
            ]
        }
        mock_chunk2 = {
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {"role": "assistant", "content": "It's sunny today. The temperature is 25°C."}
            ]
        }

        # Mock the stream method to yield our chunks
        def mock_stream(input_dict, stream_mode, context):
            yield mock_chunk1
            yield mock_chunk2

        mock_agent_instance.stream = mock_stream

        # Test execute_stream with session_id
        session_id = "test_session_123"
        query = "What's the weather?"

        # Clear any existing memory
        agent.clear_session_memory(session_id)

        # Execute and collect response
        response_chunks = list(agent.execute_stream(query, session_id=session_id))

        # Verify response was collected
        assert len(response_chunks) > 0
        print(f"PASS: Got {len(response_chunks)} response chunks")

        # Verify memory was saved
        history = agent.get_session_history(session_id)
        # Should have user message and assistant response
        assert len(history) == 2, f"Expected 2 messages in history, got {len(history)}"
        assert history[0]["role"] == "user"
        assert history[0]["content"] == query
        assert history[1]["role"] == "assistant"
        # Assistant content should contain the response
        assert "sunny" in history[1]["content"] or "25" in history[1]["content"]

        print("PASS: Memory correctly saved conversation")

        # Test multi-turn conversation
        second_query = "What about tomorrow?"
        mock_chunk3 = {
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {"role": "assistant", "content": "It's sunny today."},
                {"role": "user", "content": "What about tomorrow?"},
                {"role": "assistant", "content": "Tomorrow will be cloudy."}
            ]
        }

        def mock_stream2(input_dict, stream_mode, context):
            yield mock_chunk3

        mock_agent_instance.stream = mock_stream2

        # Execute second query
        list(agent.execute_stream(second_query, session_id=session_id))

        # Verify history now has 4 messages
        history = agent.get_session_history(session_id)
        assert len(history) == 4, f"Expected 4 messages after second turn, got {len(history)}"

        # Verify conversation order
        assert history[0]["role"] == "user"
        assert history[0]["content"] == query
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"
        assert history[2]["content"] == second_query
        assert history[3]["role"] == "assistant"
        assert "cloudy" in history[3]["content"]

        print("PASS: Multi-turn conversation memory works correctly")

        # Test session isolation
        other_session = "other_session"
        agent.clear_session_memory(other_session)
        mock_chunk4 = {
            "messages": [
                {"role": "user", "content": "Where am I?"},
                {"role": "assistant", "content": "You're in Beijing."}
            ]
        }

        def mock_stream3(input_dict, stream_mode, context):
            yield mock_chunk4

        mock_agent_instance.stream = mock_stream3
        list(agent.execute_stream("Where am I?", session_id=other_session))

        # Verify sessions are isolated
        session1_history = agent.get_session_history(session_id)
        session2_history = agent.get_session_history(other_session)
        assert len(session1_history) == 4, f"Session 1 should have 4 messages, got {len(session1_history)}"
        assert len(session2_history) == 2, f"Session 2 should have 2 messages, got {len(session2_history)}"
        assert "Beijing" in session2_history[1]["content"]
        assert "Beijing" not in session1_history[3]["content"]

        print("PASS: Session isolation works correctly")

        return True

    except Exception as e:
        print(f"FAIL: Memory integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_window_memory_mode():
    """Test window memory mode with mocked agent"""
    print("\n=== Testing window memory mode ===")

    try:
        with patch('agent.react_agent.chat_model'), \
             patch('agent.react_agent.load_system_prompts'), \
             patch('agent.react_agent.get_enhanced_tools'), \
             patch('langchain.agents.create_agent'):

            # Import after mocking
            from agent.react_agent import ReactAgent

            # Create agent with window memory config
            agent = ReactAgent(memory_config={
                "type": "buffer_window",
                "window_size": 2  # Keep only 2 messages (1 user + 1 assistant)
            })

            # Setup mock
            mock_agent = Mock()
            agent.agent = mock_agent

            # Mock stream to always return a simple response
            def mock_stream(input_dict, stream_mode, context):
                yield {
                    "messages": input_dict["messages"] + [{"role": "assistant", "content": "Response"}]
                }

            mock_agent.stream = mock_stream

            session_id = "window_session"

            # Add multiple conversations
            for i in range(5):
                list(agent.execute_stream(f"Message {i}", session_id=session_id))

            # With window size 2, we should have only last 2 messages (1 user + 1 assistant)
            # But memory manager handles window_size as number of message pairs
            # window_size=2 means keep 2 user messages and 2 assistant messages
            history = agent.get_session_history(session_id)
            # Expect 4 messages (2 user + 2 assistant)
            assert len(history) == 4, f"Window mode should keep 4 messages, got {len(history)}"

            # Verify recent messages are kept
            assert "Message 3" in history[0]["content"] or "Message 4" in history[0]["content"]
            assert "Message 4" in history[2]["content"]

            print("PASS: Window memory mode works correctly")
            return True

    except Exception as e:
        print(f"FAIL: Window memory mode test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run integration tests"""
    print("Starting Memory Integration Tests")
    print("=" * 50)

    tests = [
        test_memory_integration_with_mocked_agent,
        test_window_memory_mode,
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
        print("SUCCESS: All memory integration tests passed!")
        return True
    else:
        print("WARNING: Some memory integration tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)