"""Starts the app the way Vercel runs it and checks that the pages answer.

Vercel installs the packages with uv from pyproject.toml into a vendor folder (/var/task/_vendor, not site-packages)
and serves asgi.py. The tests job installs from requirements.txt into site-packages, so it cannot see problems that
only show up on Vercel (a package missing from pyproject.toml, Streamlit switching to development mode and dropping
its frontend). The vercel-build job in .github/workflows/tests.yml installs the packages the same way and runs this.

Run from the repository root:   PYTHONPATH=_vendor python scripts/check_vercel_build.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(1, str(Path(__file__).resolve().parents[1]))  # the repo root, after the vendor folder

import streamlit  # noqa: E402

if "site-packages" in streamlit.__file__:
    sys.exit(f"Streamlit was imported from {streamlit.__file__}; put the vendor folder first on PYTHONPATH.")

from starlette.testclient import TestClient  # noqa: E402

import asgi  # noqa: E402

index_html = (Path(streamlit.__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
chunk = "/" + re.search(r'src="\./(static/js/[^"]+\.js)"', index_html).group(1)

# path -> text the response must contain
CHECKS = {
    "/": 'id="root"',
    "/hotspots": 'id="root"',
    chunk: "",
    "/favicon.png": "",
    "/_stcore/health": "ok",
    "/api/v1/countries": '"index_year"',
}

failed = []
with TestClient(asgi.app) as client:
    for path, want in CHECKS.items():
        response = client.get(path)
        ok = response.status_code == 200 and want in response.text
        print(f"{'ok  ' if ok else 'FAIL'} {response.status_code} {path}")
        if not ok:
            failed.append(path)

if failed:
    sys.exit(f"{len(failed)} of {len(CHECKS)} checks failed: the app would break on Vercel.")
print("The app answers as it would on Vercel.")
