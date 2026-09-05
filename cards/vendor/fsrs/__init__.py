"""
py-fsrs
-------

Py-FSRS is the official Python implementation of the FSRS scheduler algorithm, which can be used to develop spaced repetition systems.
"""

from typing import TYPE_CHECKING

from .card import Card
from .rating import Rating
from .review_log import ReviewLog
from .scheduler import Scheduler
from .state import State

if TYPE_CHECKING:
    from fsrs.optimizer import Optimizer


# lazy load the Optimizer module due to heavy dependencies
def __getattr__(name: str) -> type:
    if name == "Optimizer":
        global Optimizer
        from fsrs.optimizer import Optimizer

        return Optimizer
    raise AttributeError


__all__ = ["Card", "Optimizer", "Rating", "ReviewLog", "Scheduler", "State"]
