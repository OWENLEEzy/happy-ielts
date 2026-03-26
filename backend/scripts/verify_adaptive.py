"""Adaptive Learning Chain — end-to-end diagnostic script.

Run from project root:
    uv run python backend/scripts/verify_adaptive.py
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure project root is on sys.path so `from backend.xxx import ...` works
# regardless of whether this script is invoked directly or via uv.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── ANSI color helpers ────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def _pass(label: str) -> None:
    print(f"{GREEN}✓ PASS{RESET}  {label}")


def _fail(label: str, detail: str = "") -> None:
    msg = f"{RED}✗ FAIL{RESET}  {label}"
    if detail:
        msg += f"\n       detail: {detail}"
    print(msg)


# ── Result accumulator ────────────────────────────────────────────────────────

_results: list[bool] = []


def assert_equal(label: str, actual, expected) -> None:
    ok = actual == expected
    _results.append(ok)
    if ok:
        _pass(label)
    else:
        _fail(label, f"expected={expected!r}, got={actual!r}")


def assert_true(label: str, value: bool, detail: str = "") -> None:
    _results.append(bool(value))
    if value:
        _pass(label)
    else:
        _fail(label, detail)


# ── Fake quiz data ────────────────────────────────────────────────────────────

FAKE_QUIZ = [
    {
        "question": "What is the capital of France?",
        "hint": "Think European capitals",
        "answerOptions": [
            {"text": "Berlin", "isCorrect": False, "rationale": "Germany's capital"},
            {"text": "Paris", "isCorrect": True, "rationale": "Correct!"},
            {"text": "Madrid", "isCorrect": False, "rationale": "Spain's capital"},
        ],
    },
    {
        "question": "What is 2 + 2?",
        "hint": "Basic arithmetic",
        "answerOptions": [
            {"text": "3", "isCorrect": False, "rationale": "One less"},
            {"text": "5", "isCorrect": False, "rationale": "One more"},
            {"text": "4", "isCorrect": True, "rationale": "Correct!"},
        ],
    },
]


# ── Main diagnostic coroutine ─────────────────────────────────────────────────


async def main() -> None:
    # Use a temp directory so we never touch the real DB.
    tmp_dir = tempfile.mkdtemp()
    db_path = f"{tmp_dir}/test_adaptive.sqlite3"
    print(f"\nUsing temp DB: {db_path}\n")

    # Import AFTER the path is established so there's no accidental singleton
    # contamination from the real database.
    from backend.database import Database
    from backend.general.nodes import _get_valid_reshuffled_quiz
    from backend.models import (
        LearningChapter,
        LearningLesson,
        LearningMap,
        UserGoalProfile,
    )

    db = Database(db_path)

    # ── Step 1: Create project + learning map + 2 lessons ────────────────────
    print("── Step 1: Seed project, learning map, and lessons ──")

    goal_profile = UserGoalProfile(
        mode="skill",
        topic="Python Programming",
        motivation="Career switch",
        goal_outcome="Build production-grade Python apps",
        context="Working software developer, new to Python",
        current_level="beginner",
        time_per_week=10,
        duration_weeks=8,
        constraints=[],
    )

    learning_map = LearningMap(
        topic="Python Programming",
        total_weeks=8,
        chapters=[
            LearningChapter(
                title="基础入门",
                lessons=[
                    LearningLesson(title="Python Basics", objectives=["Variables", "Types"]),
                    LearningLesson(title="Control Flow", objectives=["if/else", "loops"]),
                ],
            ),
            LearningChapter(
                title="进阶技巧",
                lessons=[
                    LearningLesson(title="Functions", objectives=["def", "return"]),
                ],
            ),
        ],
    )

    project_id = db.create_general_project("Python Programming", goal_profile, tier="free")
    db.update_general_project_profile_and_map(project_id, goal_profile, learning_map)
    db.update_general_project_status(project_id, "active")

    # Create 2 lessons (chapter=0, lesson=0 and chapter=0, lesson=1)
    db.upsert_general_lesson(
        project_id=project_id,
        chapter=0,
        lesson=0,
        title="Python Basics",
        study_guide="Learn variables and types.",
        quiz_json=FAKE_QUIZ,
        flashcards=[],
    )
    db.upsert_general_lesson(
        project_id=project_id,
        chapter=0,
        lesson=1,
        title="Control Flow",
        study_guide="Learn if/else and loops.",
        quiz_json=FAKE_QUIZ,
        flashcards=[],
    )

    lessons = db.get_project_lessons(project_id)
    assert_true("Two lessons created", len(lessons) == 2, f"got {len(lessons)} lessons")

    lid0 = lessons[0].id  # lesson at chapter=0, lesson=0
    print(f"  lesson[0].id = {lid0}, lesson[1].id = {lessons[1].id}\n")

    # ── Step 2: Save two sessions for lesson 0 with scores 30 then 25 ────────
    print("── Step 2: Save two sessions (score=30, then score=25) ──")

    # First session: score=30 (older)
    db.save_general_session(
        project_id=project_id,
        lesson_id=lid0,
        quiz_answers=[0, 0],  # both wrong (index 0 is not correct for either)
        quiz_score=30,
        qa_history=[],
    )

    # Small sleep to guarantee created_at ordering
    await asyncio.sleep(0.01)

    # Second session: score=25 (newer, even worse)
    db.save_general_session(
        project_id=project_id,
        lesson_id=lid0,
        quiz_answers=[1, 0],
        quiz_score=25,
        qa_history=[],
    )

    print("  Two sessions saved.\n")

    # ── Step 3: run_reflect with mocked run_targeted_research ────────────────
    print("── Step 3: run_reflect (mocked run_targeted_research) ──")

    mock_targeted_research = AsyncMock(return_value=None)

    with (
        patch("backend.general.reflect.get_db", return_value=db),
        patch("backend.general.researcher.run_targeted_research", mock_targeted_research),
    ):
        from backend.general.reflect import run_reflect

        await run_reflect(project_id)

    print("  run_reflect completed.\n")

    # ── Step 4: Query the student model ──────────────────────────────────────
    print("── Step 4: Query GeneralStudentModel ──")

    student_model = db.get_general_student_model_full(project_id)
    assert_true("Student model exists", student_model is not None, "model was None")

    if student_model:
        print(f"  goal_progress  = {student_model.goal_progress}")
        print(f"  dimensions     = {student_model.dimensions}")
        print(f"  fsrs_due count = {len(student_model.fsrs_due)}\n")

        # ── Assertion A: goal_progress == 0.0 ────────────────────────────────
        # Only lesson 0 has sessions; its avg mastery = mean([0.25, 0.30]) = 0.275 < 0.5.
        # "基础入门" has sessions; "进阶技巧" has none (no sessions at all).
        # mastered chapters = 0 → goal_progress = 0/2 = 0.0
        assert_equal("goal_progress == 0.0", student_model.goal_progress, 0.0)

        # ── Assertion B: trend == "worsening" ────────────────────────────────
        # Sessions returned DESC: newest first → scores = [0.25, 0.30]
        # scores[0]=0.25 < scores[-1]=0.30 → worsening
        dim = student_model.dimensions.get("基础入门")
        assert_true(
            '"基础入门" dimension exists',
            dim is not None,
            f"dimensions keys: {list(student_model.dimensions.keys())}",
        )
        if dim:
            assert_equal(
                'dimensions["基础入门"].trend == "worsening"',
                dim.trend,
                "worsening",
            )

    # ── Step 5: get_last_session_for_lesson ──────────────────────────────────
    print("── Step 5: get_last_session_for_lesson ──")

    last_session = db.get_last_session_for_lesson(project_id, lid0)
    print(f"  last_session = {last_session}\n")

    assert_true(
        "get_last_session_for_lesson returns a result",
        last_session is not None,
        "returned None",
    )
    if last_session:
        assert_equal(
            "Most recent session has quiz_score=25",
            last_session.get("quiz_score"),
            25,
        )

    # ── Step 6: Simulate route_start retry_hint computation ──────────────────
    print("── Step 6: Simulate route_start retry_hint ──")

    # Use a fixed lesson_id so the reshuffle is deterministic.
    lesson_id_for_test = lid0
    reshuffled = _get_valid_reshuffled_quiz(FAKE_QUIZ, lesson_id_for_test)

    # Determine which answer indices are WRONG after reshuffling, so we can guarantee
    # retry_hint is non-empty (quiz_score < 60 and at least one wrong answer).
    # After reshuffling with lesson_id=lid0 (seed=lid0), find the correct index for
    # each question and use a different index as the student's (wrong) answer.
    prior_answers = []
    for q in reshuffled:
        opts = q.get("answerOptions", [])
        correct_idx = next((j for j, o in enumerate(opts) if o.get("isCorrect")), 0)
        # Pick a wrong index: (correct_idx + 1) % len(opts)
        wrong_idx = (correct_idx + 1) % len(opts)
        prior_answers.append(wrong_idx)

    saved_answers: list[int] = prior_answers

    retry_hint = []
    for i, q in enumerate(reshuffled):
        opts = q.get("answerOptions", [])
        student_idx = saved_answers[i] if i < len(saved_answers) else None
        loop_correct: int | None = next((j for j, o in enumerate(opts) if o.get("isCorrect")), None)
        if student_idx != loop_correct and loop_correct is not None:
            retry_hint.append(
                {
                    "question": q.get("question", ""),
                    "correct_answer": opts[loop_correct].get("text", ""),
                }
            )

    print(f"  reshuffled quiz ({len(reshuffled)} questions)")
    print(f"  retry_hint = {retry_hint}\n")

    # ── Assertion C: retry_hint is non-empty list of dicts ───────────────────
    assert_true(
        "retry_hint is non-empty when quiz_score < 60",
        len(retry_hint) > 0,
        f"retry_hint was empty. reshuffled={reshuffled}, prior_answers={prior_answers}",
    )
    assert_true(
        "retry_hint items have 'question' key",
        all("question" in h for h in retry_hint),
        str(retry_hint),
    )
    assert_true(
        "retry_hint items have 'correct_answer' key",
        all("correct_answer" in h for h in retry_hint),
        str(retry_hint),
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    total = len(_results)
    passed = sum(_results)
    failed = total - passed
    if failed == 0:
        print(f"{GREEN}All {total} assertions PASSED.{RESET}")
    else:
        print(f"{RED}{failed}/{total} assertions FAILED.{RESET}")
    print("─" * 60 + "\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
