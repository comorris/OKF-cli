from __future__ import annotations

from pathlib import Path

from okf_cli.config import config_report, resolve_catalog


def write_config(home: Path, value: Path) -> None:
    config_path = home / ".config" / "okf" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(f'catalog_root = "{value}"\n', encoding="utf-8")


def test_catalog_cli_option_wins_over_everything(tmp_path: Path) -> None:
    home = tmp_path / "home"
    env_path = tmp_path / "environment"
    cli_path = tmp_path / "cli"
    home.mkdir()
    write_config(home, tmp_path / "config")

    resolved = resolve_catalog(
        cli_path,
        {"OKF_CATALOG_ROOT": str(env_path)},
        home,
    )

    assert resolved.path == cli_path
    assert resolved.source == "cli"


def test_catalog_environment_wins_over_config_file(tmp_path: Path) -> None:
    home = tmp_path / "home"
    env_path = tmp_path / "environment"
    home.mkdir()
    write_config(home, tmp_path / "config")

    resolved = resolve_catalog(
        None,
        {"OKF_CATALOG_ROOT": str(env_path)},
        home,
    )

    assert resolved.path == env_path
    assert resolved.source == "environment"


def test_catalog_uses_xdg_config_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    configured = tmp_path / "configured"
    home.mkdir()
    config_path = xdg / "okf" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(f'catalog_root = "{configured}"\n', encoding="utf-8")

    resolved = resolve_catalog(None, {"XDG_CONFIG_HOME": str(xdg)}, home)

    assert resolved.path == configured
    assert resolved.source == "config"


def test_catalog_defaults_to_home_dot_config(tmp_path: Path) -> None:
    home = tmp_path / "home"
    configured = tmp_path / "configured"
    home.mkdir()
    write_config(home, configured)

    resolved = resolve_catalog(None, {}, home)

    assert resolved.path == configured
    assert resolved.source == "config"


def test_config_show_reports_value_and_source(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"

    report = config_report(
        None,
        {"OKF_CATALOG_ROOT": str(catalog)},
        tmp_path / "home",
    )

    assert report == {"catalog_root": str(catalog), "source": "environment"}
