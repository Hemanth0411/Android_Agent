from typing import Optional, Tuple, List, Dict
from .android_action import AndroidActionType

class AndroidStateTracker:
    def __init__(self):
        self.last_tap_position = None
        self.last_action = None
        self.action_count = {}
        self.max_attempts = 5  # Increased from 3 to 5 for more tolerance
        self.must_type_next = False
        self.last_screen_state = None
        self.input_box_tapped = False  # Flag to track if we tapped an input box
        # Add regions where UI is expected to be different from inputs
        self.app_icon_regions = [
            (0, 0.8, 1.0, 1.0),  # Bottom 20% where app icons typically are
            (0, 0, 1.0, 0.08)    # Top status bar area
        ]
        self.consecutive_same_tap_count = 0
        self.last_tap_coords = None
        self.known_input_regions = self._init_known_input_regions()
        
    def _init_known_input_regions(self) -> Dict[str, List[Tuple[float, float, float, float]]]:
        """Initialize known input regions for common apps.
        
        Returns:
            Dictionary mapping app names to lists of input regions
        """
        return {
            "com.android.chrome": [
                (0.1, 0.05, 0.9, 0.15),  # URL bar area
                (0.1, 0.3, 0.9, 0.5)     # Google search box area
            ],
            # Add more apps as needed
        }

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
        
        # Special handling for exact same tap location to avoid being stuck clicking the same spot
        if action == AndroidActionType.TAP and coordinate:
            if self.last_tap_coords == coordinate:
                self.consecutive_same_tap_count += 1
                # Allow a few repeated taps, but not too many at exactly the same location
                if self.consecutive_same_tap_count > 3:
                    # Slightly adjust the tap position to avoid being stuck
                    print(f"⚠️ Detected exactly same tap position {self.consecutive_same_tap_count} times")
                    # Return True but flag this as a potential issue
                    if self.consecutive_same_tap_count > 5:
                        return False
            else:
                self.consecutive_same_tap_count = 0
                self.last_tap_coords = coordinate
        
        # Be more lenient with checking for redundant actions
        if action == self.last_action:
            if self.action_count[action] > self.max_attempts:
                # Reset the counter to prevent being stuck forever
                self.action_count[action] = 0
                # Only block for tap actions that seem stuck
                if action == AndroidActionType.TAP and self.consecutive_same_tap_count > 3:
                    print(f"⚠️ Excessive same-location taps detected. Blocking to avoid loop.")
                    return False
                print(f"⚠️ Many repeated {action} actions, but allowing to continue")
        
        # Special handling for input box taps - improved detection
        if action == AndroidActionType.TAP and coordinate:
            # Normalize coordinates for checking
            norm_x, norm_y = coordinate[0], coordinate[1]
            if isinstance(norm_x, (int, float)) and norm_x > 1:
                norm_x /= 1000.0  # Normalize to 0-1 range if needed
            if isinstance(norm_y, (int, float)) and norm_y > 1:
                norm_y /= 1000.0  # Normalize to 0-1 range if needed
                
            if self._is_input_box((norm_x, norm_y)):
                print(f"🖋️ Detected tap on input field at {coordinate}")
                self.input_box_tapped = True
                self.must_type_next = True
            else:
                print(f"👆 Tapped non-input area at {coordinate}")
                self.input_box_tapped = False
                self.must_type_next = False
                
                # Special case: If tapping in URL bar area of Chrome, treat as input
                if 0.1 <= norm_y <= 0.2:  # Top area where URL bar usually is
                    print(f"🖋️ Possible URL bar tap detected")
                    self.input_box_tapped = True
                    self.must_type_next = True
        elif action == AndroidActionType.TYPE:
            # Be more permissive with typing actions to avoid being stuck
            if not self.must_type_next:
                print("⚠️ Type action without tapping input field first, but allowing")
            self.must_type_next = False
            self.input_box_tapped = False
            return True
        
        # Update last action
        self.last_action = action
        if coordinate:
            self.last_tap_position = coordinate
            
        return True

    def _is_input_box(self, coordinate: Tuple[float, float]) -> bool:
        """Detect if the tapped area is likely an input box.
        
        Args:
            coordinate: Normalized x,y coordinates (0-1)
            
        Returns:
            bool: Whether the coordinate is likely an input box
        """
        x, y = coordinate[0], coordinate[1]
        
        # Check if in app icon region (bottom of screen)
        for region in self.app_icon_regions:
            left, top, right, bottom = region
            if left <= x <= right and top <= y <= bottom:
                return False
        
        # Look for known input regions in common apps
        for app_name, regions in self.known_input_regions.items():
            for region in regions:
                left, top, right, bottom = region
                if left <= x <= right and top <= y <= bottom:
                    print(f"📝 Found input region match for {app_name}")
                    return True
                
        # More generous input detection
        # 1. Address/URL bars - near top of screen
        if 0.05 <= y <= 0.2:
            if 0.1 <= x <= 0.9:  # Centered horizontally
                print("📝 Likely URL/address bar detected")
                return True
                
        # 2. Search boxes and form fields - middle of screen
        if 0.15 <= y <= 0.7:  # Expanded middle section
            if 0.1 <= x <= 0.9:  # Centered horizontally
                print("📝 Possible form field detected")
                return True
        
        # Default to not an input box
        return False

    def reset(self) -> None:
        """Reset the state tracker"""
        self.last_tap_position = None
        self.last_action = None
        self.action_count = {}
        self.must_type_next = False
        self.last_screen_state = None
        self.input_box_tapped = False
        self.consecutive_same_tap_count = 0
        self.last_tap_coords = None 