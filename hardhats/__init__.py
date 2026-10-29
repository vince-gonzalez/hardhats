"""hardHats - the crew framework. coldHat is for play; hardHats are for work."""
from .backends import BACKENDS, chat
from .crew import Crew, Hat

__all__ = ["Crew", "Hat", "chat", "BACKENDS"]
__version__ = "0.5.0"
