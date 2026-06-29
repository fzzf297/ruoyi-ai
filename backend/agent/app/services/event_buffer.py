import threading
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Optional

_event_buffers: dict[str, list[tuple[str, str]]] = defaultdict(list)
_lock = threading.Lock()

MAX_BUFFER_SIZE = 200


def store_event(session_id: str, event_id: str, sse_line: str) -> None:
    with _lock:
        buf = _event_buffers[session_id]
        buf.append((event_id, sse_line))
        if len(buf) > MAX_BUFFER_SIZE:
            _event_buffers[session_id] = buf[-MAX_BUFFER_SIZE:]


def get_events_after(session_id: str, last_event_id: str) -> list[str]:
    with _lock:
        buf = _event_buffers.get(session_id, [])
    found = False
    result = []
    for eid, line in buf:
        if found:
            result.append(line)
        if eid == last_event_id:
            found = True
    if not found:
        return [line for _, line in buf]
    return result


def clear_session(session_id: str) -> None:
    with _lock:
        _event_buffers.pop(session_id, None)


async def replay_then_stream(
    session_id: str,
    last_event_id: Optional[str],
    stream: AsyncIterator[str],
) -> AsyncIterator[str]:
    if last_event_id:
        missed = get_events_after(session_id, last_event_id)
        for line in missed:
            yield line
    async for sse_line in stream:
        yield sse_line
