"""Serve web/ locally with the rewrites, redirects and headers from web/vercel.json."""
import argparse
import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, unquote


def _source(pattern):
    """Vercel source pattern -> compiled regex (supports :param and raw regex groups)."""
    return re.compile("^" + re.sub(r":(\w+)", r"(?P<\1>[^/]+)", pattern) + "$")


def _subst(dest, m):
    return re.sub(r":(\w+)", lambda g: m.groupdict().get(g.group(1), g.group(0)), dest)


def _cond(c, query):
    vals = query.get(c["key"], [])
    return any(re.search(c["value"], v) for v in vals) if "value" in c else bool(vals)


def _has_ok(rule, query):
    """Vercel semantics: every `has` condition holds and no `missing` condition does."""
    q = lambda k: [c for c in rule.get(k, []) if c["type"] == "query"]
    return all(_cond(c, query) for c in q("has")) and not any(_cond(c, query) for c in q("missing"))


def _exact_case(root, p):
    """Vercel's file system is case-sensitive; Windows is not. Every component must match on-disk case."""
    cur = root
    for part in p.relative_to(root).parts:
        if part not in os.listdir(cur):
            return False
        cur = cur / part
    return True


def make_handler(root):
    root = Path(root).resolve()
    cfg = json.loads((root / "vercel.json").read_text(encoding="utf-8"))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body=b"", ctype="text/plain", extra=()):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _file(self, rel):
            try:
                raw = root / rel.lstrip("/")  # resolve() would normalise the case on Windows, so check the raw path
                p = raw.resolve()
                if root not in p.parents:
                    return None
                h = Path(str(raw) + ".html")
                if cfg.get("cleanUrls") and not p.is_file() and h.is_file():
                    raw = h
                return raw if raw.is_file() and _exact_case(root, raw) else None
            except (ValueError, OSError):  # NUL bytes, over-long names
                return None

        def do_GET(self):
            u = urlsplit(self.path)
            path, query = unquote(u.path), parse_qs(u.query, keep_blank_values=True)
            if cfg.get("cleanUrls"):  # Vercel canonicalises /x.html and /x/ to /x, /index.html to /
                clean = path[:-len("index.html")] if path.endswith("/index.html") else re.sub(r"\.html$", "", path)
                if len(clean) > 1:
                    clean = clean.rstrip("/")
                if clean != path:
                    return self._send(308, extra=[("Location", (clean or "/") + ("?" + u.query if u.query else ""))])
            for r in cfg.get("redirects", []):
                m = _source(r["source"]).match(path)
                if m:
                    code = 308 if r.get("permanent") else 307
                    return self._send(code, extra=[("Location", _subst(r["destination"], m))])
            target = self._file(path.rstrip("/") + "/index.html" if path.endswith("/") else path)
            if target is None:
                for r in cfg.get("rewrites", []):
                    m = _source(r["source"]).match(path)
                    if m and _has_ok(r, query):
                        target = self._file(_subst(r["destination"], m))
                        break
            if target is None:
                page = root / "404.html"
                return self._send(404, page.read_bytes() if page.is_file() else b"Not found", "text/html; charset=utf-8")
            extra = [(h["key"], h["value"]) for rule in cfg.get("headers", [])
                     if _source(rule["source"]).match(path) for h in rule["headers"] if h["key"].lower() != "cache-control"]  # dev server never caches
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith(("json", "javascript")):
                ctype += "; charset=utf-8"
            self._send(200, target.read_bytes(), ctype, extra)

        do_HEAD = do_GET

    return Handler


class _Server(ThreadingHTTPServer):
    request_queue_size = 128  # the default 5 refuses connections when a page asks for ~30 files at once (Windows)
    def handle_error(self, request, client_address):  # browsers drop connections mid-request; not worth a traceback
        pass


def make_server(root, port=8600):
    return _Server(("127.0.0.1", port), make_handler(root))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8600)
    ap.add_argument("--root", default="web")
    a = ap.parse_args()
    print(f"Serving {a.root} on http://localhost:{a.port}")
    make_server(a.root, a.port).serve_forever()
