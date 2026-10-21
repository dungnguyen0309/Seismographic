"""Shared test setup.

The 3D globe registers itself with the Streamlit runtime when prm.globe is first imported. Running the app once
before any test imports the UI modules makes sure that happens inside the test app's runtime, whatever the order.
"""

import os
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PRM_RAISE_ERRORS"] = "1"  # errors fail the tests instead of being shown as a polite note
os.environ["STREAMLIT_CLIENT_SHOW_ERROR_DETAILS"] = "full"  # visitors see only the error type; tests need everything


@pytest.fixture(scope="session", autouse=True)
def app() -> AppTest:
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=300)
    at.run()
    return at
