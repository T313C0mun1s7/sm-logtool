from sm_logtool import log_kinds


def test_search_ungrouped_kinds_exclude_administrative() -> None:
    assert log_kinds.is_search_ungrouped_kind("activation")
    assert log_kinds.is_search_ungrouped_kind("webdav")
    assert not log_kinds.is_search_ungrouped_kind("administrative")


def test_entry_render_kinds_include_administrative() -> None:
    assert log_kinds.is_entry_render_kind("administrative")
    assert log_kinds.is_entry_render_kind("activation")
    assert not log_kinds.is_entry_render_kind("smtp")


def test_entry_render_kinds_cover_search_ungrouped_kinds() -> None:
    missing = [
        kind
        for kind in log_kinds.SEARCH_UNGROUPED_KINDS
        if kind not in log_kinds.ENTRY_RENDER_KINDS
    ]
    assert not missing
