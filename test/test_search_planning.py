from sm_logtool.search_planning import choose_search_execution_plan


def test_plan_uses_serial_for_single_target():
    plan = choose_search_execution_plan(
        1,
        500_000_000,
        use_index_cache=False,
        max_workers=4,
    )
    assert plan.workers == 1
    assert "single target" in plan.reason


def test_plan_uses_serial_for_small_two_target_indexed_workload():
    plan = choose_search_execution_plan(
        2,
        500_000_000,
        use_index_cache=True,
        max_workers=4,
    )
    assert plan.workers == 1
    assert "indexed two-target" in plan.reason


def test_plan_uses_parallel_for_large_indexed_workload():
    plan = choose_search_execution_plan(
        6,
        2 * 1024 * 1024 * 1024,
        use_index_cache=True,
        max_workers=4,
    )
    assert plan.workers == 4
    assert "indexed large workload" in plan.reason


def test_plan_uses_serial_for_small_two_target_workload():
    plan = choose_search_execution_plan(
        2,
        64 * 1024 * 1024,
        use_index_cache=False,
        max_workers=4,
    )
    assert plan.workers == 1
    assert "small two-target" in plan.reason


def test_plan_uses_serial_for_small_per_target_workload():
    plan = choose_search_execution_plan(
        3,
        100 * 1024 * 1024,
        use_index_cache=False,
        max_workers=4,
    )
    assert plan.workers == 1
    assert "small per-target" in plan.reason


def test_plan_limits_medium_workload_parallelism():
    plan = choose_search_execution_plan(
        6,
        300 * 1024 * 1024,
        use_index_cache=False,
        max_workers=4,
    )
    assert plan.workers == 2
    assert "medium workload" in plan.reason


def test_plan_uses_bounded_workers_for_large_workload():
    plan = choose_search_execution_plan(
        8,
        2 * 1024 * 1024 * 1024,
        use_index_cache=False,
        max_workers=4,
    )
    assert plan.workers == 4
    assert "large workload" in plan.reason
