"""Tests for thread-safe Event-based implementation of _agent_running and _interrupt_requested.

These tests verify:
1. _agent_running works correctly as a threading.Event
2. _interrupt_requested works correctly as a threading.Event  
3. Concurrent access from multiple threads is safe
"""

import threading
import time
import unittest

from run_agent import AIAgent


class TestAgentRunningEvent(unittest.TestCase):
    """Verify _agent_running Event works correctly."""

    def test_agent_running_starts_cleared(self):
        """_agent_running Event should start in cleared (not set) state."""
        cli_mod = __import__('cli', fromlist=['HermesCLI'])
        cli = object.__new__(cli_mod.HermesCLI)
        cli._agent_running = threading.Event()
        
        assert cli._agent_running.is_set() is False

    def test_agent_running_set_and_clear(self):
        """Setting and clearing _agent_running Event works."""
        cli_mod = __import__('cli', fromlist=['HermesCLI'])
        cli = object.__new__(cli_mod.HermesCLI)
        cli._agent_running = threading.Event()
        
        cli._agent_running.set()
        assert cli._agent_running.is_set() is True
        
        cli._agent_running.clear()
        assert cli._agent_running.is_set() is False

    def test_agent_running_concurrent_reads(self):
        """Multiple threads can safely read _agent_running.is_set() concurrently."""
        cli_mod = __import__('cli', fromlist=['HermesCLI'])
        cli = object.__new__(cli_mod.HermesCLI)
        cli._agent_running = threading.Event()
        
        results = []
        errors = []

        def reader():
            try:
                for _ in range(100):
                    results.append(cli._agent_running.is_set())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All reads should be False since event was never set
        assert all(r is False for r in results)

    def test_agent_running_concurrent_set_from_different_thread(self):
        """Setting _agent_running from one thread is visible to another."""
        cli_mod = __import__('cli', fromlist=['HermesCLI'])
        cli = object.__new__(cli_mod.HermesCLI)
        cli._agent_running = threading.Event()
        
        seen_values = []
        barrier = threading.Barrier(2)

        def setter():
            barrier.wait()
            time.sleep(0.01)  # Ensure reader starts first
            cli._agent_running.set()

        def reader():
            barrier.wait()
            for _ in range(50):
                seen_values.append(cli._agent_running.is_set())
                time.sleep(0.002)

        t1 = threading.Thread(target=setter)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Reader should eventually see True
        assert True in seen_values


class TestInterruptRequestedEvent(unittest.TestCase):
    """Verify _interrupt_requested Event works correctly."""

    def test_interrupt_requested_starts_cleared(self):
        """_interrupt_requested should start in cleared state."""
        agent = AIAgent.__new__(AIAgent)
        agent._interrupt_requested = threading.Event()
        agent._interrupt_message = None
        agent._active_children = []
        agent._active_children_lock = threading.Lock()
        agent.quiet_mode = True

        assert agent._interrupt_requested.is_set() is False

    def test_interrupt_sets_event_and_propagates(self):
        """Calling interrupt() sets the Event and propagates to children."""
        agent = AIAgent.__new__(AIAgent)
        agent._interrupt_requested = threading.Event()
        agent._interrupt_message = None
        agent._active_children = []
        agent._active_children_lock = threading.Lock()
        agent.quiet_mode = True

        child = AIAgent.__new__(AIAgent)
        child._interrupt_requested = threading.Event()
        child._interrupt_message = None
        child._active_children = []
        child._active_children_lock = threading.Lock()
        child.quiet_mode = True

        agent._active_children.append(child)

        agent.interrupt("test message")

        assert agent._interrupt_requested.is_set() is True
        assert child._interrupt_requested.is_set() is True
        assert child._interrupt_message == "test message"

    def test_clear_interrupt_clears_event(self):
        """clear_interrupt() clears the Event."""
        agent = AIAgent.__new__(AIAgent)
        agent._interrupt_requested = threading.Event()
        agent._interrupt_requested.set()
        agent._interrupt_message = "old message"
        agent._active_children = []
        agent._active_children_lock = threading.Lock()
        agent.quiet_mode = True

        from tools.interrupt import set_interrupt
        set_interrupt(True)

        agent.clear_interrupt()

        assert agent._interrupt_requested.is_set() is False
        assert agent._interrupt_message is None

    def test_is_interrupted_property_uses_event(self):
        """is_interrupted property correctly delegates to Event.is_set()."""
        agent = AIAgent.__new__(AIAgent)
        agent._interrupt_requested = threading.Event()
        agent._interrupt_message = None
        agent._active_children = []
        agent._active_children_lock = threading.Lock()
        agent.quiet_mode = True

        assert agent.is_interrupted is False

        agent._interrupt_requested.set()
        assert agent.is_interrupted is True

        agent._interrupt_requested.clear()
        assert agent.is_interrupted is False

    def test_concurrent_interrupt_check(self):
        """Multiple threads can safely check _interrupt_requested concurrently."""
        agent = AIAgent.__new__(AIAgent)
        agent._interrupt_requested = threading.Event()
        agent._interrupt_message = None
        agent._active_children = []
        agent._active_children_lock = threading.Lock()
        agent.quiet_mode = True

        results = []
        errors = []

        def checker():
            try:
                for _ in range(100):
                    results.append(agent._interrupt_requested.is_set())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=checker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(r is False for r in results)


if __name__ == "__main__":
    unittest.main()
