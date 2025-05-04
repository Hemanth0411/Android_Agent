"""Android state tracker module.

Tracks the state of Android automation to help prevent loops and errors.
"""
from typing import Optional, Tuple, List, Dict, Union
from .android_action import AndroidActionType, Coordinate

class AndroidStateTracker:
    def __init__(self):
        self.last_tap_position = None
        self.last_action = None
        self.action_count = {}
        self.max_attempts = 10  # Increased from 5 to 10 for more tolerance
        self.must_type_next = False
        self.last_screen_state = None
        self.input_box_tapped = False  # Flag to track if we tapped an input box
        self.keyboard_visible = False  # Flag to track if keyboard is currently visible
        # Add regions where UI is expected to be different from inputs
        self.app_icon_regions = [
            (0, 0.8, 1.0, 1.0),  # Bottom 20% where app icons typically are
            (0, 0, 1.0, 0.08)    # Top status bar area
        ]
        self.consecutive_same_tap_count = 0
        self.last_tap_coords = None
        self.known_input_regions = self._init_known_input_regions()
        self.typing_attempted = False   # Flag to track if typing was already attempted
        self.last_tap_was_input = False # Track if last tap was on an input field
        
    def _init_known_input_regions(self) -> Dict[str, List[Tuple[float, float, float, float]]]:
        """Initialize known input regions for common apps.
        
        Returns:
            Dictionary mapping app names to lists of input regions
        """
        return {
            "com.android.chrome": [
                (0.05, 0.03, 0.95, 0.15),  # URL bar area (expanded)
                (0.05, 0.2, 0.95, 0.4),    # Google search box area (expanded)
                (0.05, 0.4, 0.95, 0.6)     # Possible forms in content area
            ],
            "com.google.android.gm": [  # Gmail
                (0.05, 0.1, 0.95, 0.3),   # Search bar
                (0.05, 0.3, 0.95, 0.9)    # Email composition area
            ],
            "com.android.messaging": [  # Messaging
                (0.05, 0.8, 0.8, 0.95)    # Message input area
            ],
            # Add more apps as needed
        }

    def update_state(self, action: AndroidActionType, coordinate: Optional[Union[Tuple[float, float], 'Coordinate']] = None, text: Optional[str] = None) -> bool:
        """Update the state tracker with a new action.
        
        Args:
            action: The type of action being performed
            coordinate: Optional coordinate for tap actions (tuple or Coordinate object)
            text: Optional text for type actions
            
        Returns:
            bool: Whether the action should be allowed
        """
        # Update action count
        if action not in self.action_count:
            self.action_count[action] = 0
        self.action_count[action] += 1
        
        # Handle TYPE action specially - we want to be more permissive
        if action == AndroidActionType.TYPE:
            # If keyboard is visible or we recently tapped an input field, always allow typing
            if self.keyboard_visible or self.input_box_tapped or self.last_tap_was_input:
                print("⌨️ Type action allowed - keyboard visible or input field tapped")
                self.typing_attempted = True
                return True
                
            # If a type action was recently blocked, try again but warn
            if self.typing_attempted:
                print("⚠️ Multiple type attempts without keyboard, but allowing anyway")
                return True
                
            # First time trying to type without visible keyboard
            print("⚠️ Type action requested but no input field tapped first")
            self.typing_attempted = True
            # Be permissive and allow it anyway
            return True
        
        # Reset typing flag for non-type actions
        if action != AndroidActionType.TYPE:
            self.typing_attempted = False
            
        # Special handling for exact same tap location to avoid being stuck clicking the same spot
        if action == AndroidActionType.TAP and coordinate:
            if self.last_tap_coords == coordinate:
                self.consecutive_same_tap_count += 1
                # Allow more repeated taps before blocking
                if self.consecutive_same_tap_count > 5:  # Increased from 3 to 5
                    print(f"⚠️ Detected exactly same tap position {self.consecutive_same_tap_count} times")
                    # Allow more attempts before blocking
                    if self.consecutive_same_tap_count > 8:  # Increased from 5 to 8
                        print("❌ Too many identical taps, trying to break out of loop")
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
                if action == AndroidActionType.TAP and self.consecutive_same_tap_count > 5:
                    print(f"⚠️ Excessive same-location taps detected. Blocking to avoid loop.")
                    return False
                print(f"⚠️ Many repeated {action} actions, but allowing to continue")
        
        # Special handling for input box taps - improved detection
        if action == AndroidActionType.TAP and coordinate:
            # Check if the coordinate is a Coordinate object or a tuple
            is_input = self._is_input_box(coordinate)
            self.last_tap_was_input = is_input
            
            if is_input:
                print(f"🖋️ Detected tap on input field at {coordinate}")
                self.input_box_tapped = True
                self.must_type_next = True
                
                # Set flag for keyboard checks
                self.keyboard_visible = True  # Optimistically set true, will be verified later
            else:
                print(f"👆 Tapped non-input area at {coordinate}")
                # Don't immediately reset these flags - keep them for one more action
                # This allows for slight mistakes in input detection
        elif action == AndroidActionType.TYPE:
            # After typing, we should reset the input box tapped flag
            self.input_box_tapped = False
            self.must_type_next = False
            
            # After typing, keyboard probably disappears depending on the app
            # This will be verified by keyboard detection in the agent
        
        # Update last action
        self.last_action = action
        if coordinate:
            self.last_tap_position = coordinate
            
        return True

    def _is_input_box(self, coordinate: Union[Tuple[float, float], 'Coordinate']) -> bool:
        """Detect if the tapped area is likely an input box.
        
        Args:
            coordinate: Normalized x,y coordinates (0-1) or Coordinate object
            
        Returns:
            bool: Whether the coordinate is likely an input box
        """
        # Handle both tuple coordinates and Coordinate objects
        if hasattr(coordinate, 'x') and hasattr(coordinate, 'y'):
            # It's a Coordinate object
            x, y = coordinate.x, coordinate.y
        else:
            # It's a tuple
            x, y = coordinate[0], coordinate[1]
        
        # Normalize coordinates if needed
        if isinstance(x, (int, float)) and x > 1:
            x /= 1000.0  # Normalize to 0-1 range if needed
        if isinstance(y, (int, float)) and y > 1:
            y /= 1000.0  # Normalize to 0-1 range if needed
        
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
            if 0.05 <= x <= 0.95:  # Centered horizontally, wider range
                print("📝 Likely URL/address bar detected")
                return True
                
        # 2. Search boxes and form fields - middle of screen
        if 0.15 <= y <= 0.85:  # Expanded middle section even more
            if 0.05 <= x <= 0.95:  # Centered horizontally, wider range
                print("📝 Possible form field detected")
                return True
        
        # 3. Bottom text input areas (common in chat apps)
        if 0.75 <= y <= 0.95:
            if 0.05 <= x <= 0.8:  # Left side of bottom (typical text input)
                print("📝 Possible chat/message input field detected")
                return True
        
        # Default to not an input box
        return False
        
    def set_keyboard_visible(self, visible: bool) -> None:
        """Set keyboard visibility flag.
        
        Args:
            visible: Whether keyboard is visible
        """
        self.keyboard_visible = visible
        print(f"⌨️ Keyboard visibility set to: {visible}")
        
        # If keyboard becomes visible, this confirms we're in an input field
        if visible:
            self.input_box_tapped = True
            self.must_type_next = True
            self.last_tap_was_input = True

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
        self.keyboard_visible = False
        self.typing_attempted = False
        self.last_tap_was_input = False 