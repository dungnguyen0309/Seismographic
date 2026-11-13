"""Seismographic as an ASGI app, for hosts that run Python web apps rather than `streamlit run` (e.g. Vercel).
It also serves the read-only JSON API under /api/v1 (prm/api.py).

Run it locally with:   uvicorn asgi:app --port 8501
"""

from pathlib import Path

import streamlit as st
from starlette.middleware import Middleware

from prm import api


class EdgeCacheFrontend:
    """Lets Vercel's CDN keep the files Streamlit marks immutable (its content-hashed /static/* bundles and
    favicon.png), so the ~60 chunks of a page load stop running the function. Vercel's CDN stores a function
    response only with s-maxage or a CDN cache header, and Streamlit sends max-age only. index.html, manifest.json
    and the fallback for unknown paths are no-cache, so they never match."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("GET", "HEAD"):
            await self.app(scope, receive, send)
            return

        async def send_with_edge_cache(message):
            if message["type"] == "http.response.start" and message["status"] == 200:
                headers = message.get("headers") or []
                if any(k.lower() == b"cache-control" and b"immutable" in v for k, v in headers):
                    # Vercel reads and strips this header; browsers keep Streamlit's own Cache-Control.
                    message["headers"] = [*headers, (b"vercel-cdn-cache-control", b"max-age=31536000")]
            await send(message)

        await self.app(scope, receive, send_with_edge_cache)


app = st.App(
    Path(__file__).resolve().parent / "streamlit_app.py",
    routes=api.routes(),
    middleware=[Middleware(EdgeCacheFrontend)],
)
