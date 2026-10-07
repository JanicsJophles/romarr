"""Disabled ROM Hub boundary for the companion fork.

The upstream bridge installs and executes third-party plugin code. That feature
is outside this build's supported scope. Preserve its response shape so the UI
can explain the limitation, without importing plugins, constructing credential
environments, changing process environment, or spawning a subprocess.
"""
from pathlib import Path

DISABLED = "ROM Hub plugin execution is disabled in this companion build."
HOME = Path("/config/rom-hub")
_ENV_PASSTHROUGH = ()


def _backend_env() -> dict:
    return {}


def _import():
    raise RuntimeError(DISABLED)


def _plugin_env() -> dict:
    raise RuntimeError(DISABLED)


def available() -> bool:
    return False


def sandbox_state() -> tuple[bool, str]:
    return False, DISABLED


def plugins() -> dict:
    return {"items": [], "installed_count": 0, "total": 0, "error": DISABLED}


def _run_cli(*args, timeout=180):
    return {"ok": False, "out": "", "err": DISABLED, "code": -1}


def _set_enabled(slug: str, on: bool) -> dict:
    return _run_cli()


def install(slug: str) -> dict:
    return _run_cli()


def enable(slug: str) -> dict:
    return _run_cli()


def disable(slug: str) -> dict:
    return _run_cli()


def uninstall(slug: str) -> dict:
    return _run_cli()
