"""Shared LLM factory — uses DashScope's OpenAI-compatible international endpoint."""

import os

from langchain_openai import ChatOpenAI


def get_llm(model: str = "qwen-max") -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=os.environ["DASHSCOPE_API_KEY"],  # type: ignore[arg-type]
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
