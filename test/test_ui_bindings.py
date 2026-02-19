from pathlib import Path
import time

import pytest
from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import Button, Static

from sm_logtool import config as config_module
from sm_logtool.search import Conversation
from sm_logtool.search import get_search_function
from sm_logtool.search import SmtpSearchResult
from sm_logtool.ui import app as ui_app_module
from sm_logtool.ui.app import LogBrowser, ResultsArea, TopAction, WizardStep
from sm_logtool.ui.themes import CYBERDARK_THEME_NAME
from sm_logtool.ui.themes import CYBERNOTDARK_THEME_NAME
from sm_logtool.ui.theme_importer import load_imported_themes
from sm_logtool.ui.theme_importer import save_converted_theme
from sm_logtool.ui.theme_studio import ThemeStudio


def write_sample_logs(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    log_path = root / "2024.01.01-smtpLog.log"
    log_path.write_text(
        "00:00:00 [1.1.1.1][ABC123] Connection initiated\n",
        encoding="utf-8",
    )


def test_log_browser_loads_saved_converted_themes(tmp_path):
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

    store_dir = tmp_path / "saved-themes"
    save_converted_theme(
        theme=imported[0],
        store_dir=store_dir,
        source_path=source,
        mapping_profile="balanced",
        quantize_ansi256=True,
    )
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)

    app = LogBrowser(logs_dir=logs_dir, theme_store_dir=store_dir)
    assert imported[0].name in app.available_themes


def test_theme_studio_quit_button_calls_exit(monkeypatch, tmp_path):
    app = ThemeStudio(
        source_paths=(tmp_path,),
        store_dir=tmp_path / "themes",
        profile="balanced",
        quantize_ansi256=True,
    )
    called = {"value": False}

    def _fake_exit() -> None:
        called["value"] = True

    monkeypatch.setattr(app, "exit", _fake_exit)
    button = Button("Quit", id="quit-studio")
    app.on_button_pressed(Button.Pressed(button))
    assert called["value"] is True


def test_theme_studio_preview_theme_name_changes_each_refresh(tmp_path):
    app = ThemeStudio(
        source_paths=(tmp_path,),
        store_dir=tmp_path / "themes",
        profile="balanced",
        quantize_ansi256=True,
    )
    first = app._next_preview_theme_name()
    second = app._next_preview_theme_name()
    assert first != second


def test_theme_studio_default_save_name_uses_source_name(tmp_path):
    app = ThemeStudio(
        source_paths=(tmp_path,),
        store_dir=tmp_path / "themes",
        profile="balanced",
        quantize_ansi256=True,
    )
    assert app._default_save_name("builtin-tango-light") == (
        "builtin-tango-light"
    )
    assert app._default_save_name("My Theme") == "My Theme"


