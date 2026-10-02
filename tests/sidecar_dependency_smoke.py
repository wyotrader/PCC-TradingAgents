"""Check the installed sidecar without starting a listener or provider work."""

import asyncio
import json

import fastapi
import uvicorn
from pcc_wrapper.server import app


async def check_health():
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/health",
            "raw_path": b"/api/health",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("127.0.0.1", 80),
        },
        receive,
        send,
    )
    assert next(m for m in messages if m["type"] == "http.response.start")["status"] == 200
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    payload = json.loads(body)
    assert payload["status"] == "ok", payload
    assert payload["active_jobs"] == 0, payload
    assert isinstance(app, fastapi.FastAPI)
    assert uvicorn.Config
    print("SIDECAR_DEPENDENCY_SMOKE=PASS imports=PASS health=200 active_jobs=0")


if __name__ == "__main__":
    asyncio.run(check_health())
