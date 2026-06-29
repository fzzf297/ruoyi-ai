import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("AGENT_LLM_API_KEY", "test-key")
os.environ.setdefault("AGENT_LLM_BASE_URL", "https://api.openai.com/v1")
os.environ.setdefault("AGENT_LLM_MODEL", "gpt-4o-mini")

from app.core.config import settings  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.llm import build_llm, build_llm_with_tools, stream_chat  # noqa: E402


def test_build_llm_returns_chat_openAI_with_settings() -> None:
    with patch("app.core.llm.ChatOpenAI") as mock_cls:
        build_llm()
        mock_cls.assert_called_once_with(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )


def test_build_llm_rejects_placeholder_key() -> None:
    with patch("app.core.llm.settings") as mock_settings:
        mock_settings.llm_api_key = "change-me"
        mock_settings.llm_base_url = "https://api.example.com/v1"
        mock_settings.llm_model = "gpt-4o-mini"
        with pytest.raises(AppError) as exc_info:
            build_llm()
        assert exc_info.value.status_code == 500
        assert "LLM_API_KEY" in exc_info.value.message
        assert "change-me" not in exc_info.value.message


class _Chunk:
    def __init__(self, content: str) -> None:
        self.content = content


class _AsyncIter:
    def __init__(self, items: list) -> None:
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


@pytest.mark.anyio
async def test_stream_chat_yields_non_empty_content() -> None:
    llm = MagicMock()
    llm.astream = MagicMock(
        return_value=_AsyncIter([_Chunk("hello"), _Chunk(""), _Chunk(" world")])
    )

    result = [text async for text in stream_chat(llm, [{"role": "user", "content": "hi"}])]
    assert result == ["hello", " world"]


@pytest.mark.anyio
async def test_stream_chat_raises_app_error_on_llm_failure() -> None:
    llm = MagicMock()

    def raise_err(_messages):
        raise RuntimeError("upstream down")

    llm.astream = MagicMock(side_effect=raise_err)

    with pytest.raises(AppError) as exc_info:
        async for _ in stream_chat(llm, [{"role": "user", "content": "hi"}]):
            pass
    assert exc_info.value.status_code == 503


def test_build_llm_with_tools_calls_bind_tools() -> None:
    with patch("app.core.llm.ChatOpenAI") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        bound = MagicMock()
        instance.bind_tools.return_value = bound

        tool = MagicMock()
        result = build_llm_with_tools([tool])
        instance.bind_tools.assert_called_once_with([tool])
        assert result is bound


def test_build_llm_with_tools_empty_skips_bind() -> None:
    with patch("app.core.llm.ChatOpenAI") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance

        result: Any = build_llm_with_tools([])
        instance.bind_tools.assert_not_called()
        assert result is instance

