"""Simple load test for the agent API.

Run against a local server:

    AGENT_API_URL=http://localhost:8001 python3 scripts/load_test.py

Set AGENT_LLM_API_KEY to also exercise the chat endpoint; otherwise only
session creation and health checks are load-tested.
"""

import asyncio
import os
import time

import httpx

BASE_URL = os.getenv("AGENT_API_URL", "http://localhost:8001").rstrip("/")
CONCURRENCY = int(os.getenv("LOAD_TEST_CONCURRENCY", "10"))
REQUESTS = int(os.getenv("LOAD_TEST_REQUESTS", "50"))
CHAT_REQUESTS = int(os.getenv("LOAD_TEST_CHAT_REQUESTS", "10"))
LLM_API_KEY = os.getenv("AGENT_LLM_API_KEY", "")
ENABLE_CHAT = LLM_API_KEY and LLM_API_KEY != "change-me"


async def health_check(client: httpx.AsyncClient) -> tuple[int, float]:
    start = time.time()
    resp = await client.get(f"{BASE_URL}/health")
    return resp.status_code, time.time() - start


async def create_session(client: httpx.AsyncClient) -> tuple[str, int, float]:
    start = time.time()
    resp = await client.post(
        f"{BASE_URL}/api/agent/sessions",
        json={"userLabel": "load-test"},
    )
    elapsed = time.time() - start
    if resp.status_code != 201:
        return "", resp.status_code, elapsed
    return resp.json()["sessionId"], resp.status_code, elapsed


async def chat_once(client: httpx.AsyncClient, session_id: str) -> tuple[int, float]:
    start = time.time()
    resp = await client.post(
        f"{BASE_URL}/api/agent/sessions/{session_id}/messages",
        json={"content": "列出所有项目"},
        timeout=60,
    )
    elapsed = time.time() - start
    return resp.status_code, elapsed


async def _bounded(
    sem: asyncio.Semaphore,
    coro,
    results: list,
) -> None:
    async with sem:
        results.append(await coro)


async def _run_health(client: httpx.AsyncClient) -> dict:
    results = []
    sem = asyncio.Semaphore(CONCURRENCY)
    start = time.time()
    await asyncio.gather(
        *[_bounded(sem, health_check(client), results) for _ in range(REQUESTS)]
    )
    elapsed = time.time() - start
    ok = sum(1 for s, _ in results if s == 200)
    return {
        "endpoint": "GET /health",
        "total": REQUESTS,
        "ok": ok,
        "elapsed": elapsed,
        "rps": REQUESTS / elapsed if elapsed > 0 else 0,
        "avg_latency_ms": sum(d for _, d in results) / len(results) * 1000 if results else 0,
    }


async def _run_sessions(client: httpx.AsyncClient) -> dict:
    results = []
    sem = asyncio.Semaphore(CONCURRENCY)
    start = time.time()
    await asyncio.gather(
        *[_bounded(sem, create_session(client), results) for _ in range(REQUESTS)]
    )
    elapsed = time.time() - start
    ok = sum(1 for _, s, _ in results if s == 201)
    return {
        "endpoint": "POST /api/agent/sessions",
        "total": REQUESTS,
        "ok": ok,
        "elapsed": elapsed,
        "rps": REQUESTS / elapsed if elapsed > 0 else 0,
        "avg_latency_ms": sum(d for _, _, d in results) / len(results) * 1000 if results else 0,
    }


async def _run_chat(client: httpx.AsyncClient) -> dict:
    sessions = []
    for _ in range(CHAT_REQUESTS):
        session_id, status, _ = await create_session(client)
        if status == 201:
            sessions.append(session_id)

    results = []
    sem = asyncio.Semaphore(min(CONCURRENCY, len(sessions) or 1))
    start = time.time()
    await asyncio.gather(
        *[_bounded(sem, chat_once(client, sid), results) for sid in sessions]
    )
    elapsed = time.time() - start
    ok = sum(1 for s, _ in results if s == 200)
    return {
        "endpoint": "POST /api/agent/sessions/{id}/messages",
        "total": len(sessions),
        "ok": ok,
        "elapsed": elapsed,
        "rps": len(sessions) / elapsed if elapsed > 0 else 0,
        "avg_latency_ms": sum(d for _, d in results) / len(results) * 1000 if results else 0,
    }


async def main() -> None:
    print(f"target={BASE_URL} concurrency={CONCURRENCY}")
    async with httpx.AsyncClient() as client:
        health_report = await _run_health(client)
        session_report = await _run_sessions(client)
        chat_report = await _run_chat(client) if ENABLE_CHAT else None

    for report in [health_report, session_report, chat_report]:
        if report is None:
            continue
        print(
            f"{report['endpoint']}: total={report['total']} ok={report['ok']} "
            f"elapsed={report['elapsed']:.2f}s rps={report['rps']:.2f} "
            f"avg_latency={report['avg_latency_ms']:.1f}ms"
        )

    if not ENABLE_CHAT:
        print("\nNote: chat endpoint skipped; set AGENT_LLM_API_KEY to exercise it.")


if __name__ == "__main__":
    asyncio.run(main())
