"""Android Agent module for automating Android devices.

This module provides the core Android automation functionality including state
management, action planning, and action execution.
"""

import base64
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from .android_controller import (
    get_device_size,
    take_screenshot,
    get_screenshot_base64,
    tap,
    swipe,
    swipe_up,
    swipe_down,
    type_text,
    press_back,
    press_home,
    launch_app,
    get_current_app
)
from .android_action import AndroidAction, AndroidActionType, Coordinate, SwipeCoordinates
from .state_tracker import AndroidStateTracker
from .android_state import AndroidState
from .android_step import AndroidStep


class AndroidGoalState(str, Enum):
    """Enumeration of Android automation states.
    
    This enum represents the possible states of an Android automation task.
    """
    INITIAL = "initial"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class AndroidAgentOptions:
    """Configuration options for AndroidAgent.
    
    Attributes:
        additional_context: Extra context information
        additional_instructions: Extra instructions for planner
        pause_after_each_action: Whether to pause after each action
        max_steps: Maximum number of steps before stopping
        screenshot_dir: Directory to save screenshots
    """
    additional_context: Optional[Union[str, Dict[str, Any]]] = None
    additional_instructions: Optional[List[str]] = None
    pause_after_each_action: bool = False
    max_steps: int = 50
    screenshot_dir: str = "screenshots"


