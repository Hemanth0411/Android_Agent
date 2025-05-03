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
    
    def _take_action(self, action: AndroidAction) -> None:
        """Execute an action with state tracking and validation."""
        print(f"DEBUG: Next action: {action.action}, coordinate: {getattr(action, 'coordinate', None)}, text: {getattr(action, 'text', None)}")
        
        try:
            if action.action == AndroidActionType.SCREENSHOT:
                pass
            elif action.action == AndroidActionType.TAP:
                if not action.coordinate:
                    raise ValueError("Coordinate is required for tap action")
                if not self.state_tracker.update_state(AndroidActionType.TAP, coordinate=(action.coordinate.x, action.coordinate.y)):
                    print("Redundant tap detected. Skipping...")
                    return
                tap(self.adb_path, action.coordinate.x, action.coordinate.y)
                
                # If we tapped an input box, ensure the next action is typing
                if self.state_tracker.input_box_tapped:
                    print("Input box tapped - next action must be typing")
            elif action.action == AndroidActionType.TYPE:
                if not action.text:
                    raise ValueError("Text is required for type action")
                if not self.state_tracker.update_state(AndroidActionType.TYPE, text=action.text):
                    print("Type action not allowed: must type immediately after tap on input field.")
                    return
                type_text(self.adb_path, action.text)
            elif action.action == AndroidActionType.PRESS:
                if not action.key:
                    raise ValueError("Key is required for press action")
                if not self.state_tracker.update_state(AndroidActionType.PRESS):
                    print("Redundant press detected. Skipping...")
                    return
                press_back(self.adb_path) if action.key == 4 else press_home(self.adb_path)
            elif action.action == AndroidActionType.SWIPE:
                if not action.swipe:
                    raise ValueError("Swipe coordinates are required for swipe action")
                if not self.state_tracker.update_state(AndroidActionType.SWIPE):
                    print("Redundant swipe detected. Skipping...")
                    return
                swipe(
                    self.adb_path,
                    action.swipe.start.x,
                    action.swipe.start.y,
                    action.swipe.end.x,
                    action.swipe.end.y,
                    action.swipe.duration
                )
        except Exception as e:
            print(f"Error in _take_action: {e}")
            raise
    
    def get_state(self) -> AndroidState:
        """Capture current device state including screenshot.
        
        Returns:
            Current state of the Android device
        """
        # Get device dimensions
        width, height = get_device_size(self.adb_path)
        
        # Generate a timestamp for the screenshot filename
        timestamp = int(time.time())
        screenshot_path = os.path.join(self.options.screenshot_dir, f"screenshot_{timestamp}.png")
        
        # Take screenshot
        take_screenshot(self.adb_path, screenshot_path)
        
        # Get current app
        current_app = get_current_app(self.adb_path)
        
        # Read screenshot and convert to base64
        with open(screenshot_path, "rb") as image_file:
            screenshot_base64 = base64.b64encode(image_file.read()).decode('utf-8')
        
        return AndroidState(
            screenshot=screenshot_base64,
            height=height,
            width=width,
            current_app=current_app,
            timestamp=time.time()
        )
    
    def get_state_hash(self, state: AndroidState) -> str:
        """Generate a hash of the current state to detect repeated states."""
        return f"{state.current_app}:{state.width}:{state.height}"
    
    def detect_repeated_state(self, current_state: AndroidState) -> bool:
        """Detect if we're stuck in a repeated state."""
        current_hash = self.get_state_hash(current_state)
        if current_hash == self.last_state_hash:
            self.repeated_states += 1
            return self.repeated_states >= self.max_repeated_states
        else:
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
            print("Detected repeated state - trying alternative approach")
            self._status = AndroidGoalState.FAILED
            return
        
        # Get next action from planner
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
            print("Goal achieved successfully!")
            return
        elif next_action.action == AndroidActionType.FAILURE:
            self._status = AndroidGoalState.FAILED
            print("Failed to achieve goal.")
            return
        else:
            self._status = AndroidGoalState.RUNNING
        
        # Update action counts
        self.action_counts[next_action.action] += 1
        
        # Check for excessive use of the same action type
        if self.action_counts[next_action.action] > 5:
            print(f"Warning: Excessive use of {next_action.action} action")
            self._status = AndroidGoalState.FAILED
            return
        
        # Execute the action
        self._take_action(next_action)
        
        # Record this step in history
        self.history.append(AndroidStep(state=current_state, action=next_action))
        
        # Pause if configured to do so
        if self.options.pause_after_each_action:
            input("Press Enter to continue...")
    
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

    def _initialize_device(self):
        """Initialize ADB connection to the device"""
        # Implementation details...
        pass

    def _get_current_state(self):
        """Get current state of the device"""
        # Implementation details...
        pass

    def _is_goal_achieved(self):
        """Check if the goal has been achieved"""
        # Implementation details...
        pass 