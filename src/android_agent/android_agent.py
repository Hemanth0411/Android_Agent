"""Android Agent module for automating Android devices.

This module provides the core Android automation functionality including state
management, action planning, and action execution.
"""

import base64
import json
import os
import time
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import random

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
    get_current_app,
    wait_for_keyboard,
    is_keyboard_visible,
    dismiss_keyboard,
    smart_type_text,
    type_text_with_uiautomator2
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
        """Execute an action on the device.
        
        Args:
            action: Action to execute
            
        Returns:
            bool: Whether the action executed successfully
        """
        if not action.action:
            print("❌ Error: No action specified")
            return False
            
        action_type = action.action
        
        try:
            # Print action details
            print(f"\n▶️ Taking action: {action_type}")
            if action.coordinate:
                print(f"📍 Coordinate: {action.coordinate}")
            if action.text:
                print(f"💬 Text: {action.text}")
            if action.key is not None:
                print(f"🔑 Key: {action.key}")
                
            # Record the action in our counter
            if action_type not in self.action_counts:
                self.action_counts[action_type] = 0
            self.action_counts[action_type] += 1
            
            # Handle different action types
            if action_type == AndroidActionType.TAP:
                if not action.coordinate:
                    print("❌ Error: No coordinate specified for tap action")
                    return False
                
                # Get device dimensions
                device_w, device_h = get_device_size(self.adb_path)
                
                # Extract coordinates
                x, y = action.coordinate.x, action.coordinate.y
                
                # Let tap function handle the coordinate scaling
                tap_result = tap(self.adb_path, x, y, device_w, device_h)
                
                if tap_result:
                    # Record input-box tap for subsequent TYPE actions
                    if self.state_tracker._is_input_box(action.coordinate):
                        self.last_input_tap_coords = action.coordinate
                        self.state_tracker.input_box_tapped = True
                    return True
                    
                # If tap failed, try alternative tap location slightly offset
                print("⚠️ First tap failed, trying offset tap...")
                offset = 5  # 5 pixel offset
                tap_result = tap(self.adb_path, x + offset, y + offset, device_w, device_h)
                
                if tap_result:
                    if self.state_tracker._is_input_box(action.coordinate):
                        self.last_input_tap_coords = action.coordinate
                        self.state_tracker.input_box_tapped = True
                    return True
                    
                return False
            elif action_type == AndroidActionType.TYPE:
                if not action.text:
                    print("❌ Error: No text specified for type action")
                    return False
                # Inject text directly via ADB without UIAutomator2
                type_text(self.adb_path, action.text)
                print(f"⌨️ Typed text via ADB shell: '{action.text}'")
                return True
            elif action_type == AndroidActionType.SWIPE_UP:
                swipe_up(self.adb_path, distance=0.5)
            elif action_type == AndroidActionType.SWIPE_DOWN:
                swipe_down(self.adb_path, distance=0.5)
            elif action_type == AndroidActionType.SWIPE:
                if not action.start_coordinate or not action.end_coordinate:
                    print("❌ Error: Start and end coordinates required for swipe action")
                    return False
                start_x, start_y = action.start_coordinate.x, action.start_coordinate.y
                end_x, end_y = action.end_coordinate.x, action.end_coordinate.y
                swipe(self.adb_path, start_x, start_y, end_x, end_y)
            elif action_type == AndroidActionType.PRESS:
                if action.key is None:
                    print("❌ Error: No key specified for press action")
                    return False
                key = action.key
                if key == 4:  # Back button
                    press_back(self.adb_path)
                elif key == 3:  # Home button
                    press_home(self.adb_path)
                else:
                    command = f"{self.adb_path} shell input keyevent {key}"
                    subprocess.run(command, shell=True, check=True)
            elif action_type == AndroidActionType.WAIT:
                # Use at least 5 seconds for wait actions
                duration = action.duration if action.duration is not None else 5
                if duration < 5:
                    duration = 5
                print(f"⏱️ Waiting for {duration} seconds...")
                time.sleep(duration)
            elif action_type == AndroidActionType.LAUNCH_APP:
                if not action.package:
                    print("❌ Error: No package specified for launch_app action")
                    return False
                print(f"🚀 Launching app: {action.package}")
                
                # Special handling for Chrome as it's commonly problematic
                if "chrome" in action.package.lower():
                    print("🌐 Using Chrome-specific launch strategies")
                    
                    # Try different Chrome launch approaches
                    
                    # 1. First try standard launch
                    standard_launch = launch_app(self.adb_path, action.package, action.activity)
                    
                    # 2. If standard launch doesn't work, try alternative methods
                    if not standard_launch:
                        # Try multiple known Chrome package names
                        chrome_packages = [
                            "com.android.chrome",
                            "com.chrome.beta",
                            "com.google.android.apps.chrome",
                            "org.chromium.chrome"
                        ]
                        
                        for pkg in chrome_packages:
                            if pkg != action.package:
                                print(f"🌐 Trying alternative Chrome package: {pkg}")
                                alt_launch = launch_app(self.adb_path, pkg)
                                if alt_launch:
                                    print(f"✅ Successfully launched Chrome with alternative package: {pkg}")
                                    time.sleep(2)  # Wait for Chrome to fully load
                                    return True
                        
                        # If all package attempts fail, try using monkey
                        print("🌐 Trying monkey command for Chrome launch...")
                        monkey_cmd = f"{self.adb_path} shell monkey -p {action.package} -c android.intent.category.LAUNCHER 1"
                        try:
                            result = subprocess.run(monkey_cmd, shell=True, check=False, capture_output=True, text=True)
                            if "Events injected: 1" in result.stdout:
                                print("✅ Chrome launched via monkey command")
                                time.sleep(2)  # Wait for Chrome to fully load
                                return True
                        except Exception as e:
                            print(f"⚠️ Monkey launch failed: {e}")
                    
                    # Check if launch was successful by verifying current app
                    time.sleep(2)  # Give app time to launch
                    current_app = get_current_app(self.adb_path)
                    if "chrome" in current_app.lower():
                        print(f"✅ Chrome launch confirmed - current app: {current_app}")
                        return True
                    else:
                        print(f"⚠️ Chrome may not have launched - current app: {current_app}")
                        return False
                else:
                    # For non-Chrome apps, use standard launch
                    return launch_app(self.adb_path, action.package, action.activity)
            else:
                print(f"❌ Error: Unknown action type: {action_type}")
                return False
                
            # Pause after action if requested
            if self.options.pause_after_each_action:
                input("⏸️ Paused - Press Enter to continue...")
                
            return True
                
        except Exception as e:
            print(f"❌ Error executing action: {e}")
            import traceback
            traceback.print_exc()
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
            
            # Clean up the saved screenshot immediately
            try:
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
                    print(f"✅ Cleaned up screenshot file: {screenshot_path}")
            except Exception as e:
                print(f"⚠️ Failed to clean screenshot file: {e}")
            
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
        repeated_state = self.detect_repeated_state(current_state)
        
        # Save a reference to the last action for loop detection
        last_action_type = None
        if len(self.history) > 0:
            last_action_type = self.history[-1].action.action
            
        # Initialize action counter for TAP if it doesn't exist
        if AndroidActionType.TAP not in self.action_counts:
            self.action_counts[AndroidActionType.TAP] = 0
            
        # Check keyboard state to update the state tracker
        try:
            keyboard_visible = is_keyboard_visible(self.adb_path)
            self.state_tracker.set_keyboard_visible(keyboard_visible)
            print(f"⌨️ Keyboard visible: {keyboard_visible}")
        except Exception as e:
            print(f"⚠️ Error checking keyboard state: {e}")
            
        # If we've hit repeated state and the last few actions were taps,
        # try a different strategy to break out of the loop
        if (repeated_state and last_action_type == AndroidActionType.TAP and 
            self.action_counts[AndroidActionType.TAP] >= 3):
            print("🔄 Detected tap loop - trying alternative action to break out")
            
            # Special case: If we're trying to tap Chrome repeatedly but it's not launching
            chrome_target_detected = (
                "chrome" in str(current_state.current_app).lower() or 
                self._check_for_chrome_ui(current_state.screenshot) or
                (len(self.history) > 0 and self.history[-1].action.coordinate and 
                 self.history[-1].action.coordinate.y > 0.8)  # Bottom of screen tap
            )
                
            if chrome_target_detected:
                print("🌐 Chrome detected in repeated tap loop - trying direct command")
                
                # First try to go home to reset the state
                press_home(self.adb_path)
                time.sleep(1)
                
                # Try direct Chrome launch with am start (most reliable method)
                try:
                    chrome_cmd = f"{self.adb_path} shell am start -a android.intent.action.VIEW -d \"about:blank\" -n com.android.chrome/com.google.android.apps.chrome.Main"
                    subprocess.run(chrome_cmd, shell=True)
                    time.sleep(2)
                    
                    # Check if Chrome launched
                    current_app = get_current_app(self.adb_path)
                    if "chrome" in current_app.lower():
                        print("✅ Chrome directly launched with am start command")
                        # Record as a press home + chrome launch action
                        recovery_action = AndroidAction(
                            action=AndroidActionType.PRESS,
                            key=3  # Home key
                        )
                        self.history.append(AndroidStep(state=current_state, action=recovery_action))
                        return
                except Exception as e:
                    print(f"⚠️ Chrome direct launch failed: {e}")
                
                # Try with monkey command as fallback
                try:
                    print("🌐 Trying monkey command to launch Chrome")
                    monkey_cmd = f"{self.adb_path} shell monkey -p com.android.chrome -c android.intent.category.LAUNCHER 1"
                    subprocess.run(monkey_cmd, shell=True)
                    time.sleep(2)
                    
                    # Record as a successful recovery
                    recovery_action = AndroidAction(
                        action=AndroidActionType.TAP,
                        coordinate=Coordinate(x=500, y=500),  # Generic coordinate since we used monkey
                        text="Chrome launch via monkey"
                    )
                    self.history.append(AndroidStep(state=current_state, action=recovery_action))
                    return
                except Exception as e:
                    print(f"⚠️ Chrome monkey command failed: {e}")
            
            # First check if keyboard is visible
            try:
                if is_keyboard_visible(self.adb_path):
                    print("⌨️ Keyboard is visible but stuck in tap loop - attempting to type")
                    # Try typing a search term as a recovery action
                    recovery_action = AndroidAction(
                        action=AndroidActionType.TYPE,
                        text="search"
                    )
                    self._take_action(recovery_action)
                    # Record this action
                    self.history.append(AndroidStep(state=current_state, action=recovery_action))
                    return
            except Exception:
                pass
                
            # Check if we have coordinates of a possible input field from previous taps
            if hasattr(self, 'last_input_tap_coords') and self.last_input_tap_coords:
                print("🔄 Trying UIAutomator2 direct input as loop-breaking strategy")
                recovery_text = "search"
                x, y = self.last_input_tap_coords.x, self.last_input_tap_coords.y
                
                try:
                    # Try using UIAutomator2 to input text directly
                    if type_text_with_uiautomator2(self.adb_path, recovery_text, x, y):
                        print("✅ Successfully used UIAutomator2 to break out of loop")
                        # Record as a type action
                        recovery_action = AndroidAction(
                            action=AndroidActionType.TYPE,
                            text=recovery_text
                        )
                        self.history.append(AndroidStep(state=current_state, action=recovery_action))
                        return
                except Exception as e:
                    print(f"⚠️ UIAutomator2 loop-breaking failed: {e}")
            
            # Try pressing back as a recovery action
            print("⬅️ Trying BACK button to break out of loop")
            recovery_action = AndroidAction(
                action=AndroidActionType.PRESS,
                key=4  # Back key
            )
            self._take_action(recovery_action)
            # Record this action
            self.history.append(AndroidStep(state=current_state, action=recovery_action))
            return
        
        # Get next action from planner
        print(f"\n🧠 Determining next action (step {len(self.history) + 1}/{self.options.max_steps})...")
        
        # Save screenshot to file if requested
        if self.options.screenshot_dir:
            # Create filename with timestamp and step number
            timestamp = int(time.time())
            filename = f"{self.options.screenshot_dir}/step_{len(self.history) + 1:02d}_{timestamp}.png"
            try:
                take_screenshot(self.adb_path, filename)
                print(f"📸 Saved screenshot to {filename}")
            except Exception as e:
                print(f"⚠️ Failed to save screenshot: {e}")
                
        next_action = self.planner.plan_action(
            self.goal,
            self.options.additional_context,
            self.options.additional_instructions,
            current_state,
            self.history
        )
        
        if not next_action:
            print("❌ Failed to determine next action")
            self.update_status(AndroidGoalState.FAILED)
            return
            
        # Record that we're starting a specific action
        action_desc = f"{next_action.action}"
        if next_action.action == AndroidActionType.TAP and next_action.coordinate:
            action_desc = f"{next_action.action} at ({next_action.coordinate.x:.0f}, {next_action.coordinate.y:.0f})"
        elif next_action.action == AndroidActionType.TYPE and next_action.text:
            action_desc = f"{next_action.action} \"{next_action.text}\""
            
        print(f"🤖 Next action: {action_desc}")
        
        # Check if we've reached a success or failure action
        if next_action.action == AndroidActionType.SUCCESS:
            print("🎯 Goal reached!")
            self.update_status(AndroidGoalState.SUCCESS)
            return
        elif next_action.action == AndroidActionType.FAILURE:
            print("❌ Failed to achieve goal")
            self.update_status(AndroidGoalState.FAILED)
            return
        
        # Special case for opening Chrome - only when on the launcher
        if next_action.action == AndroidActionType.TAP:
            is_chrome_target = False
            # Only treat taps as Chrome-launch when on the launcher dock area
            if "launcher" in str(current_state.current_app).lower():
                # If tap is in the bottom dock region, assume Chrome icon
                if next_action.coordinate and next_action.coordinate.y > 0.8:
                    is_chrome_target = True
            
            if is_chrome_target:
                print("🌐 Detected possible Chrome icon tap - trying Chrome-specific strategies")
                
                # First, try a specialized Chrome launch command (more reliable than LAUNCH_APP)
                # This uses am start with the explicit Chrome launcher activity
                chrome_launch_cmd = f"{self.adb_path} shell am start -a android.intent.action.VIEW -d \"about:blank\" -n com.android.chrome/com.google.android.apps.chrome.Main"
                
                try:
                    print("🌐 Executing Chrome-specific launch command...")
                    result = subprocess.run(chrome_launch_cmd, shell=True, capture_output=True, text=True)
                    
                    if result.returncode == 0 and "Error" not in result.stdout:
                        print("✅ Chrome-specific launch command successful")
                        time.sleep(2)  # Give Chrome time to start
                        
                        # Record this as a successful tap action
                        self.history.append(AndroidStep(
                            state=current_state,
                            action=next_action
                        ))
                        return
                    else:
                        print(f"⚠️ Chrome-specific launch failed: {result.stderr}")
                except Exception as e:
                    print(f"⚠️ Error launching Chrome: {e}")
                
                # If direct command failed, try alternative Chrome packages
                chrome_packages = [
                    "com.android.chrome",
                    "com.chrome.beta",
                    "com.google.android.apps.chrome",
                ]
                
                for package in chrome_packages:
                    try:
                        print(f"🌐 Trying to launch {package}...")
                        alt_cmd = f"{self.adb_path} shell monkey -p {package} -c android.intent.category.LAUNCHER 1"
                        result = subprocess.run(alt_cmd, shell=True, capture_output=True, text=True)
                        
                        if "Events injected: 1" in result.stdout:
                            print(f"✅ Successfully launched Chrome via {package}")
                            time.sleep(2)
                            
                            # Record this as a successful tap action
                            self.history.append(AndroidStep(
                                state=current_state,
                                action=next_action
                            ))
                            return
                    except Exception as e:
                        print(f"⚠️ Error with alternative Chrome launch: {e}")
                
                print("🔍 Falling back to standard tap method")
                # Continue with original tap action below
            
        # Execute the action
        action_result = self._take_action(next_action)
        
        # If the action failed to execute, mark step as failed
        if not action_result:
            print("❌ Action failed to execute")
            next_action.failed = True
            
        # Record the step with the current state and action taken
        self.history.append(AndroidStep(
            state=current_state,
            action=next_action
        ))
        
        # Check if we've reached the maximum steps
        if len(self.history) >= self.options.max_steps:
            print("⚠️ Maximum number of steps reached")
            self.update_status(AndroidGoalState.FAILED)
    
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

    def update_status(self, new_status: AndroidGoalState) -> None:
        """Update the current status of the automation.
        
        Args:
            new_status: New status to set
        """
        self._status = new_status