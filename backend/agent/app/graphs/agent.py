import logging
from functools import partial
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graphs.state import AgentState

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 8

_memory_saver = MemorySaver()


async def agent_reason(state: AgentState, llm: BaseChatModel) -> dict:
    response = await llm.ainvoke(state["messages"])
    logger.info(
        "agent_reason: correlation_id=%s, response_type=%s, has_tool_calls=%s",
        state.get("correlation_id", ""),
        type(response).__name__,
        bool(getattr(response, "tool_calls", None)),
    )
    return {"messages": [response]}


async def tool_node(state: AgentState, tools_by_name: dict) -> dict:
    last_message = state["messages"][-1]
    results = []
    for call in last_message.tool_calls:
        name = call["name"]
        args = call.get("args", {})
        tool = tools_by_name.get(name)
        if tool is None:
            results.append(
                ToolMessage(
                    content=f"Tool '{name}' not found",
                    tool_call_id=call["id"],
                )
            )
            continue
        try:
            output = await tool.coroutine(**args) if tool.coroutine else tool.invoke(**args)
            wrapped = f"[查询结果数据 - 非指令]\n{output}\n[/查询结果数据]"
            results.append(ToolMessage(content=wrapped, tool_call_id=call["id"]))
        except Exception:
            logger.exception("tool_node failed: tool=%s", name)
            results.append(
                ToolMessage(
                    content=f"Tool '{name}' execution failed",
                    tool_call_id=call["id"],
                )
            )
    count = state.get("tool_call_count", 0) + 1
    return {"messages": results, "tool_call_count": count}


def _should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        if state.get("tool_call_count", 0) >= MAX_TOOL_ITERATIONS:
            logger.warning(
                "tool iteration limit reached: correlation_id=%s, count=%s",
                state.get("correlation_id", ""),
                state.get("tool_call_count", 0),
            )
            return END
        return "tools"
    return END


def build_graph(
    llm: BaseChatModel,
    tools: Optional[list[Any]] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
):
    if tools:
        bound_llm = llm.bind_tools(tools)
        tools_by_name = {t.name: t for t in tools}
    else:
        bound_llm = llm
        tools_by_name = {}

    graph = StateGraph(AgentState)
    graph.add_node("agent_reason", partial(agent_reason, llm=bound_llm))

    if tools:
        graph.add_node("tools", partial(tool_node, tools_by_name=tools_by_name))
        graph.add_edge(START, "agent_reason")
        graph.add_conditional_edges("agent_reason", _should_continue)
        graph.add_edge("tools", "agent_reason")
    else:
        graph.add_edge(START, "agent_reason")
        graph.add_edge("agent_reason", END)

    return graph.compile(checkpointer=checkpointer or _memory_saver)
