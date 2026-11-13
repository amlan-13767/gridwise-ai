"""Short-lived per-user response cache for read-only analytics endpoints.
Why: on Render's free tier (a fraction of a CPU) pandas aggregations take seconds. The data only changes on writes, so
identical GETs are served from memory. Safety: keyed by the caller's bearer token (no cross-user leakage); invalid/expired
tokens bypass the cache and reach the normal 401 path; any successful POST/PATCH/DELETE clears everything; bounded size + TTL."""
import time
from collections import OrderedDict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from .security import decode_token

TTL_SECONDS = 180
MAX_ENTRIES = 80
MAX_BODY_BYTES = 400_000
CACHEABLE = ("/api/energy/", "/api/cooling/", "/api/reports/", "/api/renewable/", "/api/forecast", "/api/anomalies", "/api/recommendations", "/api/optimization/runs")
SKIP_HEADERS = {"content-length", "transfer-encoding", "connection"}

_store: "OrderedDict[tuple, tuple]" = OrderedDict()


def clear():
    _store.clear()


class ResponseCache(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            resp = await call_next(request)
            if resp.status_code < 400:
                clear()  # data may have changed
            return resp
        auth = request.headers.get("authorization", "")
        if request.method != "GET" or not path.startswith(CACHEABLE) or not auth.lower().startswith("bearer ") or not decode_token(auth.split(" ", 1)[1]):
            return await call_next(request)
        key = (path, request.url.query, auth)
        hit = _store.get(key)
        if hit and time.time() - hit[0] < TTL_SECONDS:
            _store.move_to_end(key)
            return Response(hit[1], status_code=200, headers={**hit[2], "X-Cache": "HIT"})
        resp = await call_next(request)
        if resp.status_code != 200:
            return resp
        body = b"".join([chunk async for chunk in resp.body_iterator])
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in SKIP_HEADERS}  # includes content-type / content-disposition
        if len(body) <= MAX_BODY_BYTES:
            _store[key] = (time.time(), body, headers)
            while len(_store) > MAX_ENTRIES:
                _store.popitem(last=False)
        return Response(body, status_code=200, headers={**headers, "X-Cache": "MISS"})
