"""Handler registration for the congress domain."""

from __future__ import annotations

from .congress_handlers import register_handlers as _register_congress


def register_all_registry_handlers(runner) -> None:
    _register_congress(runner)
