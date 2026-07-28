from __future__ import annotations

import json

import pytest

from okf_cli import cli
from okf_cli.cli import main
from okf_cli.errors import ConflictError


def test_version_from_console_command(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--version"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == "okf-cli 0.1.0"
    assert captured.err == ""


def test_missing_command_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([])

    captured = capsys.readouterr()
    assert code == 2
    assert "usage:" in captured.err.lower()
    assert "traceback" not in captured.err.lower()


def test_json_success_envelope(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--format", "json", "config", "show"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert set(payload) == {"ok", "command", "data", "warnings", "errors"}
    assert payload["ok"] is True
    assert payload["command"] == "config.show"
    assert payload["warnings"] == []
    assert payload["errors"] == []
    assert captured.err == ""


def test_domain_error_uses_stable_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raise_conflict(_args: object) -> object:
        raise ConflictError("already exists")

    monkeypatch.setattr(cli, "dispatch_command", raise_conflict)

    code = main(["config", "show"])

    captured = capsys.readouterr()
    assert code == 4
    assert "already exists" in captured.err
    assert "traceback" not in captured.err.lower()


def test_unexpected_error_returns_operational_exit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raise_unexpected(_args: object) -> object:
        raise RuntimeError("implementation detail")

    monkeypatch.setattr(cli, "dispatch_command", raise_unexpected)

    code = main(["config", "show"])

    captured = capsys.readouterr()
    assert code == 6
    assert "unexpected error" in captured.err.lower()
    assert "implementation detail" not in captured.err
    assert "traceback" not in captured.err.lower()
