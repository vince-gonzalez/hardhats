"""Deterministic gates. A gate is a callable that measures something and
can fail; nothing in here asks a model anything."""
from .webtest import (GATES, GAME_GATES, Finding, Result, Target,
                      BLOCK, WARN, NOTE)

__all__ = ["GATES", "GAME_GATES", "Finding", "Result", "Target",
           "BLOCK", "WARN", "NOTE"]
