from unittest.mock import patch
from romarr import hub


def test_companion_never_executes_or_enables_plugins():
    with patch('subprocess.run') as run:
        assert not hub.available()
        assert not hub.sandbox_state()[0]
        assert hub.plugins()['items'] == []
        for action in (hub.install, hub.enable, hub.disable):
            assert action('example')['ok'] is False
        run.assert_not_called()


def test_container_preserves_upstream_license_and_notice():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert "COPY LICENSE NOTICE /app/" in (root / "Dockerfile").read_text()
    ignored = (root / ".dockerignore").read_text().splitlines()
    assert "LICENSE" not in ignored and "NOTICE" not in ignored


def test_runtime_removes_package_installers():
    from pathlib import Path
    body = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    runtime = body.rsplit("\nFROM ", 1)[-1]
    assert "python -m pip uninstall -y pip" in runtime
    assert "'ensurepip'" in runtime
