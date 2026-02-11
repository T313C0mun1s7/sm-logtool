import importlib.util
from pathlib import Path
import unittest

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - fallback for unittest
    from test import _pytest_stub as pytest

if importlib.util.find_spec("textual") is None:
    raise unittest.SkipTest("Textual not installed")

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
        bindings = [
            binding
            for (_, binding, enabled, _tooltip) in (
                app.screen.active_bindings.values()
            )
            if enabled and binding.show
        ]
        descriptions = {binding.description for binding in bindings}
        assert "Quit" in descriptions
        assert "Reset Search" in descriptions
        assert "Menu" in descriptions


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
        await pilot.press("ctrl+r")
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
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert app._exit is True
