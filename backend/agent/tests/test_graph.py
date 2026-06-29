import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("AGENT_LLM_API_KEY", "test-key")

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402

from app.graphs.agent import build_graph  # noqa: E402


@pytest.fixture
def tmp_db_path(tmp_path):
    return tmp_path / "agent_graph_test.db"


def _mock_llm(response_content: str = "hello from agent") -> MagicMock:
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=response_content))
    return llm


@pytest.mark.anyio
async def test_graph_produces_ai_message() -> None:
    llm = _mock_llm("hello world")
    app = build_graph(llm)

    result = await app.ainvoke(
        {"messages": [HumanMessage(content="hi")], "correlation_id": "c1"},
        config={"configurable": {"thread_id": "t1"}},
    )
    assert len(result["messages"]) == 2
    assert result["messages"][0].content == "hi"
    assert result["messages"][1].content == "hello world"
    llm.ainvoke.assert_awaited_once()


@pytest.mark.anyio
async def test_graph_persists_state_in_memory_saver() -> None:
    llm = _mock_llm("reply 1")
    app = build_graph(llm)

    await app.ainvoke(
        {"messages": [HumanMessage(content="first")], "correlation_id": "c2"},
        config={"configurable": {"thread_id": "persist-test"}},
    )

    state = await app.aget_state(config={"configurable": {"thread_id": "persist-test"}})
    assert state.values is not None
    assert len(state.values["messages"]) == 2
    assert state.values["messages"][0].content == "first"
    assert state.values["messages"][1].content == "reply 1"


@pytest.mark.anyio
async def test_graph_streams_message_chunks() -> None:
    llm = _mock_llm("streamed reply")
    app = build_graph(llm)

    chunks = []
    async for chunk, metadata in app.astream(
        {"messages": [HumanMessage(content="hi")], "correlation_id": "c3"},
        config={"configurable": {"thread_id": "stream-test"}},
        stream_mode="messages",
    ):
        chunks.append((chunk, metadata))

    assert len(chunks) >= 1
    last_chunk = chunks[-1][0]
    assert last_chunk.content == "streamed reply"
    assert chunks[-1][1].get("langgraph_node") == "agent_reason"


@pytest.mark.anyio
async def test_graph_thread_isolation() -> None:
    llm = _mock_llm("response")
    app = build_graph(llm)

    await app.ainvoke(
        {"messages": [HumanMessage(content="thread a")], "correlation_id": "c4"},
        config={"configurable": {"thread_id": "thread-a"}},
    )
    await app.ainvoke(
        {"messages": [HumanMessage(content="thread b")], "correlation_id": "c5"},
        config={"configurable": {"thread_id": "thread-b"}},
    )

    state_a = await app.aget_state(config={"configurable": {"thread_id": "thread-a"}})
    state_b = await app.aget_state(config={"configurable": {"thread_id": "thread-b"}})
    assert state_a.values["messages"][0].content == "thread a"
    assert state_b.values["messages"][0].content == "thread b"
    assert len(state_a.values["messages"]) == 2
    assert len(state_b.values["messages"]) == 2


@pytest.mark.anyio
async def test_graph_react_loop_with_tools() -> None:
    call_count = 0

    def fake_ainvoke(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return AIMessage(
                content="",
                tool_calls=[{"id": "c1", "name": "list_projects", "args": {}}],
            )
        return AIMessage(content="found 1 project named demo")

    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    llm.bind_tools = MagicMock(return_value=llm)

    async def fake_tool_coroutine(**kwargs):
        return '{"items":[{"code":"demo"}],"total":1}'

    mock_tool = MagicMock()
    mock_tool.name = "list_projects"
    mock_tool.coroutine = fake_tool_coroutine

    app = build_graph(llm, tools=[mock_tool])

    result = await app.ainvoke(
        {"messages": [HumanMessage(content="what projects exist?")], "correlation_id": "c6"},
        config={"configurable": {"thread_id": "react-test"}},
    )
    assert call_count == 2
    messages = result["messages"]
    assert len(messages) == 4
    assert messages[1].tool_calls[0]["name"] == "list_projects"
    assert isinstance(messages[2], ToolMessage)
    assert "demo" in messages[2].content
    assert messages[3].content == "found 1 project named demo"
    llm.bind_tools.assert_called_once_with([mock_tool])


@pytest.mark.anyio
async def test_graph_no_tools_degrades_to_simple() -> None:
    llm = _mock_llm("simple reply")
    app = build_graph(llm, tools=None)

    result = await app.ainvoke(
        {"messages": [HumanMessage(content="hi")], "correlation_id": "c7"},
        config={"configurable": {"thread_id": "no-tools-test"}},
    )
    assert len(result["messages"]) == 2
    assert result["messages"][1].content == "simple reply"
    llm.bind_tools.assert_not_called()


@pytest.mark.anyio
async def test_graph_tool_iteration_limit() -> None:
    from app.graphs.agent import MAX_TOOL_ITERATIONS

    call_count = 0

    def fake_ainvoke(messages):
        nonlocal call_count
        call_count += 1
        return AIMessage(
            content=f"attempt {call_count}",
            tool_calls=[{"id": f"c{call_count}", "name": "list_projects", "args": {}}],
        )

    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    llm.bind_tools = MagicMock(return_value=llm)

    async def fake_tool_coroutine(**kwargs):
        return '{"items":[],"total":0}'

    mock_tool = MagicMock()
    mock_tool.name = "list_projects"
    mock_tool.coroutine = fake_tool_coroutine

    app = build_graph(llm, tools=[mock_tool])

    result = await app.ainvoke(
        {"messages": [HumanMessage(content="loop test")], "correlation_id": "c8"},
        config={"configurable": {"thread_id": "limit-test"}},
    )
    assert call_count == MAX_TOOL_ITERATIONS + 1
    assert result["tool_call_count"] == MAX_TOOL_ITERATIONS
    last_msg = result["messages"][-1]
    assert isinstance(last_msg, AIMessage)
    assert last_msg.tool_calls


@pytest.mark.anyio
async def test_graph_persists_state_in_sqlite_checkpoint(tmp_db_path) -> None:
    """State must survive graph reconstruction using AsyncSqliteCheckpoint."""
    import asyncio

    import aiosqlite

    from app.graphs.checkpoint_sqlite import AsyncSqliteCheckpoint  # noqa: E402

    conn = await aiosqlite.connect(str(tmp_db_path))
    checkpointer = AsyncSqliteCheckpoint(conn)
    await checkpointer.setup()

    llm = _mock_llm("reply 1")
    app = build_graph(llm, checkpointer=checkpointer)

    await app.ainvoke(
        {"messages": [HumanMessage(content="first")], "correlation_id": "c2"},
        config={"configurable": {"thread_id": "persist-sqlite-test"}},
    )

    # Simulate process restart: close connection, reopen, rebuild graph.
    await conn.close()
    await asyncio.sleep(0.01)
    conn2 = await aiosqlite.connect(str(tmp_db_path))
    checkpointer2 = AsyncSqliteCheckpoint(conn2)
    await checkpointer2.setup()
    app2 = build_graph(llm, checkpointer=checkpointer2)

    state = await app2.aget_state(
        config={"configurable": {"thread_id": "persist-sqlite-test"}}
    )
    assert state.values is not None
    assert len(state.values["messages"]) == 2
    assert state.values["messages"][0].content == "first"
    assert state.values["messages"][1].content == "reply 1"
    await conn2.close()
