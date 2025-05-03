from typing import Optional, Tuple
from .android_action import AndroidActionType

class AndroidStateTracker:
    def __init__(self):
        self.last_tap_position = None
        self.last_action = None
        self.action_count = {}
        self.max_attempts = 3
        self.must_type_next = False
        self.last_screen_state = None
        self.input_box_tapped = False  # New flag to track if we tapped an input box

    def update_state(self, action: AndroidActionType, coordinate: Optional[Tuple[float, float]] = None, text: Optional[str] = None) -> bool:
        """Update the state tracker with a new action.
        
        Args:
            action: The type of action being performed
            coordinate: Optional coordinate for tap actions
            text: Optional text for type actions
            
        Returns:
            bool: Whether the action should be allowed
        """
        # Update action count
        if action not in self.action_count:
            self.action_count[action] = 0
        self.action_count[action] += 1
        
        # Check for redundant actions
        if action == self.last_action:
            if self.action_count[action] > self.max_attempts:
                return False
        
        # Special handling for input box taps
        if action == AndroidActionType.TAP and coordinate:
            self.input_box_tapped = True
            self.must_type_next = True
        elif action == AndroidActionType.TYPE:
            if self.must_type_next:
                self.must_type_next = False
                self.input_box_tapped = False
            else:
                return False
        
        # Update last action
        self.last_action = action
        if coordinate:
            self.last_tap_position = coordinate
            
        return True

    def _is_input_box(self, coordinate: Tuple[float, float]) -> bool:
        """Detect if the tapped area is likely an input box.
        
        This is a simple implementation. You might want to enhance it with:
        1. OCR to detect input fields
        2. Screen analysis to identify input areas
        3. App-specific knowledge of input field locations
        """
        # For now, we'll assume any tap in the upper half of the screen is an input box
        # This is a placeholder - you should replace this with proper detection
        return coordinate[1] < 500  # Assuming screen height is 1000

    def reset(self) -> None:
        """Reset the state tracker"""
        self.last_tap_position = None
        self.last_action = None
        self.action_count = {}
        self.must_type_next = False
        self.last_screen_state = None
        self.input_box_tapped = False 