import asyncio
import os
import time
import json

import pytest
import httpx

BASE_URL = os.environ.get("KULIMA_API_URL", "http://localhost:8000")
STREAM_ENDPOINT = f"{BASE_URL}/api/v1/ask/ic/stream"


@pytest.mark.asyncio
async def test_sse_streaming_end_to_end():
    payload = {"runId": "test-run", "question": "Give a short recommendation.", "history": []}
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        start = time.perf_counter()
        delta_events = []
        complete_received = False
        first_chunk_time = None

        async with client.stream("POST", STREAM_ENDPOINT, json=payload) as resp:
            assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {await resp.aread()!r}"
            buf = b""
            async for chunk in resp.aiter_bytes():
                now = time.perf_counter()
                if not first_chunk_time:
                    first_chunk_time = now - start
                buf += chunk
                # parse full SSE frames separated by \n\n
                while b"\n\n" in buf:
                    idx = buf.index(b"\n\n")
                    raw = buf[:idx].decode(errors="replace")
                    buf = buf[idx + 2 :]
                    # parse lines
                    ev = None
                    data = ""
                    for line in raw.splitlines():
                        if line.startswith("event:"):
                            ev = line[len("event:"):].strip()
                        elif line.startswith("data:"):
                            data += line[len("data:"):]
                    delta_events.append((ev, data, now - start))
                    if ev == "complete":
                        complete_received = True
            total_duration = time.perf_counter() - start

    # Assertions & report
    assert len(delta_events) > 0, "No events received"
    # expecting at least one delta and one complete
    types = [e[0] for e in delta_events]
    assert "delta" in types, f"No delta events present: {types}"
    assert "complete" in types, f"No complete event present: {types}"

    # Compute stats
    delta_chunks = [e for e in delta_events if e[0] == "delta"]
    chunk_count = len(delta_chunks)
    total_chars = sum(len(e[1]) for e in delta_chunks)
    avg_chunk_size = (total_chars / chunk_count) if chunk_count else 0

    print("SSE stream test results:")
    print(f"  events: {len(delta_events)} (deltas={chunk_count})")
    print(f"  avg chunk size (chars): {avg_chunk_size:.2f}")
    print(f"  time to first chunk (s): {first_chunk_time:.3f}")
    print(f"  total duration (s): {total_duration:.3f}")


@pytest.mark.asyncio
async def test_sse_abort_after_timeout():
    payload = {"runId": "test-run-abort", "question": "Long answer please.", "history": []}
    timeout = httpx.Timeout(None, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        start = time.perf_counter()
        async with client.stream("POST", STREAM_ENDPOINT, json=payload) as resp:
            assert resp.status_code == 200
            buf = b""
            got_any = False
            reader = resp.aiter_bytes()

            async def reader_task():
                nonlocal got_any, buf
                async for chunk in reader:
                    got_any = True
                    buf += chunk

            task = asyncio.create_task(reader_task())
            # abort after 3 seconds
            await asyncio.sleep(3.0)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            duration = time.perf_counter() - start

    print("Abort test completed, duration:", duration)
    assert duration >= 3.0, "Abort did not wait long enough"
    # we at least should have received some bytes before aborting
    assert got_any, "No bytes received before abort"
