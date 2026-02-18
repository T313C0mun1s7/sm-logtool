from __future__ import annotations

from pathlib import Path
import plistlib

from sm_logtool.ui.theme_importer import default_theme_store_dir
from sm_logtool.ui.theme_importer import map_terminal_palette
from sm_logtool.ui.theme_importer import TerminalPalette
from sm_logtool.ui.theme_importer import load_saved_themes
from sm_logtool.ui.theme_importer import discover_theme_files
from sm_logtool.ui.theme_importer import load_imported_themes
from sm_logtool.ui.theme_importer import normalize_mapping_profile
from sm_logtool.ui.theme_importer import save_converted_theme
from rich.color_triplet import ColorTriplet


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


def test_save_converted_theme_overwrites_by_name(tmp_path: Path) -> None:
    source = tmp_path / "demo.colortheme"
    source.write_text(
        "background=#101010\n"
        "foreground=#f0f0f0\n"
        "color14=#00ffcc\n"
        "color9=#dd3333\n",
        encoding="utf-8",
    )
    imported, _ = load_imported_themes(
        [source],
        profile="balanced",
        quantize_ansi256=True,
    )
    theme = imported[0]
    store_dir = tmp_path / "store"

    first = save_converted_theme(
        theme=theme,
        store_dir=store_dir,
        source_path=source,
        mapping_profile="balanced",
        quantize_ansi256=True,
    )
    second = save_converted_theme(
        theme=theme,
        store_dir=store_dir,
        source_path=source,
        mapping_profile="balanced",
        quantize_ansi256=True,
    )

    assert first == second
    saved_files = list(store_dir.glob("*.smlogtheme.yaml"))
    assert len(saved_files) == 1


def test_mapping_profiles_produce_distinct_themes() -> None:
    palette = TerminalPalette(
        name="Demo",
        source=Path("/tmp/demo.colortheme"),
        background=ColorTriplet(16, 16, 16),
        foreground=ColorTriplet(240, 240, 240),
        cursor=ColorTriplet(240, 240, 240),
        ansi=(
            ColorTriplet(0, 0, 0),
            ColorTriplet(255, 64, 64),
            ColorTriplet(64, 255, 128),
            ColorTriplet(255, 210, 64),
            ColorTriplet(86, 170, 255),
            ColorTriplet(226, 128, 255),
            ColorTriplet(96, 236, 255),
            ColorTriplet(214, 214, 214),
            ColorTriplet(96, 96, 96),
            ColorTriplet(255, 96, 124),
            ColorTriplet(96, 255, 164),
            ColorTriplet(255, 232, 96),
            ColorTriplet(120, 196, 255),
            ColorTriplet(236, 156, 255),
            ColorTriplet(132, 244, 255),
            ColorTriplet(255, 255, 255),
        ),
    )
    balanced = map_terminal_palette(
        name="balanced",
        palette=palette,
        profile="balanced",
        overrides=None,
        quantize_ansi256=False,
    )
    vivid = map_terminal_palette(
        name="vivid",
        palette=palette,
        profile="vivid",
        overrides=None,
        quantize_ansi256=False,
    )
    soft = map_terminal_palette(
        name="soft",
        palette=palette,
        profile="soft",
        overrides=None,
        quantize_ansi256=False,
    )

    assert balanced.accent != vivid.accent
    assert (
        vivid.variables["selection-selected-background"]
        != soft.variables["selection-selected-background"]
    )


def test_saved_theme_round_trip_preserves_visual_values(tmp_path: Path) -> None:
    source = tmp_path / "demo.colortheme"
    source.write_text(
        "background=#111111\n"
        "foreground=#f3f3f3\n"
        "color14=#00ffcc\n"
        "color13=#ff66cc\n"
        "color12=#55aaff\n",
        encoding="utf-8",
    )
    imported, warnings = load_imported_themes(
        [source],
        profile="vivid",
        quantize_ansi256=True,
    )
    assert warnings == []
    theme = imported[0]
    store_dir = tmp_path / "store"

    save_converted_theme(
        theme=theme,
        store_dir=store_dir,
        source_path=source,
        mapping_profile="vivid",
        quantize_ansi256=True,
    )
    loaded, load_warnings = load_saved_themes(store_dir=store_dir)
    assert load_warnings == []
    assert len(loaded) == 1
    saved = loaded[0]

    assert saved.name == theme.name
    assert saved.primary == theme.primary
    assert saved.accent == theme.accent
    assert saved.background == theme.background
    assert saved.panel == theme.panel
    assert dict(saved.variables or {}) == dict(theme.variables or {})
