from enum import Enum
from dataclasses import dataclass
from typing import Optional

class AndroidActionType(str, Enum):
    """Enumeration of possible Android actions."""
    TAP = "tap"
    TYPE = "type"
    PRESS = "press"
    SWIPE = "swipe"
    SWIPE_UP = "swipe_up"
    SWIPE_DOWN = "swipe_down"
    SCREENSHOT = "screenshot"
    LAUNCH_APP = "launch_app"
    WAIT = "wait"
    SUCCESS = "success"
    FAILURE = "failure"

@dataclass
class Coordinate:
    """Represents a coordinate point on the screen."""
    x: int
    y: int

@dataclass
class SwipeCoordinates:
    """Represents start and end coordinates for swipe actions."""
    start: Coordinate
    end: Coordinate
    duration: int = 100  # Default duration in milliseconds

@dataclass
class AndroidAction:
    """Represents an action to perform on an Android device."""
    action: AndroidActionType
    coordinate: Optional[Coordinate] = None
    text: Optional[str] = None
    key: Optional[int] = None
    swipe: Optional[SwipeCoordinates] = None
    package: Optional[str] = None  # Package name for LAUNCH_APP action
    activity: Optional[str] = None  # Activity name for LAUNCH_APP action
    duration: Optional[int] = None  # Duration for wait actions
    failed: bool = False  # Whether the action failed to execute 