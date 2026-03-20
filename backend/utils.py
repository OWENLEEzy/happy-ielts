import json
import re

from pydantic import BaseModel


def parse_json(content: str, model: type[BaseModel]) -> BaseModel:
    """Parse JSON from LLM content, stripping markdown code fences."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    return model.model_validate(json.loads(cleaned.strip()))
