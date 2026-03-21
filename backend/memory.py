import json
from datetime import date, timedelta
from pathlib import Path

MEMORY_DIR = Path("./memories")


def _ensure_dir() -> None:
    MEMORY_DIR.mkdir(exist_ok=True)


def append_insight(insight: dict) -> None:
    """Append a Reflect-generated teaching insight. Key: date, insight, action."""
    _ensure_dir()
    with open(MEMORY_DIR / "teaching-insights.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(insight, ensure_ascii=False) + "\n")


def read_insights(days: int = 14) -> list[dict]:
    """Read teaching insights from the last N days."""
    path = MEMORY_DIR / "teaching-insights.jsonl"
    if not path.exists():
        return []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        if entry.get("date", "") >= cutoff:
            results.append(entry)
    return results


def append_observation(observation: dict) -> None:
    """Append a Tutor real-time observation. Key: date, observation."""
    _ensure_dir()
    with open(MEMORY_DIR / "tutor-observations.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(observation, ensure_ascii=False) + "\n")


def read_observations(days: int = 7) -> list[dict]:
    """Read Tutor observations from the last N days."""
    path = MEMORY_DIR / "tutor-observations.jsonl"
    if not path.exists():
        return []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        if entry.get("date", "") >= cutoff:
            results.append(entry)
    return results
