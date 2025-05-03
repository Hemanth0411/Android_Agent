from dataclasses import dataclass
from typing import Optional

from .android_action import AndroidAction
from .android_state import AndroidState

@dataclass
class AndroidStep:
    """Represents a single step in the automation session.
    
    Attributes:
        action: The action that was performed
        state: The state of the device after the action
        timestamp: When the step was recorded
    """
    action: AndroidAction
    state: AndroidState
    timestamp: Optional[float] = None 