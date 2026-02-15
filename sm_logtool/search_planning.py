"""Planning helpers for adaptive search execution strategy."""

from __future__ import annotations

from dataclasses import dataclass


_SMALL_TWO_TARGET_BYTES = 96 * 1024 * 1024
_SMALL_PER_TARGET_BYTES = 48 * 1024 * 1024
_MEDIUM_TOTAL_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class SearchExecutionPlan:
    """Execution strategy for a search run."""

    workers: int
    reason: str


def choose_search_execution_plan(
    target_count: int,
    total_bytes: int,
    *,
    use_index_cache: bool,
    max_workers: int,
) -> SearchExecutionPlan:
    """Return an adaptive serial/parallel search execution plan."""

    if target_count <= 1:
        return SearchExecutionPlan(1, "single target")

    bounded_workers = max(1, min(target_count, max_workers))
    if use_index_cache:
        if target_count == 2:
            return SearchExecutionPlan(1, "indexed two-target workload")
        if total_bytes <= 0:
            return SearchExecutionPlan(
                bounded_workers,
                "indexed workload size unavailable",
            )
        if total_bytes < _MEDIUM_TOTAL_BYTES:
            workers = min(2, bounded_workers)
            return SearchExecutionPlan(workers, "indexed medium workload")
        return SearchExecutionPlan(bounded_workers, "indexed large workload")

    if total_bytes <= 0:
        return SearchExecutionPlan(bounded_workers, "workload size unavailable")

    per_target = total_bytes / target_count
    if target_count == 2 and total_bytes < _SMALL_TWO_TARGET_BYTES:
        return SearchExecutionPlan(1, "small two-target workload")

    if target_count <= 3 and per_target < _SMALL_PER_TARGET_BYTES:
        return SearchExecutionPlan(1, "small per-target workload")

    if total_bytes < _MEDIUM_TOTAL_BYTES and bounded_workers > 2:
        return SearchExecutionPlan(2, "medium workload")

    return SearchExecutionPlan(bounded_workers, "large workload")
