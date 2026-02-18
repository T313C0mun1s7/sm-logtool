from __future__ import annotations

from pathlib import Path
import plistlib

from sm_logtool.ui.theme_importer import default_theme_store_dir
from sm_logtool.ui.theme_importer import load_saved_themes
from sm_logtool.ui.theme_importer import discover_theme_files
from sm_logtool.ui.theme_importer import load_imported_themes
from sm_logtool.ui.theme_importer import normalize_mapping_profile
from sm_logtool.ui.theme_importer import save_converted_theme


def _iterm_color(red: float, green: float, blue: float) -> dict[str, float]:
    return {
        "Red Component": red,
        "Green Component": green,
        "Blue Component": blue,
    }


def test_discover_theme_files_finds_supported_suffixes(tmp_path: Path) -> None:
    themes = tmp_path / "themes"
    themes.mkdir()
    first = themes / "one.colortheme"
    second = themes / "two.itermcolors"
    ignored = themes / "skip.txt"
    first.write_text("background=#000000\n", encoding="utf-8")
    second.write_bytes(b"{}")
    ignored.write_text("ignored", encoding="utf-8")

    discovered = discover_theme_files([themes])

    assert discovered == [first, second]


def test_load_imported_themes_parses_itermcolors(tmp_path: Path) -> None:
    payload = {
        "Background Color": _iterm_color(0.0, 0.0, 0.0),
        "Foreground Color": _iterm_color(1.0, 1.0, 1.0),
        "Ansi 1 Color": _iterm_color(1.0, 0.0, 0.0),
        "Ansi 2 Color": _iterm_color(0.0, 1.0, 0.0),
        "Ansi 4 Color": _iterm_color(0.0, 0.0, 1.0),
        "Ansi 11 Color": _iterm_color(1.0, 1.0, 0.0),
        "Ansi 13 Color": _iterm_color(1.0, 0.0, 1.0),
        "Ansi 14 Color": _iterm_color(0.0, 1.0, 1.0),
    }
    path = tmp_path / "Demo.itermcolors"
    path.write_bytes(plistlib.dumps(payload))

    themes, warnings = load_imported_themes(
        [path],
        profile="balanced",
        quantize_ansi256=False,
    )

    assert warnings == []
    assert len(themes) == 1
    theme = themes[0]
    assert theme.name == "Demo"
    assert theme.background == "#000000"
    assert theme.foreground == "#ffffff"


def test_load_imported_themes_supports_overrides(tmp_path: Path) -> None:
    path = tmp_path / "demo.colortheme"
    path.write_text(
        "background=#101010\n"
        "foreground=#f0f0f0\n"
        "color14=#00ffcc\n"
        "color9=#dd3333\n",
        encoding="utf-8",
    )

    themes, warnings = load_imported_themes(
        [path],
        profile="soft",
        overrides={
            "demo": {
                "primary": "ansi14",
                "panel": "#112233",
            }
        },
        quantize_ansi256=False,
    )

    assert warnings == []
    assert len(themes) == 1
    theme = themes[0]
    assert theme.name == "demo"
    assert theme.primary == "#00ffcc"
    assert theme.panel == "#112233"


def test_normalize_mapping_profile_rejects_unknown() -> None:
    try:
        normalize_mapping_profile("unknown")
    except ValueError as exc:
        assert "Unsupported theme_mapping_profile" in str(exc)
        return
    raise AssertionError("Expected ValueError for unknown mapping profile")


def test_save_and_load_converted_theme(tmp_path: Path) -> None:
    source = tmp_path / "demo.colortheme"
    source.write_text(
        "background=#101010\n"
        "foreground=#f0f0f0\n"
        "color14=#00ffcc\n"
        "color9=#dd3333\n",
        encoding="utf-8",
    )
    imported, warnings = load_imported_themes(
        [source],
        profile="balanced",
        quantize_ansi256=True,
    )
    assert warnings == []
    assert len(imported) == 1
    theme = imported[0]

    store_dir = tmp_path / "store"
    saved = save_converted_theme(
        theme=theme,
        store_dir=store_dir,
        source_path=source,
        mapping_profile="balanced",
        quantize_ansi256=True,
    )

    assert saved.exists()
    loaded, load_warnings = load_saved_themes(store_dir=store_dir)
    assert load_warnings == []
    assert len(loaded) == 1
    assert loaded[0].name == theme.name
    assert loaded[0].background == theme.background


def test_default_theme_store_dir_uses_config_parent(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "custom.yaml"
    expected = Path.home() / ".config" / "sm-logtool" / "themes"
    assert default_theme_store_dir(config_path) == expected
