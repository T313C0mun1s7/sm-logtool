from pathlib import Path

import pytest
from rich.text import Text
from textual.widgets import Button, Static

from sm_logtool import config as config_module
from sm_logtool.ui.app import LogBrowser, TopAction, WizardStep


def write_sample_logs(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    log_path = root / "2024.01.01-smtpLog.log"
    log_path.write_text(
        "00:00:00 [1.1.1.1][ABC123] Connection initiated\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_top_action_buttons_show_core_shortcuts(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        await pilot.pause()
        menu_action = app.query_one("#top-menu", TopAction)
        quit_action = app.query_one("#top-quit", TopAction)
        reset_action = app.query_one("#top-reset", TopAction)
        menu_text = menu_action.render()
        quit_text = quit_action.render()
        reset_text = reset_action.render()
        assert isinstance(menu_text, Text)
        assert isinstance(quit_text, Text)
        assert isinstance(reset_text, Text)
        assert menu_text.plain == "Menu"
        assert quit_text.plain == "Quit"
        assert reset_text.plain == "Reset"
        assert any(span.start <= 3 < span.end for span in menu_text.spans)
        assert any(span.start <= 0 < span.end for span in quit_text.spans)
        assert any(span.start <= 0 < span.end for span in reset_text.spans)


@pytest.mark.asyncio
async def test_footer_hides_core_shortcuts_outside_search_step(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_results()
        await pilot.pause()
        bindings = [
            binding
            for (_, binding, enabled, _tooltip) in (
                app.screen.active_bindings.values()
            )
            if enabled and binding.show
        ]
        descriptions = {binding.description for binding in bindings}
        assert "Quit" not in descriptions
        assert "Reset Search" not in descriptions
        assert "Menu" not in descriptions
        assert "Focus" not in descriptions
        assert "Mode next" not in descriptions
        assert "Mode prev" not in descriptions


@pytest.mark.asyncio
async def test_reset_shortcut_returns_to_kind_step(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_results()
        await pilot.pause()
        assert app.step == WizardStep.RESULTS
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert app.step == WizardStep.KIND


@pytest.mark.asyncio
async def test_top_reset_button_returns_to_kind_step(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_results()
        await pilot.pause()
        assert app.step == WizardStep.RESULTS
        reset_action = app.query_one("#top-reset", TopAction)
        reset_action._dispatch()
        await pilot.pause()
        assert app.step == WizardStep.KIND


@pytest.mark.asyncio
async def test_quit_shortcut_sets_exit_flag(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_results()
        await pilot.pause()
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert app._exit is True


@pytest.mark.asyncio
async def test_search_step_mode_controls_cycle(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_search()
        await pilot.pause()

        button = app.wizard.query_one("#cycle-search-mode", Button)
        app.wizard.query_one("#search-mode-status", Static)
        assert "Literal" in str(button.label)

        app._cycle_search_mode()
        await pilot.pause()

        assert app.search_mode == "wildcard"
        assert "Wildcard" in str(button.label)

        app._cycle_search_mode()
        await pilot.pause()

        assert app.search_mode == "regex"
        assert "Regex" in str(button.label)

        app._cycle_search_mode()
        await pilot.pause()

        assert app.search_mode == "fuzzy"
        assert "Fuzzy" in str(button.label)


@pytest.mark.asyncio
async def test_search_step_mode_shortcuts_cycle_with_input_focus(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_search()
        await pilot.pause()

        assert app.search_mode == "literal"
        await pilot.press("ctrl+right")
        await pilot.pause()
        assert app.search_mode == "wildcard"
        assert app.search_input.value == ""

        await pilot.press("ctrl+right")
        await pilot.pause()
        assert app.search_mode == "regex"
        assert app.search_input.value == ""

        await pilot.press("ctrl+right")
        await pilot.pause()
        assert app.search_mode == "fuzzy"
        assert app.search_input.value == ""

        await pilot.press("ctrl+left")
        await pilot.pause()
        assert app.search_mode == "regex"
        assert app.search_input.value == ""

        await pilot.press("ctrl+left")
        await pilot.pause()
        assert app.search_mode == "wildcard"
        assert app.search_input.value == ""

        await pilot.press("ctrl+left")
        await pilot.pause()
        assert app.search_mode == "literal"
        assert app.search_input.value == ""


@pytest.mark.asyncio
async def test_fuzzy_threshold_shortcuts_adjust_value(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_search()
        await pilot.pause()

        await pilot.press("ctrl+right", "ctrl+right", "ctrl+right")
        await pilot.pause()
        assert app.search_mode == "fuzzy"
        assert "Threshold: 0.75" in app._search_mode_status_text()

        await pilot.press("ctrl+up")
        await pilot.pause()
        assert app.fuzzy_threshold == pytest.approx(0.80)

        await pilot.press("ctrl+down")
        await pilot.pause()
        assert app.fuzzy_threshold == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_plain_question_mark_remains_input_text(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_search()
        await pilot.pause()

        await pilot.press("?")
        await pilot.pause()
        assert app.search_input.value == "?"


@pytest.mark.asyncio
async def test_startup_applies_configured_theme_when_available(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir, theme="textual-light")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "textual-light"


@pytest.mark.asyncio
async def test_startup_handles_invalid_configured_theme_gracefully(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir, theme="no-such-theme")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "textual-dark"
        status = app.wizard.query_one("#status", Static)
        assert "no-such-theme" in str(status.render())


@pytest.mark.asyncio
async def test_theme_change_persists_to_config_file(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "logs_dir: /var/lib/smartermail/Logs\n"
        "staging_dir: /var/tmp/sm-logtool/logs\n"
        "default_kind: smtp\n"
        "theme: textual-dark\n",
        encoding="utf-8",
    )
    app = LogBrowser(
        logs_dir=logs_dir,
        config_path=cfg_path,
        theme="textual-dark",
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.theme = "textual-light"
        await pilot.pause()

    saved = config_module.load_config(cfg_path)
    assert saved.theme == "textual-light"
