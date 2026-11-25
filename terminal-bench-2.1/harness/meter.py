"""Host-side metering proxy for the codeaf senior-dev Harness Leaderboard run.

Containers call http://<gateway>:18788/t/<trial>/api/v1/... with a dummy key.
This proxy:
  * swaps in the real OpenRouter key (the key never enters a task container),
  * pins every call for deepseek/deepseek-v4.1-flash to the leaderboard's
    reference provider (DeepInfra, fp8) with no fallbacks,
  * enforces reasoning effort (EFFORT env, default "high") on every model call,
  * records one JSON line per model call (trial, model, provider, usage, cost,
    latency, the effort the harness asked for) to calls.jsonl.

Cost comes from OpenRouter's own usage accounting on each response, so it is
measured outside the harness, like the leaderboard's meter.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, TCPConnector, web

UPSTREAM = "https://openrouter.ai"
MODEL = "deepseek/deepseek-v4.1-flash"
PROVIDER = {"only": ["deepinfra"], "quantizations": ["fp8"], "allow_fallbacks": False}
EFFORT = os.environ.get("EFFORT", "high")
KEY = Path(os.environ["OR_KEY_FILE"]).read_text().strip()
LOG = Path(os.environ.get("METER_LOG", "calls.jsonl"))
PORT = int(os.environ.get("METER_PORT", "18788"))

HOP = {"host", "content-length", "transfer-encoding", "connection", "authorization", "accept-encoding"}


def _log(row: dict) -> None:
    with LOG.open("a") as f:
        f.write(json.dumps(row) + "\n")


def _rewrite(body: dict, row: dict) -> dict:
    model = str(body.get("model", ""))
    row["model"] = model
    row["effort_asked"] = (body.get("reasoning") or {}).get("effort", body.get("reasoning_effort"))
    row["provider_asked"] = body.get("provider")
    if model.removeprefix("openrouter/") == MODEL:
        body["provider"] = PROVIDER
        reasoning = dict(body.get("reasoning") or {})
        reasoning.pop("max_tokens", None)
        reasoning["effort"] = EFFORT
        body["reasoning"] = reasoning
        body.pop("reasoning_effort", None)
        row["pinned"] = True
    else:
        row["pinned"] = False  # flagged: a role used a model other than the run's model
    if body.get("stream"):
        opts = dict(body.get("stream_options") or {})
        opts["include_usage"] = True
        body["stream_options"] = opts
    body["usage"] = {"include": True}
    return body


def _take_usage(obj: dict, row: dict) -> None:
    if obj.get("provider"):
        row["provider"] = obj["provider"]
    if obj.get("usage"):
        u = obj["usage"]
        row["usage"] = u
        row["cost_usd"] = u.get("cost")


async def handle(request: web.Request) -> web.StreamResponse:
    trial = request.match_info["trial"]
    rest = request.match_info["rest"]
    url = f"{UPSTREAM}/{rest}"
    if request.query_string:
        url += "?" + request.query_string
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP}
    headers["Authorization"] = f"Bearer {KEY}"
    raw = await request.read()
    row: dict = {"ts": time.time(), "trial": trial, "path": rest}
    is_model_call = rest.endswith("chat/completions") and request.method == "POST"
    if is_model_call and raw:
        body = _rewrite(json.loads(raw), row)
        raw = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    t0 = time.monotonic()
    session: ClientSession = request.app["session"]
    try:
        async with session.request(request.method, url, data=raw or None, headers=headers) as up:
            resp = web.StreamResponse(status=up.status)
            for k, v in up.headers.items():
                if k.lower() not in HOP and k.lower() != "content-encoding":
                    resp.headers[k] = v
            await resp.prepare(request)
            buf = b""
            first = None
            async for chunk in up.content.iter_any():
                if first is None:
                    first = time.monotonic() - t0
                await resp.write(chunk)
                if is_model_call:
                    buf += chunk
            await resp.write_eof()
            if is_model_call:
                row["status"] = up.status
                row["ttfb_s"] = round(first or 0.0, 3)
                row["latency_s"] = round(time.monotonic() - t0, 3)
                text = buf.decode("utf-8", "replace")
                if text.lstrip().startswith("{"):
                    try:
                        _take_usage(json.loads(text), row)
                    except json.JSONDecodeError:
                        pass
                    if up.status >= 400:
                        row["error"] = text[:800]
                else:
                    for line in text.splitlines():
                        if line.startswith("data: ") and line[6:].strip() not in ("", "[DONE]"):
                            try:
                                _take_usage(json.loads(line[6:]), row)
                            except json.JSONDecodeError:
                                continue
                _log(row)
            return resp
    except Exception as exc:  # upstream failure: tell the harness, record it
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["latency_s"] = round(time.monotonic() - t0, 3)
        _log(row)
        return web.json_response({"error": {"message": row["error"], "code": 502}}, status=502)


async def _startup(app: web.Application) -> None:
    app["session"] = ClientSession(timeout=ClientTimeout(total=None, sock_read=600), connector=TCPConnector(limit=0))


async def _cleanup(app: web.Application) -> None:
    await app["session"].close()


def main() -> None:
    app = web.Application(client_max_size=256 * 1024 * 1024)
    app.on_startup.append(_startup)
    app.on_cleanup.append(_cleanup)
    app.router.add_route("*", "/t/{trial}/{rest:.*}", handle)
    app.router.add_get("/healthz", lambda r: web.Response(text="ok"))
    print(f"meter on :{PORT} effort={EFFORT} provider={PROVIDER} log={LOG}", file=sys.stderr)
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
