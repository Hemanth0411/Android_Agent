from dataclasses import dataclass
from typing import Optional

@dataclass
class AndroidState:
    """Represents the current state of an Android device.
    
    Attributes:
        screenshot: Base64 encoded screenshot of the current screen
        width: Screen width in pixels
        height: Screen height in pixels
        current_app: Package name of the current foreground app
        timestamp: Timestamp when the state was captured
    """
    screenshot: str
    width: int
    height: int
    current_app: str
    timestamp: Optional[float] = None 