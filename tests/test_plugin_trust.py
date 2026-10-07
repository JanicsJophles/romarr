"""Disabled plugins receive neither credentials nor an environment fallback."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from romarr import hub


@pytest.fixture
def secrets(monkeypatch):
    values = {
        "ROMARR_API_KEY": "test-romarr-secret",
        "PROWLARR_API_KEY": "test-prowlarr-secret",
        "QBITTORRENT_PASS": "test-qbit-secret",
        "LIBRARY_PASSWORD": "test-library-secret",
        "SOME_FUTURE_CREDENTIAL": "test-future-secret",
        "HTTPS_PROXY": "https://user:test-proxy-secret@proxy.invalid",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def test_no_environment_or_library_credentials_are_materialized(monkeypatch, secrets):
    backend = Mock(side_effect=AssertionError("Do not build plugin credentials"))
    monkeypatch.setattr(hub, "_backend_env", backend)
    with pytest.raises(RuntimeError, match="disabled") as error:
        hub._plugin_env()
    backend.assert_not_called()
    for value in secrets.values():
        assert value not in str(error.value)


def test_refusal_does_not_log_or_return_secrets(secrets, caplog):
    with caplog.at_level("DEBUG"):
        results = [hub.plugins(), hub.install("example"), hub.enable("example"), hub.disable("example")]
        with pytest.raises(RuntimeError):
            hub._plugin_env()
    visible = json.dumps(results) + caplog.text
    for value in secrets.values():
        assert value not in visible


def test_cli_refuses_without_echoing_arguments_or_building_environment(monkeypatch, secrets):
    import subprocess
    process = Mock(side_effect=AssertionError("No plugin subprocess"))
    env = Mock(side_effect=AssertionError("No plugin environment"))
    monkeypatch.setattr(subprocess, "Popen", process)
    monkeypatch.setattr(hub, "_plugin_env", env)
    result = hub._run_cli("plugin", "secret", "example", secrets["LIBRARY_PASSWORD"])
    assert result["ok"] is False
    assert result["out"] == ""
    assert result["err"] == hub.DISABLED
    assert result["code"] != 0
    process.assert_not_called()
    env.assert_not_called()


def test_security_description_matches_disabled_boundary():
    security = (Path(__file__).resolve().parents[1] / "SECURITY.md").read_text(encoding="utf-8")
    assert "execution are disabled in this companion build" in security
    assert "no environment override to re-enable plugin execution" in security
    assert "No filesystem confinement for the main service" in security
    assert hub.available() is False
    assert hub.sandbox_state()[0] is False
