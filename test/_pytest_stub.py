"""Minimal pytest stub for unittest discovery environments."""

from __future__ import annotations

from contextlib import contextmanager


class _Mark:
    def __getattr__(self, _name: str):
        def decorator(func):
            return func

        return decorator


class _PytestStub:
    mark = _Mark()

    @staticmethod
    @contextmanager
    def raises(expected_exception):
        try:
            yield
        except expected_exception:
            return
        raise AssertionError(
            f"Expected {expected_exception.__name__} to be raised"
        )


pytest = _PytestStub()
