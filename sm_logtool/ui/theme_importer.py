"""Import terminal color themes as Textual themes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import plistlib
import re
from typing import Iterable, Mapping

from rich.color import Color
from rich.color_triplet import ColorTriplet
from textual.theme import Theme
import yaml

from .themes import CYBER_THEME_VARIABLE_DEFAULTS

SUPPORTED_THEME_IMPORT_SUFFIXES = (
    ".itermcolors",
    ".colors",
    ".colortheme",
)
SUPPORTED_THEME_MAPPING_PROFILES = (
    "balanced",
    "vivid",
    "soft",
)
THEME_FILE_SUFFIX = ".smlogtheme.yaml"

_SEMANTIC_COLOR_KEYS = {
    "primary",
    "secondary",
    "warning",
    "error",
    "success",
    "accent",
    "foreground",
    "background",
    "surface",
    "panel",
}

_DEFAULT_ANSI = (
    ColorTriplet(0, 0, 0),
    ColorTriplet(205, 0, 0),
    ColorTriplet(0, 205, 0),
    ColorTriplet(205, 205, 0),
    ColorTriplet(0, 0, 238),
    ColorTriplet(205, 0, 205),
    ColorTriplet(0, 205, 205),
    ColorTriplet(229, 229, 229),
    ColorTriplet(127, 127, 127),
    ColorTriplet(255, 0, 0),
    ColorTriplet(0, 255, 0),
    ColorTriplet(255, 255, 0),
    ColorTriplet(92, 92, 255),
    ColorTriplet(255, 0, 255),
    ColorTriplet(0, 255, 255),
    ColorTriplet(255, 255, 255),
)


@dataclass(frozen=True)
class TerminalPalette:
    """Terminal palette values used for semantic theme mapping."""

    name: str
    source: Path
    background: ColorTriplet
    foreground: ColorTriplet
    cursor: ColorTriplet
    ansi: tuple[ColorTriplet, ...]


@dataclass(frozen=True)
class _ProfileSpec:
    primary_slots: tuple[int, ...]
    accent_slots: tuple[int, ...]
    panel_mix: float
    surface_mix: float
    action_mix: float


_PROFILE_SPECS = {
    "balanced": _ProfileSpec(
        primary_slots=(14, 12, 6, 4),
        accent_slots=(13, 11, 10, 9, 15),
        panel_mix=0.08,
        surface_mix=0.04,
        action_mix=0.14,
    ),
    "vivid": _ProfileSpec(
        primary_slots=(12, 14, 4, 6),
        accent_slots=(13, 11, 10, 9, 14),
        panel_mix=0.11,
        surface_mix=0.05,
        action_mix=0.20,
    ),
    "soft": _ProfileSpec(
        primary_slots=(6, 4, 14, 12),
        accent_slots=(5, 3, 2, 4, 6),
        panel_mix=0.06,
        surface_mix=0.03,
        action_mix=0.10,
    ),
}

def load_imported_themes(
    paths: Iterable[Path],
    *,
    profile: str,
    overrides: Mapping[str, Mapping[str, str]] | None = None,
    quantize_ansi256: bool,
    existing_names: set[str] | None = None,
) -> tuple[list[Theme], list[str]]:
    """Load themes from files/directories and map them to Textual themes."""

    normalized_profile = normalize_mapping_profile(profile)
    override_map = _normalize_override_map(overrides)
    registered_names = set(existing_names or ())
    files = discover_theme_files(paths)

    themes: list[Theme] = []
    warnings: list[str] = []
    for file_path in files:
        try:
            palette = parse_terminal_palette(file_path)
        except ValueError as exc:
            warnings.append(f"{file_path}: {exc}")
            continue

        source_name = palette.name
        theme_name = _unique_theme_name(source_name, registered_names)
        resolved = (
            override_map.get(theme_name)
            or override_map.get(source_name)
        )
        mapped = map_terminal_palette(
            name=theme_name,
            palette=palette,
            profile=normalized_profile,
            overrides=resolved,
            quantize_ansi256=quantize_ansi256,
        )
        themes.append(mapped)
    return themes, warnings


def discover_theme_files(paths: Iterable[Path]) -> list[Path]:
    """Return sorted importable theme files from configured paths."""

    files: set[Path] = set()
    suffixes = set(SUPPORTED_THEME_IMPORT_SUFFIXES)
    for raw_path in paths:
        path = raw_path.expanduser()
        if not path.exists():
            continue
        if path.is_file() and path.suffix.lower() in suffixes:
            files.add(path)
            continue
        if not path.is_dir():
            continue
        for child in path.rglob("*"):
            if not child.is_file():
                continue
            if child.suffix.lower() in suffixes:
                files.add(child)
    return sorted(files)


def normalize_mapping_profile(profile: str) -> str:
    """Normalize and validate a mapping profile name."""

    normalized = profile.strip().lower()
    if normalized not in SUPPORTED_THEME_MAPPING_PROFILES:
        choices = ", ".join(SUPPORTED_THEME_MAPPING_PROFILES)
        raise ValueError(
            f"Unsupported theme_mapping_profile '{profile}'. "
            f"Expected one of: {choices}."
        )
    return normalized


def parse_terminal_palette(path: Path) -> TerminalPalette:
    """Parse a terminal palette from ``path``."""

    suffix = path.suffix.lower()
    if suffix == ".itermcolors":
        return _parse_itermcolors(path)
    return _parse_line_theme(path)


def map_terminal_palette(
    *,
    name: str,
    palette: TerminalPalette,
    profile: str,
    overrides: Mapping[str, str] | None,
    quantize_ansi256: bool,
) -> Theme:
    """Convert a terminal palette into a Textual app theme."""

    profile_name = normalize_mapping_profile(profile)
    spec = _PROFILE_SPECS[profile_name]
    dark = _luminance(palette.background) < 0.45

    background = palette.background
    foreground = _ensure_contrast(
        palette.foreground,
        background,
        minimum_ratio=7.0,
        prefer_light=dark,
    )

    primary = _pick_slot_color(
        palette,
        spec.primary_slots,
        background,
        minimum_ratio=3.0,
        prefer_light=dark,
    )
    secondary = _pick_slot_color(
        palette,
        (13, 5, 12, 4),
        background,
        minimum_ratio=3.0,
        prefer_light=dark,
    )
    warning = _pick_slot_color(
        palette,
        (11, 3),
        background,
        minimum_ratio=3.0,
        prefer_light=dark,
    )
    error = _pick_slot_color(
        palette,
        (9, 1),
        background,
        minimum_ratio=3.0,
        prefer_light=dark,
    )
    success = _pick_slot_color(
        palette,
        (10, 2),
        background,
        minimum_ratio=3.0,
        prefer_light=dark,
    )
    accent = _pick_slot_color(
        palette,
        spec.accent_slots,
        background,
        minimum_ratio=3.0,
        prefer_light=dark,
    )

    surface = _ensure_contrast(
        _blend(background, foreground, spec.surface_mix),
        foreground,
        minimum_ratio=4.5,
        prefer_light=not dark,
    )
    panel = _ensure_contrast(
        _blend(background, foreground, spec.panel_mix),
        foreground,
        minimum_ratio=4.5,
        prefer_light=not dark,
    )

    semantic: dict[str, ColorTriplet] = {
        "primary": primary,
        "secondary": secondary,
        "warning": warning,
        "error": error,
        "success": success,
        "accent": accent,
        "foreground": foreground,
        "background": background,
        "surface": surface,
        "panel": panel,
    }

    variables = _derive_theme_variables(
        semantic,
        action_mix=spec.action_mix,
        dark=dark,
    )
    _apply_overrides(semantic, variables, overrides or {}, palette)

    if quantize_ansi256:
        semantic = {
            key: _nearest_xterm_256(color)
            for key, color in semantic.items()
        }
        variables = {
            key: _as_hex(
                _nearest_xterm_256(
                    Color.parse(value).get_truecolor()
                )
            )
            for key, value in variables.items()
        }

    return Theme(
        name=name,
        primary=_as_hex(semantic["primary"]),
        secondary=_as_hex(semantic["secondary"]),
        warning=_as_hex(semantic["warning"]),
        error=_as_hex(semantic["error"]),
        success=_as_hex(semantic["success"]),
        accent=_as_hex(semantic["accent"]),
        foreground=_as_hex(semantic["foreground"]),
        background=_as_hex(semantic["background"]),
        surface=_as_hex(semantic["surface"]),
        panel=_as_hex(semantic["panel"]),
        dark=dark,
        variables=variables,
    )


def _parse_itermcolors(path: Path) -> TerminalPalette:
    try:
        payload = plistlib.loads(path.read_bytes())
    except Exception as exc:
        raise ValueError(f"Failed to parse plist: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Top-level plist value must be a mapping")

    ansi = [*list(_DEFAULT_ANSI)]
    for index in range(16):
        key = f"Ansi {index} Color"
        parsed = _triplet_from_iterm_dict(payload.get(key))
        if parsed is not None:
            ansi[index] = parsed

    foreground = _triplet_from_iterm_dict(payload.get("Foreground Color"))
    background = _triplet_from_iterm_dict(payload.get("Background Color"))
    cursor = _triplet_from_iterm_dict(payload.get("Cursor Color"))

    if foreground is None:
        foreground = ansi[15]
    if background is None:
        background = ansi[0]
    if cursor is None:
        cursor = foreground

    name = _theme_name_from_path(path)
    return TerminalPalette(
        name=name,
        source=path,
        foreground=foreground,
        background=background,
        cursor=cursor,
        ansi=tuple(ansi),
    )


def _parse_line_theme(path: Path) -> TerminalPalette:
    entries = _parse_line_entries(path)
    ansi = [*list(_DEFAULT_ANSI)]
    for key, value in entries.items():
        ansi_index = _ansi_index_from_key(key)
        if ansi_index is None:
            continue
        parsed = _parse_color_value(value)
        if parsed is None:
            continue
        ansi[ansi_index] = parsed

    foreground = _pick_first_color(entries, _FOREGROUND_KEYS) or ansi[15]
    background = _pick_first_color(entries, _BACKGROUND_KEYS) or ansi[0]
    cursor = _pick_first_color(entries, _CURSOR_KEYS) or foreground

    name = _theme_name_from_path(path)
    custom_name = entries.get("name")
    if custom_name:
        name = custom_name.strip()

    return TerminalPalette(
        name=name,
        source=path,
        foreground=foreground,
        background=background,
        cursor=cursor,
        ansi=tuple(ansi),
    )


def _parse_line_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    section = ""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed to read file: {exc}") from exc

    for original_line in raw.splitlines():
        line = original_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = _normalize_key(line[1:-1])
            continue

        splitter = "=" if "=" in line else ":" if ":" in line else None
        if splitter is None:
            continue
        key, value = line.split(splitter, 1)
        norm_key = _normalize_key(key)
        if section:
            norm_key = f"{section}{norm_key}"
        cleaned = value.strip().strip('"').strip("'")
        entries[norm_key] = cleaned

    collapsed: dict[str, str] = {}
    for key, value in entries.items():
        collapsed[key] = value
        suffix = re.sub(r"^[a-z]+", "", key)
        if suffix and suffix not in collapsed:
            collapsed[suffix] = value
    return collapsed


def _pick_first_color(
    entries: Mapping[str, str],
    keys: tuple[str, ...],
) -> ColorTriplet | None:
    for key in keys:
        value = entries.get(key)
        if value is None:
            continue
        parsed = _parse_color_value(value)
        if parsed is not None:
            return parsed
    return None


def _parse_color_value(value: str) -> ColorTriplet | None:
    try:
        return Color.parse(value).get_truecolor()
    except Exception:
        pass

    numeric = re.findall(r"[+-]?\d*\.?\d+", value)
    if len(numeric) != 3:
        return None

    values = [float(part) for part in numeric]
    if max(values) <= 1.0:
        return ColorTriplet(
            _clamp_byte(round(values[0] * 255)),
            _clamp_byte(round(values[1] * 255)),
            _clamp_byte(round(values[2] * 255)),
        )

    return ColorTriplet(
        _clamp_byte(round(values[0])),
        _clamp_byte(round(values[1])),
        _clamp_byte(round(values[2])),
    )


def _triplet_from_iterm_dict(value: object) -> ColorTriplet | None:
    if not isinstance(value, dict):
        return None
    red = _component_to_byte(value.get("Red Component"))
    green = _component_to_byte(value.get("Green Component"))
    blue = _component_to_byte(value.get("Blue Component"))
    if red is None or green is None or blue is None:
        return None
    return ColorTriplet(red, green, blue)


def _component_to_byte(value: object) -> int | None:
    if not isinstance(value, (float, int)):
        return None
    channel = float(value)
    if channel < 0:
        return None
    if channel <= 1.0:
        return _clamp_byte(round(channel * 255))
    if channel <= 255.0:
        return _clamp_byte(round(channel))
    if channel <= 65535.0:
        return _clamp_byte(round(channel / 257))
    return None


def _pick_slot_color(
    palette: TerminalPalette,
    slots: tuple[int, ...],
    background: ColorTriplet,
    *,
    minimum_ratio: float,
    prefer_light: bool,
) -> ColorTriplet:
    candidates = [
        palette.ansi[slot]
        for slot in slots
        if slot < len(palette.ansi)
    ]
    if not candidates:
        candidates = [palette.foreground]

    best = max(
        candidates,
        key=lambda color: _color_score(color, background, minimum_ratio),
    )
    return _ensure_contrast(
        best,
        background,
        minimum_ratio=minimum_ratio,
        prefer_light=prefer_light,
    )


def _color_score(
    color: ColorTriplet,
    background: ColorTriplet,
    minimum_ratio: float,
) -> float:
    contrast = _contrast_ratio(color, background)
    chroma = _chroma(color) / 255.0
    contrast_bonus = 1.0 if contrast >= minimum_ratio else 0.0
    return contrast + (0.4 * chroma) + contrast_bonus


def _chroma(color: ColorTriplet) -> int:
    highest = max(color.red, color.green, color.blue)
    lowest = min(color.red, color.green, color.blue)
    return highest - lowest


def _derive_theme_variables(
    semantic: Mapping[str, ColorTriplet],
    *,
    action_mix: float,
    dark: bool,
) -> dict[str, str]:
    background = semantic["background"]
    foreground = semantic["foreground"]
    panel = semantic["panel"]
    accent = semantic["accent"]
    primary = semantic["primary"]

    top_action_background = _blend(panel, foreground, action_mix)
    hover_background = _blend(top_action_background, foreground, 0.16)
    selection_background = _blend(background, accent, 0.30)
    selection_active = _blend(background, primary, 0.35)

    selected_foreground = _preferred_text_color(selection_background)
    active_foreground = _preferred_text_color(selection_active)

    return {
        **CYBER_THEME_VARIABLE_DEFAULTS,
        "top-actions-background": _as_hex(panel),
        "top-action-background": _as_hex(top_action_background),
        "top-action-hover-background": _as_hex(hover_background),
        "top-action-mnemonic-foreground": _as_hex(accent),
        "selection-selected-background": _as_hex(selection_background),
        "selection-selected-foreground": _as_hex(selected_foreground),
        "selection-active-background": _as_hex(selection_active),
        "selection-active-foreground": _as_hex(active_foreground),
        "selection-selected-active-background": _as_hex(
            _blend(selection_background, selection_active, 0.5)
        ),
        "selection-selected-active-foreground": _as_hex(
            _preferred_text_color(
                _blend(selection_background, selection_active, 0.5)
            )
        ),
        "action-button-background": _as_hex(_blend(panel, accent, 0.20)),
        "action-button-foreground": _as_hex(
            _preferred_text_color(_blend(panel, accent, 0.20))
        ),
        "action-button-hover-background": _as_hex(
            _blend(panel, accent, 0.32)
        ),
        "action-button-focus-background": _as_hex(
            _blend(panel, accent, 0.40)
        ),
        "context-menu-background": _as_hex(panel),
        "context-menu-border": _as_hex(
            _blend(accent, foreground, 0.35 if dark else 0.20)
        ),
    }


def _apply_overrides(
    semantic: dict[str, ColorTriplet],
    variables: dict[str, str],
    overrides: Mapping[str, str],
    palette: TerminalPalette,
) -> None:
    for key, raw_value in overrides.items():
        normalized_key = key.strip().lower()
        color = _resolve_override_color(raw_value, semantic, palette)
        if color is None:
            continue
        if normalized_key in _SEMANTIC_COLOR_KEYS:
            semantic[normalized_key] = color
            continue
        if normalized_key in variables:
            variables[normalized_key] = _as_hex(color)


def _resolve_override_color(
    raw_value: str,
    semantic: Mapping[str, ColorTriplet],
    palette: TerminalPalette,
) -> ColorTriplet | None:
    value = raw_value.strip()
    lower = value.lower()

    semantic_match = semantic.get(lower)
    if semantic_match is not None:
        return semantic_match

    if lower in {"bg", "background"}:
        return palette.background
    if lower in {"fg", "foreground"}:
        return palette.foreground
    if lower == "cursor":
        return palette.cursor

    ansi_match = re.fullmatch(r"ansi(\d{1,2})", lower)
    if ansi_match:
        index = int(ansi_match.group(1))
        if 0 <= index < len(palette.ansi):
            return palette.ansi[index]

    try:
        return Color.parse(value).get_truecolor()
    except Exception:
        return None


def _normalize_override_map(
    overrides: Mapping[str, Mapping[str, str]] | None,
) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    if overrides is None:
        return normalized

    for theme_name, mapping in overrides.items():
        if not isinstance(theme_name, str) or not isinstance(mapping, Mapping):
            continue
        values: dict[str, str] = {}
        for key, value in mapping.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            values[key.strip()] = value.strip()
        if values:
            normalized[theme_name.strip()] = values
    return normalized


def _unique_theme_name(name: str, existing: set[str]) -> str:
    candidate = name
    suffix = 2
    while candidate in existing:
        candidate = f"{name} ({suffix})"
        suffix += 1
    existing.add(candidate)
    return candidate


def _theme_name_from_path(path: Path) -> str:
    stem = path.stem.replace("_", " ").strip()
    if not stem:
        return path.name
    return stem


def _ansi_index_from_key(key: str) -> int | None:
    normalized = _normalize_key(key)
    match = re.search(r"(?:ansi|color)(\d{1,2})(?:color)?$", normalized)
    if match:
        value = int(match.group(1))
        if 0 <= value < 16:
            return value

    return _NAMED_SLOT_KEYS.get(normalized)


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


def _blend(
    start: ColorTriplet,
    end: ColorTriplet,
    amount: float,
) -> ColorTriplet:
    weight = max(0.0, min(1.0, amount))
    red = round(start.red + (end.red - start.red) * weight)
    green = round(start.green + (end.green - start.green) * weight)
    blue = round(start.blue + (end.blue - start.blue) * weight)
    return ColorTriplet(red, green, blue)


def _preferred_text_color(background: ColorTriplet) -> ColorTriplet:
    white = ColorTriplet(255, 255, 255)
    black = ColorTriplet(0, 0, 0)
    if _contrast_ratio(white, background) >= _contrast_ratio(
        black,
        background,
    ):
        return white
    return black


def _linear_channel(channel: int) -> float:
    scaled = channel / 255
    if scaled <= 0.03928:
        return scaled / 12.92
    return ((scaled + 0.055) / 1.055) ** 2.4


def _luminance(color: ColorTriplet) -> float:
    return (
        (0.2126 * _linear_channel(color.red))
        + (0.7152 * _linear_channel(color.green))
        + (0.0722 * _linear_channel(color.blue))
    )


def _contrast_ratio(left: ColorTriplet, right: ColorTriplet) -> float:
    left_luma = _luminance(left)
    right_luma = _luminance(right)
    light = max(left_luma, right_luma)
    dark = min(left_luma, right_luma)
    return (light + 0.05) / (dark + 0.05)


def _ensure_contrast(
    color: ColorTriplet,
    background: ColorTriplet,
    *,
    minimum_ratio: float,
    prefer_light: bool,
) -> ColorTriplet:
    if _contrast_ratio(color, background) >= minimum_ratio:
        return color
    target = ColorTriplet(255, 255, 255)
    if not prefer_light:
        target = ColorTriplet(0, 0, 0)
    for step in range(1, 21):
        candidate = _blend(color, target, step / 20)
        if _contrast_ratio(candidate, background) >= minimum_ratio:
            return candidate
    return target


def _as_hex(color: ColorTriplet) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        color.red,
        color.green,
        color.blue,
    )


def _clamp_byte(channel: int) -> int:
    return max(0, min(255, channel))


def _nearest_xterm_256(color: ColorTriplet) -> ColorTriplet:
    return min(
        _XTERM_256,
        key=lambda candidate: _distance_sq(color, candidate),
    )


def _distance_sq(left: ColorTriplet, right: ColorTriplet) -> int:
    red = left.red - right.red
    green = left.green - right.green
    blue = left.blue - right.blue
    return (red * red) + (green * green) + (blue * blue)


def _build_xterm_256_palette() -> tuple[ColorTriplet, ...]:
    palette = list(_DEFAULT_ANSI)
    steps = (0, 95, 135, 175, 215, 255)
    for red in steps:
        for green in steps:
            for blue in steps:
                palette.append(ColorTriplet(red, green, blue))
    for gray in range(8, 239, 10):
        palette.append(ColorTriplet(gray, gray, gray))
    return tuple(palette)


_XTERM_256 = _build_xterm_256_palette()


_BACKGROUND_KEYS = (
    "background",
    "bg",
    "backgroundcolor",
    "terminalbackground",
    "colorsbackground",
    "generalbackground",
)

_FOREGROUND_KEYS = (
    "foreground",
    "fg",
    "foregroundcolor",
    "textcolor",
    "generalforeground",
    "generaltext",
)

_CURSOR_KEYS = (
    "cursor",
    "cursorcolor",
    "cursorforeground",
)

_NAMED_SLOT_KEYS = {
    "black": 0,
    "red": 1,
    "green": 2,
    "yellow": 3,
    "blue": 4,
    "magenta": 5,
    "purple": 5,
    "cyan": 6,
    "white": 7,
    "brightblack": 8,
    "brightred": 9,
    "brightgreen": 10,
    "brightyellow": 11,
    "brightblue": 12,
    "brightmagenta": 13,
    "brightpurple": 13,
    "brightcyan": 14,
    "brightwhite": 15,
    "lightblack": 8,
    "lightred": 9,
    "lightgreen": 10,
    "lightyellow": 11,
    "lightblue": 12,
    "lightmagenta": 13,
    "lightpurple": 13,
    "lightcyan": 14,
    "lightwhite": 15,
}


def default_theme_store_dir(config_path: Path | None = None) -> Path:
    """Return the directory used to store converted themes."""

    _ = config_path
    return Path.home() / ".config" / "sm-logtool" / "themes"


def default_theme_source_dir(config_path: Path | None = None) -> Path:
    """Return the default directory containing import source theme files."""

    _ = config_path
    return Path.home() / ".config" / "sm-logtool" / "theme-sources"


def save_converted_theme(
    *,
    theme: Theme,
    store_dir: Path,
    source_path: Path,
    mapping_profile: str,
    quantize_ansi256: bool,
) -> Path:
    """Persist a converted theme for future reuse by the TUI."""

    normalized = normalize_mapping_profile(mapping_profile)
    directory = store_dir.expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    target = _unique_theme_path(directory, theme.name)
    payload = {
        "name": theme.name,
        "dark": bool(theme.dark),
        "primary": theme.primary,
        "secondary": theme.secondary,
        "warning": theme.warning,
        "error": theme.error,
        "success": theme.success,
        "accent": theme.accent,
        "foreground": theme.foreground,
        "background": theme.background,
        "surface": theme.surface,
        "panel": theme.panel,
        "variables": dict(theme.variables or {}),
        "meta": {
            "source_path": str(source_path.expanduser()),
            "mapping_profile": normalized,
            "quantize_ansi256": bool(quantize_ansi256),
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    }
    with target.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)
    return target


def load_saved_themes(
    *,
    store_dir: Path,
    existing_names: set[str] | None = None,
) -> tuple[list[Theme], list[str]]:
    """Load converted themes previously saved with ``save_converted_theme``."""

    names = set(existing_names or ())
    files = _discover_saved_theme_files(store_dir.expanduser())
    themes: list[Theme] = []
    warnings: list[str] = []
    for path in files:
        try:
            payload = _load_yaml_mapping(path)
            theme = _theme_from_payload(payload)
        except ValueError as exc:
            warnings.append(f"{path}: {exc}")
            continue
        unique_name = _unique_theme_name(theme.name, names)
        if unique_name != theme.name:
            theme = Theme(
                name=unique_name,
                primary=theme.primary,
                secondary=theme.secondary,
                warning=theme.warning,
                error=theme.error,
                success=theme.success,
                accent=theme.accent,
                foreground=theme.foreground,
                background=theme.background,
                surface=theme.surface,
                panel=theme.panel,
                dark=theme.dark,
                variables=dict(theme.variables or {}),
            )
        themes.append(theme)
    return themes, warnings


def _discover_saved_theme_files(store_dir: Path) -> list[Path]:
    if not store_dir.exists() or not store_dir.is_dir():
        return []
    files = [
        path
        for path in store_dir.iterdir()
        if path.is_file() and path.name.endswith(THEME_FILE_SUFFIX)
    ]
    return sorted(files)


def _unique_theme_path(store_dir: Path, theme_name: str) -> Path:
    slug = _slugify(theme_name)
    if not slug:
        slug = "theme"
    candidate = store_dir / f"{slug}{THEME_FILE_SUFFIX}"
    index = 2
    while candidate.exists():
        candidate = store_dir / f"{slug}-{index}{THEME_FILE_SUFFIX}"
        index += 1
    return candidate


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-")


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
    except OSError as exc:
        raise ValueError(f"Failed to read YAML: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("Theme file must contain a mapping.")
    return loaded


def _theme_from_payload(payload: Mapping[str, object]) -> Theme:
    name = _require_string(payload, "name")
    dark = payload.get("dark")
    if not isinstance(dark, bool):
        raise ValueError("Theme key 'dark' must be a boolean.")
    variables = payload.get("variables", {})
    if not isinstance(variables, dict):
        raise ValueError("Theme key 'variables' must be a mapping.")
    variables_dict: dict[str, str] = {}
    for key, value in variables.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Theme variables must be string key/value pairs.")
        variables_dict[key] = value

    return Theme(
        name=name,
        primary=_require_string(payload, "primary"),
        secondary=_require_string(payload, "secondary"),
        warning=_require_string(payload, "warning"),
        error=_require_string(payload, "error"),
        success=_require_string(payload, "success"),
        accent=_require_string(payload, "accent"),
        foreground=_require_string(payload, "foreground"),
        background=_require_string(payload, "background"),
        surface=_require_string(payload, "surface"),
        panel=_require_string(payload, "panel"),
        dark=dark,
        variables=variables_dict,
    )


def _require_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Theme key '{key}' must be a non-empty string.")
    return value
