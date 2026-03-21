import backend.memory as mem_mod


def test_append_and_read_insights(tmp_path):
    mem_mod.MEMORY_DIR = tmp_path
    mem_mod.append_insight({"date": "2026-03-21", "insight": "test", "action": "act"})
    results = mem_mod.read_insights(days=30)
    assert len(results) == 1
    assert results[0]["insight"] == "test"


def test_read_insights_filters_old(tmp_path):
    mem_mod.MEMORY_DIR = tmp_path
    mem_mod.append_insight({"date": "2020-01-01", "insight": "old", "action": "old"})
    mem_mod.append_insight({"date": "2026-03-21", "insight": "recent", "action": "recent"})
    results = mem_mod.read_insights(days=14)
    assert len(results) == 1
    assert results[0]["insight"] == "recent"


def test_append_and_read_observations(tmp_path):
    mem_mod.MEMORY_DIR = tmp_path
    mem_mod.append_observation({"date": "2026-03-21", "observation": "thesis weak"})
    results = mem_mod.read_observations(days=7)
    assert len(results) == 1
    assert results[0]["observation"] == "thesis weak"


def test_read_returns_empty_when_no_file(tmp_path):
    mem_mod.MEMORY_DIR = tmp_path
    assert mem_mod.read_insights() == []
    assert mem_mod.read_observations() == []


def test_insights_skips_blank_lines(tmp_path):
    mem_mod.MEMORY_DIR = tmp_path
    # Manually write a file with blank lines
    f = tmp_path / "teaching-insights.jsonl"
    f.write_text('\n{"date": "2026-03-21", "insight": "x", "action": "y"}\n\n')
    assert len(mem_mod.read_insights(days=30)) == 1


def test_read_skips_malformed_jsonl_line(tmp_path):
    """A corrupt line is silently skipped; valid lines are still returned."""
    mem_mod.MEMORY_DIR = tmp_path
    f = tmp_path / "teaching-insights.jsonl"
    f.write_text(
        '{"date": "2026-03-21", "insight": "good", "action": "ok"}\n'
        "NOT VALID JSON\n"
        '{"date": "2026-03-21", "insight": "also good", "action": "ok"}\n'
    )
    results = mem_mod.read_insights(days=30)
    assert len(results) == 2
    assert results[0]["insight"] == "good"
    assert results[1]["insight"] == "also good"