@pytest.mark.asyncio
async def test_theme_studio_syntax_preview_uses_results_area(tmp_path):
    source = tmp_path / "demo.colortheme"
    source.write_text(
        "background=#101010\n"
        "foreground=#f0f0f0\n"
        "color14=#00ffcc\n"
        "color9=#dd3333\n",
        encoding="utf-8",
    )
    app = ThemeStudio(
        source_paths=(tmp_path,),
        store_dir=tmp_path / "themes",
        profile="balanced",
        quantize_ansi256=True,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        preview = app.query_one("#syntax-preview", ResultsArea)
        assert isinstance(preview, ResultsArea)


@pytest.mark.asyncio
async def test_theme_studio_override_controls_cycle_source(tmp_path):
    source = tmp_path / "demo.colortheme"
    source.write_text(
        "background=#101010\n"
        "foreground=#f0f0f0\n"
        "color14=#00ffcc\n"
        "color9=#dd3333\n",
        encoding="utf-8",
    )
    app = ThemeStudio(
        source_paths=(tmp_path,),
        store_dir=tmp_path / "themes",
        profile="balanced",
        quantize_ansi256=True,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._active_override_target == "selection-selected-background"
        app.action_override_source_next()
        await pilot.pause()
        assert (
            app._manual_overrides.get("selection-selected-background")
            == "accent"
        )

        app.action_override_target_next()
        await pilot.pause()
        assert app._active_override_target != "selection-selected-background"


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
async def test_kind_and_date_steps_use_compact_uniform_action_buttons(
    tmp_path,
):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        def _label_text(button: Button) -> str:
            rendered = button.render()
            if isinstance(rendered, Text):
                return rendered.plain
            return str(button.label)

        await pilot.pause()
        assert app.kind_list is not None
        assert "selection-list" in app.kind_list.classes
        kind_row = app.wizard.query_one(".button-row", Horizontal)
        kind_buttons = list(kind_row.query(Button))
        assert kind_buttons
        assert all(
            "action-button" in button.classes
            for button in kind_buttons
        )
        assert len({button.size.width for button in kind_buttons}) == 1
        assert kind_buttons[0].size.width >= max(
            len(_label_text(button))
            for button in kind_buttons
        )

        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_date()
        await pilot.pause()

        assert app.date_list is not None
        assert "selection-list" in app.date_list.classes
        date_row = app.wizard.query_one(".button-row", Horizontal)
        date_buttons = list(date_row.query(Button))
        assert date_buttons
        assert all(
            "action-button" in button.classes
            for button in date_buttons
        )
        assert len({button.size.width for button in date_buttons}) == 1
        assert date_buttons[0].size.width >= max(
            len(_label_text(button))
            for button in date_buttons
        )


@pytest.mark.asyncio
async def test_search_and_results_steps_use_explicit_button_groups(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        def _label_text(button: Button) -> str:
            rendered = button.render()
            if isinstance(rendered, Text):
                return rendered.plain
            return str(button.label)

        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]

        app._show_step_search()
        await pilot.pause()
        assert app.search_input is not None
        assert "search-term-input" in app.search_input.classes
        search_row = app.wizard.query_one(".button-row", Horizontal)
        search_left = search_row.query_one(".left-buttons", Horizontal)
        search_right = search_row.query_one(".right-buttons", Horizontal)
        search_left_buttons = list(search_left.query(Button))
        search_right_buttons = list(search_right.query(Button))
        assert search_left.query_one("#cancel-search", Button)
        assert search_right.query_one("#cycle-search-mode", Button)
        assert search_left_buttons
        assert search_right_buttons
        assert len({button.size.width for button in search_left_buttons}) == 1
        assert len({button.size.width for button in search_right_buttons}) == 1
        assert search_left_buttons[0].size.width >= max(
            len(_label_text(button))
            for button in search_left_buttons
        )
        assert search_right_buttons[0].size.width >= max(
            len(_label_text(button))
            for button in search_right_buttons
        )

        app._show_step_results()
        await pilot.pause()
        results_row = app.wizard.query_one("#results-buttons", Horizontal)
        results_left = results_row.query_one(".left-buttons", Horizontal)
        results_right = results_row.query_one(".right-buttons", Horizontal)
        results_left_buttons = list(results_left.query(Button))
        results_right_buttons = list(results_right.query(Button))
        assert results_left.query_one("#quit-results", Button)
        assert results_left.query_one("#sub-search", Button)
        assert results_right.query_one("#copy-all", Button)
        assert results_left_buttons
        assert results_right_buttons
        assert len({button.size.width for button in results_left_buttons}) == 1
        assert len(
            {button.size.width for button in results_right_buttons}
        ) == 1
        assert results_left_buttons[0].size.width >= max(
            len(_label_text(button))
            for button in results_left_buttons
        )
        assert results_right_buttons[0].size.width >= max(
            len(_label_text(button))
            for button in results_right_buttons
        )


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
async def test_search_step_busy_state_toggles_controls(tmp_path):
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

        search_button = app.wizard.query_one("#do-search", Button)
        cancel_button = app.wizard.query_one("#cancel-search", Button)
        assert app.search_input is not None
        assert app.search_input.disabled is False
        assert search_button.disabled is False
        assert cancel_button.disabled is True

        app._set_search_running(True)
        await pilot.pause()
        assert app.search_input.disabled is True
        assert search_button.disabled is True
        assert cancel_button.disabled is False
        assert app.check_action("next_search_mode", ()) is False

        app._set_search_running(False)
        await pilot.pause()
        assert app.search_input.disabled is False
        assert search_button.disabled is False
        assert cancel_button.disabled is True


@pytest.mark.asyncio
async def test_perform_search_notifies_submit_immediately(
    tmp_path,
    monkeypatch,
):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir, staging_dir=staging_dir)

    class _WorkerStub:
        is_finished = False
        is_cancelled = False

    def _run_worker_stub(*_args, **_kwargs):
        return _WorkerStub()

    monkeypatch.setattr(app, "run_worker", _run_worker_stub)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_search()
        await pilot.pause()

        assert app.search_input is not None
        app.search_input.value = "Connection"
        app._perform_search()
        await pilot.pause()

        status = app.wizard.query_one("#status", Static)
        assert "Search submitted. Preparing logs..." in str(status.render())
        assert app.step == WizardStep.RESULTS
        progress_text = app._get_full_results_text() or ""
        assert "[progress]" in progress_text
        assert "Search submitted. Preparing logs..." in progress_text
        assert "[execution]" in progress_text
        assert "Planning execution mode..." in progress_text
        assert app._search_in_progress is True
        cancel_button = app.wizard.query_one("#cancel-search", Button)
        assert cancel_button.disabled is False


@pytest.mark.asyncio
async def test_stale_back_results_button_event_is_ignored(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app.last_rendered_lines = ["prior-result-line"]
        app.last_rendered_kind = kind
        app._display_results(["current-result-line"], kind)
        await pilot.pause()

        stale_button = Button("Back to Results", id="back-results")
        app.on_button_pressed(Button.Pressed(stale_button))
        await pilot.pause()

        assert app.step == WizardStep.RESULTS
        assert isinstance(app.output_log, ResultsArea)
        assert app.output_log.text == "current-result-line"


@pytest.mark.asyncio
async def test_stale_back_subsearch_button_event_is_ignored(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app.subsearch_terms = ["john@prime42.net", "blocked"]
        app.subsearch_paths = [logs_dir / "one.log", logs_dir / "two.log"]
        app.subsearch_rendered = [
            ["prior-result-line"],
            ["current-result-line"],
        ]
        app.subsearch_depth = len(app.subsearch_paths)
        app.subsearch_path = app.subsearch_paths[-1]
        app.subsearch_kind = kind
        app.last_rendered_lines = ["current-result-line"]
        app.last_rendered_kind = kind
        app._display_results(["current-result-line"], kind)
        await pilot.pause()

        stale_button = Button("Back", id="back-subsearch")
        app.on_button_pressed(Button.Pressed(stale_button))
        await pilot.pause()

        assert app.step == WizardStep.RESULTS
        assert isinstance(app.output_log, ResultsArea)
        assert app.output_log.text == "current-result-line"


@pytest.mark.asyncio
async def test_back_subsearch_requires_arm_after_results_redraw(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app.subsearch_terms = ["john@prime42.net", "blocked"]
        app.subsearch_paths = [logs_dir / "one.log", logs_dir / "two.log"]
        app.subsearch_rendered = [
            ["prior-result-line"],
            ["current-result-line"],
        ]
        app.subsearch_depth = len(app.subsearch_paths)
        app.subsearch_path = app.subsearch_paths[-1]
        app.subsearch_kind = kind
        app.last_rendered_lines = ["current-result-line"]
        app.last_rendered_kind = kind
        app._display_results(["current-result-line"], kind)
        await pilot.pause()

        back_button = app.wizard.query_one("#back-subsearch", Button)
        app._back_navigation_armed_at = time.perf_counter() + 60
        app.on_button_pressed(Button.Pressed(back_button))
        await pilot.pause()

        assert app.step == WizardStep.RESULTS
        assert isinstance(app.output_log, ResultsArea)
        assert app.output_log.text == "current-result-line"

        app._back_navigation_armed_at = 0.0
        app.on_button_pressed(Button.Pressed(back_button))
        await pilot.pause()

        assert app.step == WizardStep.RESULTS
        assert isinstance(app.output_log, ResultsArea)
        assert app.output_log.text == "prior-result-line"


@pytest.mark.asyncio
async def test_target_progress_status_is_determinate(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        await pilot.pause()
        app._notify_target_search_progress(
            1,
            2,
            "2024.01.01-smtpLog.log",
            512,
            1024,
        )
        await pilot.pause()

        status = app.wizard.query_one("#status", Static)
        status_text = str(status.render())
        assert "Searching 1/2 log(s): 2024.01.01-smtpLog.log" in status_text
        assert "50%" in status_text
        assert "(512.0B/1.0KB)" in status_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raised_error",
    [
        PermissionError("no access"),
        RuntimeError("pool failed"),
        ValueError("bad pool state"),
    ],
)
async def test_parallel_search_uses_process_fallback_before_serial(
    tmp_path,
    monkeypatch,
    raised_error,
):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "2024.01.01-smtpLog.log").write_text(
        "00:00:00 [1.1.1.1][A] Connection initiated\n",
        encoding="utf-8",
    )
    (logs_dir / "2024.01.02-smtpLog.log").write_text(
        "00:00:00 [2.2.2.2][B] Connection initiated\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        ui_app_module,
        "_search_targets_in_thread_pool",
        lambda *args, **kwargs: (_ for _ in ()).throw(raised_error),
    )

    app = LogBrowser(logs_dir=logs_dir, staging_dir=staging_dir)
    async with app.run_test() as pilot:
        app._refresh_logs()
        infos = app._logs_by_kind["smtp"]
        app.current_kind = "smtp"
        app.selected_logs = [infos[1], infos[0]]
        app._show_step_search()
        await pilot.pause()
        assert app.search_input is not None
        app.search_input.value = "Connection"
        request = app._build_search_request()
        assert request is not None
        search_fn = get_search_function("smtp")
        assert search_fn is not None

        def _direct(f, *a):
            return f(*a)

        app.call_from_thread = _direct

        class _Worker:
            is_cancelled = False

        def _process_success(
            request,
            targets,
            *,
            workers,
            is_cancelled=None,
            on_result=None,
            on_completed=None,
        ):
            _ = workers
            results = []
            total = len(targets)
            for index, target in enumerate(targets):
                if is_cancelled is not None and is_cancelled():
                    raise AssertionError("cancelled unexpectedly")
                result = ui_app_module._search_single_target(
                    request.kind,
                    target,
                    request.term,
                    request.mode,
                    request.fuzzy_threshold,
                    request.ignore_case,
                    request.use_index_cache,
                )
                results.append(result)
                if on_result is not None:
                    on_result(index, target, result)
                if on_completed is not None:
                    on_completed(index + 1, total, target)
            return results

        monkeypatch.setattr(
            ui_app_module,
            "_search_targets_in_process_pool",
            _process_success,
        )

        def _fail_serial(*_args, **_kwargs):
            raise AssertionError("serial fallback should not run")

        monkeypatch.setattr(app, "_search_targets_serial", _fail_serial)
        results = app._search_targets_parallel(
            request,
            request.source_paths,
            workers=2,
            search_fn=search_fn,
            worker=_Worker(),
        )
        names = [result.log_path.name for result in results]
        assert names == [
            "2024.01.01-smtpLog.log",
            "2024.01.02-smtpLog.log",
        ]
        assert app._live_execution_label is not None
        assert "process fallback" in app._live_execution_label


@pytest.mark.asyncio
async def test_worker_error_stays_on_results_and_shows_message(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._show_step_results()
        app._set_search_running(True)
        await pilot.pause()

        class _WorkerStub:
            error = ValueError("boom")
            result = None

        worker = _WorkerStub()
        app._search_worker = worker

        class _EventStub:
            def __init__(self) -> None:
                self.worker = worker
                self.state = ui_app_module.WorkerState.ERROR

        app.on_worker_state_changed(_EventStub())
        await pilot.pause()

        assert app.step == WizardStep.RESULTS
        text = app._get_full_results_text() or ""
        assert "[search error]" in text
        assert "boom" in text


@pytest.mark.asyncio
async def test_live_result_stream_keeps_target_order(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir, staging_dir=tmp_path / "staging")
    target_a = logs_dir / "2024.01.01-smtpLog.log"
    target_b = logs_dir / "2024.01.02-smtpLog.log"
    target_b.write_text(
        "00:00:00 [2.2.2.2][B] Connection initiated\n",
        encoding="utf-8",
    )
    result_a = SmtpSearchResult(
        term="Connection",
        log_path=target_a,
        conversations=[
            Conversation(
                message_id="A",
                lines=["00:00:00 [1.1.1.1][A] Connection initiated"],
                first_line_number=1,
            )
        ],
        total_lines=1,
        orphan_matches=[],
    )
    result_b = SmtpSearchResult(
        term="Connection",
        log_path=target_b,
        conversations=[
            Conversation(
                message_id="B",
                lines=["00:00:00 [2.2.2.2][B] Connection initiated"],
                first_line_number=1,
            )
        ],
        total_lines=1,
        orphan_matches=[],
    )
    async with app.run_test() as pilot:
        app._live_kind = "smtp"
        app._search_started_at = time.perf_counter() - 1.0
        app._show_step_results()
        await pilot.pause()

        app._on_live_search_result(1, target_b, result_b)
        app._on_live_search_result(0, target_a, result_a)
        await pilot.pause()

        headers = [
            line
            for line in app._live_rendered_lines
            if line.startswith("=== ")
        ]
        assert headers[:2] == [
            "=== 2024.01.01-smtpLog.log ===",
            "=== 2024.01.02-smtpLog.log ===",
        ]


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
async def test_first_party_themes_are_registered_by_default(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == CYBERDARK_THEME_NAME
        assert CYBERDARK_THEME_NAME in app.available_themes
        assert CYBERNOTDARK_THEME_NAME in app.available_themes


@pytest.mark.asyncio
async def test_results_area_switches_with_app_theme(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir)
    async with app.run_test() as pilot:
        app._show_step_results()
        await pilot.pause()

        assert app.output_log is not None
        assert app.output_log.theme == CYBERDARK_THEME_NAME

        app.theme = CYBERNOTDARK_THEME_NAME
        await pilot.pause()
        assert app.output_log.theme == CYBERNOTDARK_THEME_NAME

        app.theme = CYBERDARK_THEME_NAME
        await pilot.pause()
        assert app.output_log.theme == CYBERDARK_THEME_NAME

        app.theme = "dracula"
        await pilot.pause()
        assert app.output_log.theme == "dracula"


@pytest.mark.asyncio
async def test_startup_handles_invalid_configured_theme_gracefully(tmp_path):
    logs_dir = tmp_path / "logs"
    write_sample_logs(logs_dir)
    app = LogBrowser(logs_dir=logs_dir, theme="no-such-theme")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == CYBERDARK_THEME_NAME
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
        "theme: Cyberdark\n",
        encoding="utf-8",
    )
    app = LogBrowser(
        logs_dir=logs_dir,
        config_path=cfg_path,
        theme="Cyberdark",
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.theme = "Cybernotdark"
        await pilot.pause()

    saved = config_module.load_config(cfg_path)
    assert saved.theme == "Cybernotdark"
