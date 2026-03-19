import logging

from langchain.tools import tool
from langchain_anthropic import ChatAnthropic

from backend.models import WritingFeedback, WritingTask

logger = logging.getLogger(__name__)

_llm = ChatAnthropic(model="claude-haiku-4-5-20251001")  # type: ignore[call-arg]

FEEDBACK_PROMPT = """
You are a native English editor reviewing writing from a Chinese professional.

Source article topic: {article_topic}
Writer's goal: {user_goal}
Writer's level: {level}/10

PASS 1 — Grammar: Find objective errors (tense, agreement, articles).
PASS 2 — Native fluency: Find phrases where Chinese L1 is showing through.
  Ask: "Would a native speaker in this professional context phrase it this way?"
  Focus on: verb weakening (using "have" instead of strong verbs), logic connectors,
            sentence rhythm.
  Do NOT flag correct-but-non-native as grammar errors.

IMPORTANT: Only flag the 1-2 most severe issues. Do not overwhelm the learner.
Include exactly 2 rewrite_suggestions (complete rewrites of the full text).
Be encouraging — start with what's good.

Return valid JSON matching the WritingFeedback schema exactly. No prose outside JSON.

User's writing:
{user_text}
"""


@tool
def explain_word(word: str, context: str, level: int) -> str:
    """Explain a word in context for a language learner at the given level (1-10)."""
    prompt = f"""
Explain the word "{word}" as used in this sentence:
"{context}"

The learner is level {level}/10. Adjust depth accordingly:
- Level 1-3: simple definition + 1 example
- Level 4-6: definition + usage nuance + 1 native collocation
- Level 7-10: usage nuance + register note + comparison with synonyms

Respond in Chinese (简体中文). Keep it under 100 words.
"""
    response = _llm.invoke(prompt)
    return str(response.content)


@tool
def analyze_sentence(sentence: str) -> str:
    """Break down a complex English sentence into its grammatical structure."""
    prompt = f"""
Analyze this English sentence for a Chinese learner:
"{sentence}"

Identify: main clause, subordinate clauses, subject/verb/object, and any difficult structures.
Use color labels in your response like [主语], [谓语], [宾语], [从句].
Explain in Chinese (简体中文). Keep it under 150 words.
"""
    response = _llm.invoke(prompt)
    return str(response.content)


def run_feedback(user_text: str, task: WritingTask, user_goal: str, level: int) -> WritingFeedback:
    """Run structured writing feedback. Retries up to 3 times on parse failure."""
    structured_llm = _llm.with_structured_output(WritingFeedback, include_raw=True)
    prompt = FEEDBACK_PROMPT.format(
        article_topic=task.instruction[:100],
        user_goal=user_goal,
        level=level,
        user_text=user_text,
    )
    for attempt in range(3):
        result: dict = structured_llm.invoke(prompt)  # type: ignore[assignment]
        if result["parsed"] is not None:
            return result["parsed"]
        logger.warning(f"Feedback attempt {attempt + 1} failed: {result['raw']}")
    raise ValueError("Feedback generation failed after 3 attempts")
