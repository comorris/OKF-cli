from __future__ import annotations

import json
from pathlib import Path

import pytest

from okf_cli import __version__, cli
from okf_cli.catalog import DEFAULT_ACTOR
from okf_cli.cli import main
from okf_cli.errors import ConflictError


def test_version_from_console_command(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--version"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == "okf-cli 0.2.0"
    assert captured.err == ""


def test_default_actor_tracks_package_version() -> None:
    assert DEFAULT_ACTOR == f"okf-cli/{__version__}"


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


def test_help_documents_create_provenance_options(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["concept", "create", "--help"])

    captured = capsys.readouterr()
    assert code == 0
    assert "--resource" in captured.out
    assert "--sources-file" in captured.out


def test_help_documents_concept_update_without_force(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["concept", "update", "--help"])

    captured = capsys.readouterr()
    assert code == 0
    assert "--sources-file" in captured.out
    assert "--force" not in captured.out


def test_unregister_cli_requires_bundle_and_reports_preview_and_noop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from okf_cli.catalog import init_catalog, register_bundle
    from okf_cli.bundles import init_bundle
    from okf_cli.filesystem import FileSystem

    catalog = tmp_path / "catalog"
    bundle = tmp_path / "project" / "okf"
    init_catalog(catalog, title="Projects", description="Catalog.", fs=FileSystem())
    init_bundle(bundle, title="Project", description="Knowledge.", catalog=None,
                update_gitignore=False, fs=FileSystem())
    register_bundle(catalog, bundle, fs=FileSystem())
    args = ["--format", "json", "bundle", "unregister", "--bundle", str(bundle), "--catalog", str(catalog)]
    assert main(args + ["--dry-run"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["command"] == "bundle.unregister"
    assert preview["data"]["unregistered"] is True
    assert any(c["operation"] == "delete" for c in preview["data"]["changes"])
    assert (catalog / "bundles" / "project.md").exists()

    assert main(args) == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["data"] == preview["data"]
    assert not (catalog / "bundles" / "project.md").exists()
    assert main(args) == 0
    noop = json.loads(capsys.readouterr().out)
    assert noop["data"]["unregistered"] is False
    assert "changes" not in noop["data"]

    assert main(["--format", "json", "bundle", "unregister", "--catalog", str(catalog)]) == 2
    capsys.readouterr()
    assert main(["--format", "json", "bundle", "unregister", "--bundle", str(bundle),
                 "--catalog", str(tmp_path / "missing")]) == 3
    error = json.loads(capsys.readouterr().err)
    assert error["command"] == "bundle.unregister"


def test_invalid_sources_file_returns_configuration_exit_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sources = tmp_path / "sources.yaml"
    sources.write_text("resource: README.md\n", encoding="utf-8")

    code = main(
        [
            "--format",
            "json",
            "concept",
            "create",
            "concept",
            "--bundle",
            str(tmp_path / "bundle"),
            "--type",
            "Reference",
            "--sources-file",
            str(sources),
        ]
    )
    payload = json.loads(capsys.readouterr().err)

    assert code == 3
    assert payload["ok"] is False
    assert payload["errors"]


def test_update_missing_concept_returns_configuration_exit_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from okf_cli.bundles import init_bundle
    from okf_cli.filesystem import FileSystem

    bundle = tmp_path / "bundle"
    init_bundle(
        bundle,
        title="Project",
        description="Project knowledge.",
        catalog=None,
        update_gitignore=False,
        fs=FileSystem(),
    )

    code = main(
        [
            "--format",
            "json",
            "concept",
            "update",
            "missing",
            "--bundle",
            str(bundle),
        ]
    )
    payload = json.loads(capsys.readouterr().err)

    assert code == 3
    assert payload["command"] == "concept.update"
    assert payload["ok"] is False


def test_json_error_envelope_remains_stable_for_update(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "--format",
            "json",
            "concept",
            "update",
            "missing",
            "--bundle",
            str(tmp_path / "missing-bundle"),
        ]
    )
    payload = json.loads(capsys.readouterr().err)

    assert code == 3
    assert set(payload) == {"ok", "command", "data", "warnings", "errors"}
    assert payload["command"] == "concept.update"
    assert payload["data"] == {}
    assert payload["warnings"] == []
    assert len(payload["errors"]) == 1


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
