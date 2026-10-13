"""The app must start no matter which directory it is launched from."""
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not (ROOT / "public").is_dir(), reason="public/ frontend not present")
def test_static_dir_does_not_depend_on_cwd(tmp_path, monkeypatch):
    # Stub the LLM service so the test needs no API key or network.
    service = types.ModuleType("app.agent.service")
    service.engine_mode = lambda: "mock"
    service.run_turn = lambda *a, **k: {}
    monkeypatch.setitem(sys.modules, "app.agent.service", service)
    if "app.agent" not in sys.modules:
        pkg = types.ModuleType("app.agent")
        pkg.service = service
        monkeypatch.setitem(sys.modules, "app.agent", pkg)

    monkeypatch.chdir(tmp_path)  # not the project root
    sys.modules.pop("app.main", None)
    from app import main

    assert main.PUBLIC_DIR == ROOT / "public"
