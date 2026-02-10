from pathlib import Path

import pytest

from sm_logtool.ui.app import LogBrowser, MenuScreen

SAMPLE_LOGS = Path(__file__).resolve().parent.parent / "sample_logs"


@pytest.mark.asyncio
async def test_menu_shortcut_opens_and_closes():
    app = LogBrowser(logs_dir=SAMPLE_LOGS)
    async with app.run_test() as pilot:
        await pilot.press("m")
        await pilot.pause()
        assert isinstance(app.screen, MenuScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, MenuScreen)
