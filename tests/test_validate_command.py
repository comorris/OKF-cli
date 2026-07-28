from __future__ import annotations

import json
import os
from pathlib import Path

from okf_cli.bundles import init_bundle
from okf_cli.cli import main
from okf_cli.documents import ConceptDocument, render_concept
from okf_cli.filesystem import FileSystem


def make_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "project" / "okf"
    init_bundle(
        bundle,
        title="Project",
        description="Project knowledge.",
        catalog=None,
        update_gitignore=False,
        fs=FileSystem(),
    )
    return bundle


def test_validate_conformant_bundle_exits_zero(tmp_path: Path, capsys: object) -> None:
    bundle = make_bundle(tmp_path)

    code = main(["--format", "json", "validate", "--bundle", str(bundle)])

    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert code == 0
    assert payload["ok"] is True
    assert payload["data"]["findings"] == []


def test_validate_invalid_bundle_exits_five(tmp_path: Path, capsys: object) -> None:
    bundle = make_bundle(tmp_path)
    (bundle / "broken.md").write_text("# broken\n", encoding="utf-8")

    code = main(["--format", "json", "validate", "--bundle", str(bundle)])

    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert code == 5
    assert payload["ok"] is False
    assert payload["data"]["findings"]


def test_validate_warning_only_bundle_exits_zero(tmp_path: Path, capsys: object) -> None:
    bundle = make_bundle(tmp_path)
    (bundle / "warning.md").write_text(
        render_concept(ConceptDocument({"type": "Reference"}, "See [missing](missing.md).\n")),
        encoding="utf-8",
    )

    code = main(["--format", "json", "validate", "--bundle", str(bundle)])

    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert code == 0
    assert payload["ok"] is True
    assert payload["data"]["findings"][0]["severity"] == "warning"


def test_validate_json_contains_sorted_findings(tmp_path: Path, capsys: object) -> None:
    bundle = make_bundle(tmp_path)
    (bundle / "z-broken.md").write_text("not markdown", encoding="utf-8")
    (bundle / "a-broken.md").write_text("also not markdown", encoding="utf-8")

    main(["--format", "json", "validate", "--bundle", str(bundle)])

    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    paths = [finding["path"] for finding in payload["data"]["findings"]]
    assert paths == sorted(paths)


def test_validate_missing_bundle_is_path_error(tmp_path: Path, capsys: object) -> None:
    code = main(["validate", "--bundle", str(tmp_path / "missing")])

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert code == 3
    assert "does not exist" in captured.err


def test_index_rebuild_command_rebuilds_all_indexes(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    (bundle / "architecture").mkdir()
    (bundle / "architecture" / "concept.md").write_text(
        render_concept(ConceptDocument({"type": "Reference"}, "")),
        encoding="utf-8",
    )
    (bundle / "architecture" / "index.md").unlink(missing_ok=True)

    code = main(["index", "rebuild", "--bundle", str(bundle)])

    assert code == 0
    assert (bundle / "index.md").exists()
    assert (bundle / "architecture" / "index.md").exists()


def test_config_show_text_and_json_include_catalog_source(
    tmp_path: Path, monkeypatch: object, capsys: object
) -> None:
    catalog = tmp_path / "catalog"
    monkeypatch.setenv("OKF_CATALOG_ROOT", str(catalog))  # type: ignore[attr-defined]

    code = main(["config", "show"])
    text = capsys.readouterr().out  # type: ignore[attr-defined]
    assert code == 0
    assert "source: environment" in text

    code = main(["--format", "json", "config", "show"])
    payload = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert code == 0
    assert payload["data"] == {"catalog_root": str(catalog), "source": "environment"}
