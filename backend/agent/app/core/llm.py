import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEY = "change-me"


def build_llm() -> ChatOpenAI:
    if settings.llm_api_key == _PLACEHOLDER_KEY:
        raise AppError("LLM_API_KEY not configured", status_code=500)
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )


async def stream_chat(llm: BaseChatModel, messages: list[dict]) -> AsyncIterator[str]:
    logger.info("stream_chat start: model=%s, message_count=%d", settings.llm_model, len(messages))
    try:
        async for chunk in llm.astream(messages):
            content = chunk.content
            if isinstance(content, str) and content:
                yield content
    except Exception as exc:
        logger.exception("stream_chat failed: model=%s", settings.llm_model)
        raise AppError("MODEL_ERROR", status_code=503) from exc


def build_llm_with_tools(tools: list[Any]) -> BaseChatModel:
    llm = build_llm()
    if not tools:
        return llm
    return llm.bind_tools(tools)
