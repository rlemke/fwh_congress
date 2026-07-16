"""congress domain — US congressional (voting) districts + party of the sitting rep.

Discovered by the Facetwork runner via the ``facetwork.domains`` entry point::

    [project.entry-points."facetwork.domains"]
    congress = "congress:domain"
"""

from __future__ import annotations

from pathlib import Path

from facetwork.domains import DomainPackage

from .handlers import register_all_registry_handlers

domain = DomainPackage(
    name="congress",
    ffl_dir=Path(__file__).parent / "ffl",
    register_handlers=register_all_registry_handlers,
    runner_env={
        "FW_TASK_EXECUTION_TIMEOUT_MS": "1200000",  # 20 min (shape ZIP + parse; cached after)
        "FW_STUCK_TIMEOUT_MS": "1500000",
    },
)
