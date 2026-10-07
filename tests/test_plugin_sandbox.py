"""Disabled plugin capability stays closed regardless of optional runtime support.

This fork does not run ROM Hub plugins. Installing a package, providing a working
sandbox, or retaining an old opt-out variable must not silently enable them.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import Mock

import pytest

from romarr import hub


@pytest.fixture
def installed_hub(monkeypatch):
    package = types.ModuleType("rom_hub")
    package.__path__ = []
    sandbox = types.ModuleType("rom_hub.sandbox")
    sandbox.probe = Mock(return_value=(True, "sandbox available"))
    catalog = types.ModuleType("rom_hub.catalog_sources")
    catalog.load_all = Mock()
    registry = types.ModuleType("rom_hub.registry")
    registry.Registry = Mock()
    for name, module in (("rom_hub", package), ("rom_hub.sandbox", sandbox),
                         ("rom_hub.catalog_sources", catalog), ("rom_hub.registry", registry)):
        monkeypatch.setitem(sys.modules, name, module)
    return sandbox.probe, catalog.load_all, registry.Registry


@pytest.mark.parametrize("opt_out", ["", "0", "1", "true"])
def test_old_opt_out_never_enables_plugins(monkeypatch, installed_hub, opt_out):
    monkeypatch.setenv("ROM_HUB_ALLOW_UNSANDBOXED", opt_out)
    assert hub.available() is False
    assert hub.sandbox_state() == (False, hub.DISABLED)
    with pytest.raises(RuntimeError, match="disabled"):
        hub._import()
    for call in installed_hub:
        call.assert_not_called()


def test_catalog_does_not_load_even_with_installed_package(installed_hub):
    result = hub.plugins()
    assert result["items"] == []
    assert "disabled" in result["error"].lower()
    for call in installed_hub:
        call.assert_not_called()


@pytest.mark.parametrize("action", ["install", "enable", "disable"])
def test_actions_do_not_start_processes_or_touch_registry(monkeypatch, installed_hub, action):
    import subprocess
    process = Mock(side_effect=AssertionError("Plugin process must not start"))
    monkeypatch.setattr(subprocess, "Popen", process)
    result = getattr(hub, action)("example-plugin")
    assert result["ok"] is False
    assert result["out"] == ""
    assert result["code"] != 0
    assert "disabled" in result["err"].lower()
    process.assert_not_called()
    for call in installed_hub:
        call.assert_not_called()


def test_working_sandbox_does_not_enable_environment(monkeypatch):
    monkeypatch.setattr(hub, "sandbox_state", lambda: (True, "available"))
    with pytest.raises(RuntimeError, match="disabled"):
        hub._plugin_env()


def test_broken_optional_probe_is_not_called(installed_hub):
    installed_hub[0].side_effect = RuntimeError("optional probe broke")
    assert hub.sandbox_state() == (False, hub.DISABLED)
    installed_hub[0].assert_not_called()
