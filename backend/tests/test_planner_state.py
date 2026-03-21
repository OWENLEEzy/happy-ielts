"""Tests for planner_state thread safety."""

import threading

import backend.orchestrator as orch


def test_planner_lock_prevents_double_start(monkeypatch):
    """_start_planner_thread with same date is idempotent under concurrent calls."""
    orch.planner_state.clear()
    start_count = []

    original_thread_init = threading.Thread.__init__

    def counting_thread_init(self, *args, **kwargs):
        original_thread_init(self, *args, **kwargs)
        start_count.append(1)

    def fake_run_sync(target_date, reflect_handoff):
        pass  # Don't actually run anything

    monkeypatch.setattr(orch, "_run_planner_sync", fake_run_sync)

    # Pre-set state to "running" — second call should be skipped
    from datetime import date, timedelta

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    with orch._planner_lock:
        orch.planner_state[tomorrow] = {"status": "running", "error": None}

    # This call should see "running" and skip
    orch._start_planner_thread(reflect_handoff=None)

    # State should still be "running", no new thread started for tomorrow
    assert orch.planner_state[tomorrow]["status"] == "running"
    assert len(start_count) == 0  # No new thread created