class AndroidAgent:
    """Main agent class for Android automation.
    
    Manages interaction between device, planner and state to
    achieve user goals through automated Android interactions.
    
    Attributes:
        adb_path: Path to ADB executable
        planner: Action planner to determine next actions
        goal: Goal to achieve
        options: Configuration options
        _status: Current status of the automation
        history: History of previous actions and states
        action_counts: Dictionary to track action usage
        last_state_hash: Hash of the last state for repeated state detection
        repeated_states: Counter for repeated states
        max_repeated_states: Maximum allowed repeated states
        state_tracker: State tracker for action tracking
        device: ADB connection to the device
    """
    
    def __init__(
        self,
        adb_path: str,
        action_planner: Any,
        goal: str,
        options: Optional[AndroidAgentOptions] = None
    ) -> None:
        """Initialize the Android agent.
        
        Args:
            adb_path: Path to ADB executable
            action_planner: Planner to determine next actions
            goal: Goal to achieve
            options: Configuration options
        """
        self.adb_path = adb_path
        self.planner = action_planner
        self.goal = goal
        self.options = options or AndroidAgentOptions()
        self.state_tracker = AndroidStateTracker()
        self._status = AndroidGoalState.INITIAL
        self.history: List[AndroidStep] = []
        self.action_counts: Dict[AndroidActionType, int] = {action_type: 0 for action_type in AndroidActionType}
        self.last_state_hash: Optional[str] = None
        self.repeated_states: int = 0
        self.max_repeated_states: int = 3
        self.device = None
    
    def _take_action(self, action: AndroidAction) -> bool:
        """Execute an action with state tracking and validation.
        
        Args:
            action: The action to execute
            
        Returns:
            bool: Whether the action was successful
        """
        print(f"DEBUG: Next action: {action.action}, coordinate: {getattr(action, 'coordinate', None)}, text: {getattr(action, 'text', None)}")
        
        try:
            if action.action == AndroidActionType.SCREENSHOT:
                return True
                
            elif action.action == AndroidActionType.TAP:
                if not action.coordinate:
                    print("❌ Error: Coordinate is required for tap action")
                    return False
                    
                # Check if we're tapping near the bottom of the screen (likely app icon)
                is_app_icon = False
                # Check bottom 15% of screen for app icons
                if action.coordinate.y > 0.85:
                    print("🔍 Tap detected at bottom of screen - likely app icon/navigation")
                    is_app_icon = True
                    
                if not self.state_tracker.update_state(action.action, coordinate=(action.coordinate.x, action.coordinate.y)):
                    print("⚠️ Redundant tap detected. Skipping...")
                    return False
                    
                # Execute tap and get success/failure
                tap_success = tap(self.adb_path, action.coordinate.x, action.coordinate.y)
                
                # If tap failed, report back
                if not tap_success:
                    print("❌ Tap action failed")
                    return False
                
                # For app icons, wait a bit longer for app to launch
                if is_app_icon:
                    print("⏳ Waiting for app to launch...")
                    time.sleep(1.5)  # Extra wait time for app launch
                
                # If we tapped an input box, note for next action
                if self.state_tracker.input_box_tapped:
                    print("🖋️ Input box tapped - next action should be typing")
                
                return True
                
            elif action.action == AndroidActionType.TYPE:
                if not action.text:
                    print("❌ Error: Text is required for type action")
                    return False
                    
                if not self.state_tracker.update_state(action.action, text=action.text):
                    print("⚠️ Type action not allowed: must tap input field first")
                    return False
                    
                try:
                    type_text(self.adb_path, action.text)
                    print(f"⌨️ Typed text: '{action.text}'")
                    return True
                except Exception as e:
                    print(f"❌ Error typing text: {e}")
                    return False
                    
            elif action.action == AndroidActionType.PRESS:
                if not action.key:
                    print("❌ Error: Key is required for press action")
                    return False
                    
                if not self.state_tracker.update_state(action.action):
                    print("⚠️ Redundant press detected. Skipping...")
                    return False
                    
                try:
                    if action.key == 4:
                        press_back(self.adb_path)
                        print("⬅️ Pressed BACK button")
                    else:
                        press_home(self.adb_path)
                        print("🏠 Pressed HOME button")
                    return True
                except Exception as e:
                    print(f"❌ Error pressing key: {e}")
                    return False
                    
            elif action.action == AndroidActionType.SWIPE:
                if not action.swipe:
                    print("❌ Error: Swipe coordinates are required for swipe action")
                    return False
                    
                if not self.state_tracker.update_state(action.action):
                    print("⚠️ Redundant swipe detected. Skipping...")
                    return False
                    
                try:
                    swipe(
                        self.adb_path,
                        action.swipe.start.x,
                        action.swipe.start.y,
                        action.swipe.end.x,
                        action.swipe.end.y,
                        action.swipe.duration
                    )
                    print(f"↔️ Swiped from ({action.swipe.start.x}, {action.swipe.start.y}) to ({action.swipe.end.x}, {action.swipe.end.y})")
                    return True
                except Exception as e:
                    print(f"❌ Error during swipe: {e}")
                    return False
                    
            elif action.action == AndroidActionType.SWIPE_UP:
                try:
                    swipe_up(self.adb_path)
                    print("⬆️ Swiped UP")
                    return True
                except Exception as e:
                    print(f"❌ Error swiping up: {e}")
                    return False
                    
            elif action.action == AndroidActionType.SWIPE_DOWN:
                try:
                    swipe_down(self.adb_path)
                    print("⬇️ Swiped DOWN")
                    return True
                except Exception as e:
                    print(f"❌ Error swiping down: {e}")
                    return False
                    
            elif action.action == AndroidActionType.LAUNCH_APP:
                if not action.text:
                    print("❌ Error: App package name is required for launch action")
                    return False
                    
                try:
                    launch_app(self.adb_path, action.text)
                    print(f"🚀 Launched app: {action.text}")
                    return True
                except Exception as e:
                    print(f"❌ Error launching app: {e}")
                    return False
            else:
                print(f"⚠️ Unknown action type: {action.action}")
                return False
                
        except Exception as e:
            print(f"❌ Error in _take_action: {e}")
            return False
    
    def get_state(self) -> AndroidState:
        """Capture current device state including screenshot.
        
        Returns:
            Current state of the Android device
        
        This implementation is inspired by Cerebellum's screenshot handling:
        - Uses a memory-efficient approach
        - Cleans up temporary files immediately
        - Maintains a organized screenshot directory structure
        """
        print("🔄 Capturing device state...")
        
        try:
            # Get device dimensions
            width, height = get_device_size(self.adb_path)
            print(f"📱 Device size: {width}x{height}")
            
            # Create screenshots directory with date-based subdirectory
            timestamp = int(time.time())
            date_str = time.strftime('%Y%m%d')
            screenshot_dir = os.path.join(self.options.screenshot_dir, date_str)
            os.makedirs(screenshot_dir, exist_ok=True)
            
            # Generate unique filename for this screenshot
            screenshot_path = os.path.join(screenshot_dir, f"screen_{timestamp}.png")
            
            # Take screenshot directly to memory using base64
            print(f"📸 Taking screenshot...")
            screenshot_base64 = get_screenshot_base64(self.adb_path, screenshot_path)
            print(f"✅ Screenshot captured: {len(screenshot_base64)//1024}KB in base64")
            
            # Check if we see Chrome UI elements in the screenshots
            # This is a fallback to help with app detection
            chrome_visually_detected = self._check_for_chrome_ui(screenshot_base64)
            
            # Get current app - retry up to 3 times if we get "unknown"
            current_app = "unknown"
            retries = 0
            while current_app == "unknown" and retries < 3:
                if retries > 0:
                    print(f"🔄 Retrying app detection (attempt {retries+1}/3)...")
                    time.sleep(0.5)  # Wait a bit before retry
                current_app = get_current_app(self.adb_path)
                
                # If Chrome was visually detected but app detection failed,
                # manually override the app name
                if current_app == "unknown" or "launcher" in current_app.lower():
                    if chrome_visually_detected:
                        print("🔎 Chrome UI detected in screenshot, overriding app detection")
                        current_app = "com.android.chrome"
                        break
                    
                retries += 1
                
            print(f"📱 Current app: {current_app}")
            
            # Create state object
            return AndroidState(
                screenshot=screenshot_base64,
                height=height,
                width=width,
                current_app=current_app,
                timestamp=timestamp
            )
            
        except Exception as e:
            print(f"❌ Error capturing device state: {e}")
            # Provide basic state if we can't get full state
            try:
                # Try to get just the app info as a fallback
                current_app = get_current_app(self.adb_path)
                print(f"📱 Fallback - Current app: {current_app}")
                
                # Return minimal state (without screenshot)
                return AndroidState(
                    screenshot="",
                    height=1080,  # Default values
                    width=1920,
                    current_app=current_app,
                    timestamp=int(time.time())
                )
            except Exception as inner_e:
                print(f"❌ Fatal error capturing device state: {inner_e}")
                raise
    
    def _check_for_chrome_ui(self, screenshot_base64: str) -> bool:
        """Check if the screenshot contains Chrome UI elements.
        
        This is a simple visual check to help with app detection when ADB
        methods fail to correctly identify Chrome.
        
        Args:
            screenshot_base64: Base64 encoded screenshot
            
        Returns:
            Whether Chrome UI elements were detected
        """
        # This is a very basic implementation - a real solution would use
        # image recognition or OCR to detect Chrome UI elements
        
        # For now, just check if we detect Chrome UI elements in the planner's observation
        if hasattr(self, 'planner') and hasattr(self.planner, 'last_observation'):
            last_obs = getattr(self.planner, 'last_observation', "")
            chrome_indicators = [
                "chrome", "address bar", "url bar", "search bar", 
                "google search", "google.com", "browser"
            ]
            
            for indicator in chrome_indicators:
                if indicator.lower() in last_obs.lower():
                    print(f"🔍 Chrome UI indicator detected: '{indicator}'")
                    return True
                
        # If we have history, check the last observation
        if self.history and len(self.history) > 0:
            last_step = self.history[-1]
            last_app = last_step.state.current_app if last_step and last_step.state else None
            
            if last_app and "chrome" in last_app.lower():
                print("🔍 Chrome was detected in the previous step")
                return True
            
        return False
    
    def get_state_hash(self, state: AndroidState) -> str:
        """Generate a hash of the current state to detect repeated states.
        
        Args:
            state: Current device state
            
        Returns:
            A string hash representing the state
        """
        # Include timestamp to prevent very rapid repeated states from being detected
        # Round to nearest 10 seconds to allow for moderate differences
        time_bucket = int(state.timestamp / 10) * 10
        
        # Create a hash that includes multiple state aspects
        hash_components = [
            f"app:{state.current_app}",
            f"time:{time_bucket}",
            f"dimensions:{state.width}x{state.height}"
        ]
        
        # Consider more factors for repeated state detection
        is_home_or_unknown = ("launcher" in state.current_app.lower() or 
                             state.current_app == "unknown" or
                             "com.android.systemui" in state.current_app.lower())
                             
        # Add an incrementing counter for home screen to allow more attempts
        if is_home_or_unknown:
            # Use a larger counter for home screens
            self.home_screen_attempts = getattr(self, 'home_screen_attempts', 0) + 1
            hash_components.append(f"home_attempt:{self.home_screen_attempts % 5}")
        else:
            # Reset home screen counter when in a real app
            self.home_screen_attempts = 0
        
        # Add a random component to allow some variation for special cases
        # like scrolling where the app remains the same
        action_chain = getattr(self, 'last_actions', [])
        if action_chain and action_chain[-1] in [AndroidActionType.SWIPE_UP, AndroidActionType.SWIPE_DOWN]:
            # If last action was scrolling, add some tolerance
            import random
            hash_components.append(f"scroll:{random.randint(1, 3)}")
        
        # Store the last 3 actions to detect patterns
        if not hasattr(self, 'last_actions'):
            self.last_actions = []
        if len(self.history) > 0 and self.history[-1].action.action:
            self.last_actions.append(self.history[-1].action.action)
            if len(self.last_actions) > 3:
                self.last_actions.pop(0)
        
        return ":".join(hash_components)
    
    def detect_repeated_state(self, current_state: AndroidState) -> bool:
        """Detect if we're stuck in a repeated state.
        
        Args:
            current_state: Current device state
            
        Returns:
            bool: Whether we're stuck in a repeated state
        """
        current_hash = self.get_state_hash(current_state)
        
        # If the current state is a launcher or "unknown", be more lenient
        is_home_or_unknown = ("launcher" in current_state.current_app.lower() or 
                              current_state.current_app == "unknown")
        
        # Determine max attempts based on app type
        if "chrome" in current_state.current_app.lower():
            # Special exception for Chrome - Allow even more attempts
            max_attempts = self.max_repeated_states * 3
            print(f"🔍 Chrome detected - allowing more repeated states ({max_attempts})")
        elif is_home_or_unknown:
            # For home screen, allow more attempts
            max_attempts = self.max_repeated_states * 2
        else:
            max_attempts = self.max_repeated_states
        
        if current_hash == self.last_state_hash:
            self.repeated_states += 1
            print(f"⚠️ Detected repeated state ({self.repeated_states}/{max_attempts})")
            if self.repeated_states >= max_attempts:
                print(f"❌ Maximum repeated states reached ({max_attempts})")
                return True
        else:
            print(f"✅ State changed: {self.last_state_hash} → {current_hash}")
            self.last_state_hash = current_hash
            self.repeated_states = 0
            
        return False
    
    def step(self) -> None:
        """Execute a single automation step.
        
        Gets current state, determines next action, executes it,
        and updates history.
        """
        # Get current state
        current_state = self.get_state()
        
        # Check for repeated states
        if self.detect_repeated_state(current_state):
            print("❌ Detected repeated state - trying alternative approach")
            self._status = AndroidGoalState.FAILED
            return
        
        # Get next action from planner
        print("⏳ Planning next action...")
        next_action = self.planner.plan_action(
            self.goal,
            self.options.additional_context,
            self.options.additional_instructions,
            current_state,
            self.history
        )
        
        # Check if goal has been achieved or failed
        if next_action.action == AndroidActionType.SUCCESS:
            self._status = AndroidGoalState.SUCCESS
            print("✅ Goal achieved successfully!")
            return
        elif next_action.action == AndroidActionType.FAILURE:
            self._status = AndroidGoalState.FAILED
            print("❌ Failed to achieve goal.")
            return
        else:
            self._status = AndroidGoalState.RUNNING
        
        # Update action counts
        self.action_counts[next_action.action] += 1
        
        # Check for excessive use of the same action type
        if self.action_counts[next_action.action] > 5:
            print(f"⚠️ Warning: Excessive use of {next_action.action} action")
            self._status = AndroidGoalState.FAILED
            return
        
        # Execute the action
        action_success = self._take_action(next_action)
        
        # Record this step in history regardless of success (to learn from failures)
        self.history.append(AndroidStep(state=current_state, action=next_action))
        
        # Pause if configured to do so
        if self.options.pause_after_each_action:
            input("Press Enter to continue...")
            
        # Handle action failure
        if not action_success:
            print("❌ Action failed, but will try again with a different approach")
            # Set flag to force the planner to try something different next time
            self.repeated_states = self.max_repeated_states - 1
            return
    
    def start(self) -> None:
        """Start the Android automation process.
        
        Runs steps until goal is achieved, maximum steps reached,
        or failure occurs.
        """
        print(f"Starting Android Agent with goal: {self.goal}")
        print(f"Maximum steps: {self.options.max_steps}")
        
        step_count = 0
        while (
            self._status in (AndroidGoalState.INITIAL, AndroidGoalState.RUNNING) and
            step_count < self.options.max_steps
        ):
            print(f"\nStep {step_count + 1}/{self.options.max_steps}")
            self.step()
            step_count += 1
        
        if self._status == AndroidGoalState.RUNNING:
            print(f"Reached maximum number of steps ({self.options.max_steps})")
        
        print(f"Final status: {self._status.value}")
        print("\nAction statistics:")
        for action_type, count in self.action_counts.items():
            if count > 0:
                print(f"{action_type}: {count} times")
    
    @property
    def status(self) -> AndroidGoalState:
        """Get current status of the automation.
        
        Returns:
            Current status as AndroidGoalState
        """
        return self._status