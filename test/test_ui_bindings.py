from pathlib import Path

import pytest

from sm_logtool.ui.app import LogBrowser, WizardStep

SAMPLE_LOGS = Path(__file__).resolve().parent.parent / "sample_logs"


@pytest.mark.asyncio
async def test_footer_shows_global_keys_on_results_step():
    app = LogBrowser(logs_dir=SAMPLE_LOGS)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_results("Example\n")
        await pilot.pause()
        footer = app.footer
        assert footer is not None
        rendered = footer.render()
        text = str(rendered)
        assert "Quit" in text
        assert "Reset Search" in text
        assert "Menu" in text


@pytest.mark.asyncio
async def test_reset_shortcut_returns_to_kind_step():
    app = LogBrowser(logs_dir=SAMPLE_LOGS)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_results("Example\n")
        await pilot.pause()
        assert app.step == WizardStep.RESULTS
        await pilot.press("r")
        await pilot.pause()
        assert app.step == WizardStep.KIND


@pytest.mark.asyncio
async def test_quit_shortcut_sets_exit_flag():
    app = LogBrowser(logs_dir=SAMPLE_LOGS)
    async with app.run_test() as pilot:
        app._refresh_logs()
        kind, infos = next(iter(app._logs_by_kind.items()))
        app.current_kind = kind
        app.selected_logs = infos[:1]
        app._show_step_results("Example\n")
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert app._exit is True
