"""OpenAI vision-based planner for Android automation.

This module provides a planner that uses OpenAI's API to analyze screenshots
and determine appropriate actions to achieve user goals on Android devices.
"""

import json
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI

from .base_planner import ActionPlanner
from .android_action import AndroidAction, AndroidActionType, Coordinate
from .android_state import AndroidState
from .android_step import AndroidStep


@dataclass
class OpenAIPlannerOptions:
    """Options for configuring the OpenAI planner.
    
    Attributes:
        api_key: OpenAI API key
        model: OpenAI model to use
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens in response
        debug: Whether to print debug information
    """
    api_key: Optional[str] = None
    model: str = "gpt-4"
    temperature: float = 0.2
    max_tokens: int = 1000
    debug: bool = False


class OpenAIPlanner(ActionPlanner):
    """Action planner using OpenAI's vision model.
    
    This planner uses OpenAI's vision capabilities to analyze
    screenshots and determine appropriate actions to achieve
    user goals on Android devices.
    
    Attributes:
        client: OpenAI client instance
        model: Model to use for API calls
        temperature: Sampling temperature for generation
        max_tokens: Maximum tokens in response
        debug: Whether to print debug info
    """
    
    def __init__(self, options: OpenAIPlannerOptions) -> None:
        """Initialize the OpenAI planner.
        
        Args:
            options: Configuration options
        """
        super().__init__()
        
        self.options = options
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.options.api_key)
    
    def format_system_prompt(
        self, goal: str, additional_context: str, additional_instructions: List[str]
    ) -> str:
        """Format system prompt for OpenAI model.
        
        Args:
            goal: User's goal to achieve
            additional_context: Additional context information
            additional_instructions: List of additional instructions
            
        Returns:
            Formatted system prompt
        """
        instructions = "\n".join(f"* {instruction}" for instruction in additional_instructions)
        
        system_prompt = f"""You are an Android device automation assistant. Your task is to help achieve the following goal:

GOAL: {goal}

You will analyze screenshots of an Android device to determine the appropriate actions to take.
You can perform the following actions:
1. TAP at specific coordinates (normalized from 0-1)
2. SWIPE from one point to another
3. SWIPE_UP or SWIPE_DOWN to scroll
4. TYPE text into input fields
5. BACK to press the back button
6. HOME to go to the home screen
7. LAUNCH_APP to open an application
8. SUCCESS when the goal is achieved
9. FAILURE when the goal cannot be achieved

IMPORTANT INSTRUCTIONS:
- Be precise with tap coordinates, ensuring they are within visible UI elements
- If an action doesn't work after 2-3 attempts, try a different approach
- When searching, first find and tap the search bar, then type the search term
- If you see a keyboard, make sure to tap the search/enter button after typing
- Avoid repetitive actions that don't lead to progress
- If stuck, try going back to home screen and starting over

Additional context: {additional_context}

"""
        
        if instructions:
            system_prompt += f"\nAdditional instructions:\n{instructions}\n"
        
        system_prompt += """
When deciding the next action, think step by step:
1. Analyze what's currently visible on screen
2. Identify the next logical step toward the goal
3. Determine the specific action and parameters needed

Your response must be formatted as follows:
```observation
[Brief description of what you observe on screen]
```

```action
{
  "action_type": "[TAP, SWIPE, SWIPE_UP, SWIPE_DOWN, TYPE, BACK, HOME, LAUNCH_APP, SUCCESS, FAILURE]",
  "x": 0.5,  // For TAP or SWIPE start (normalized 0-1, omit if not needed)
  "y": 0.5,  // For TAP or SWIPE start (normalized 0-1, omit if not needed)
  "end_x": 0.5,  // For SWIPE end (normalized 0-1, omit if not needed)
  "end_y": 0.5,  // For SWIPE end (normalized 0-1, omit if not needed)
  "text": "text"  // For TYPE or LAUNCH_APP (omit if not needed)
}
```

```reasoning
[Your step-by-step reasoning explaining why this action will help achieve the goal]
```
"""
        
        return system_prompt
    
    def format_message_content(
        self, current_state: AndroidState, include_history: bool = False, history: Optional[List[AndroidStep]] = None
    ) -> List[Dict[str, Any]]:
        """Format message content including screenshot and optional history.
        
        Args:
            current_state: Current device state
            include_history: Whether to include action history
            history: History of previous actions and states
            
        Returns:
            Formatted message content
        """
        content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{current_state.screenshot}"
                }
            },
            {
                "type": "text",
                "text": f"Device information: {json.dumps({'screen_width': current_state.width, 'screen_height': current_state.height, 'current_app': current_state.current_app})}"
            }
        ]
        
        # Add history information if requested
        if include_history and history:
            history_text = "Previous actions and their outcomes:\n"
            for i, step in enumerate(history[-5:]):  # Only include last 5 steps
                action = step.action
                state = step.state
                action_desc = f"{i+1}. {action.action_type}"
                
                if action.action_type == AndroidActionType.TAP and action.coordinates:
                    action_desc += f" at ({action.coordinates.x:.2f}, {action.coordinates.y:.2f})"
                elif action.action_type == AndroidActionType.SWIPE and action.coordinates and action.end_coordinates:
                    action_desc += f" from ({action.coordinates.x:.2f}, {action.coordinates.y:.2f}) to ({action.end_coordinates.x:.2f}, {action.end_coordinates.y:.2f})"
                elif action.action_type in (AndroidActionType.TYPE, AndroidActionType.LAUNCH_APP) and action.text:
                    action_desc += f" with text: '{action.text}'"
                
                # Add state information to show the outcome
                action_desc += f" → App: {state.current_app}"
                
                history_text += action_desc + "\n"
            
            content.append({
                "type": "text",
                "text": history_text
            })
        
        return content
    
    def parse_action_response(self, response_text: str) -> AndroidAction:
        """Parse OpenAI response into an AndroidAction.
        
        Args:
            response_text: Response text from OpenAI
            
        Returns:
            Parsed AndroidAction
        """
        try:
            # Extract JSON from response
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if not json_match:
                print("No JSON found in response, trying to infer action from text")
                return self._infer_action_from_text(response_text)
            
            action_json = json.loads(json_match.group(1))
            
            # Create appropriate action based on type
            action_type = action_json.get("action", "").lower()
            
            if action_type == "tap":
                return AndroidAction(
                    action=AndroidActionType.TAP,
                    coordinate=Coordinate(
                        x=int(action_json["x"] * 1000),
                        y=int(action_json["y"] * 1000)
                    )
                )
            elif action_type == "type":
                return AndroidAction(
                    action=AndroidActionType.TYPE,
                    text=action_json["text"]
                )
            elif action_type == "press":
                key = 4 if action_json["key"] == "back" else 3  # 4 is back, 3 is home
                return AndroidAction(
                    action=AndroidActionType.PRESS,
                    key=key
                )
            elif action_type == "swipe":
                return AndroidAction(
                    action=AndroidActionType.SWIPE,
                    swipe=SwipeCoordinates(
                        start=Coordinate(
                            x=int(action_json["start_x"] * 1000),
                            y=int(action_json["start_y"] * 1000)
                        ),
                        end=Coordinate(
                            x=int(action_json["end_x"] * 1000),
                            y=int(action_json["end_y"] * 1000)
                        ),
                        duration=action_json.get("duration", 100)
                    )
                )
            elif action_type == "success":
                return AndroidAction(action=AndroidActionType.SUCCESS)
            elif action_type == "failure":
                return AndroidAction(action=AndroidActionType.FAILURE)
            else:
                print(f"Unknown action type: {action_type}")
                return self._infer_action_from_text(response_text)
                
        except Exception as e:
            print(f"Error parsing action response: {e}")
            return self._infer_action_from_text(response_text)
    
    def _infer_action_from_text(self, text: str) -> AndroidAction:
        """Attempt to infer action from text when JSON parsing fails.
        
        Args:
            text: Response text to parse
            
        Returns:
            Inferred AndroidAction
        """
        text = text.lower()
        
        # Look for success or failure indications
        if "success" in text or "goal achieved" in text or "task complete" in text:
            return AndroidAction(action=AndroidActionType.SUCCESS)
        
        if "fail" in text or "cannot" in text or "unable" in text:
            return AndroidAction(action=AndroidActionType.FAILURE)
        
        # Look for tap indications
        tap_match = re.search(r'(?:tap|click).*?(\d+\.?\d*).*?(\d+\.?\d*)', text)
        if tap_match:
            try:
                x = float(tap_match.group(1))
                y = float(tap_match.group(2))
                return AndroidAction(
                    action=AndroidActionType.TAP,
                    coordinate=Coordinate(x=int(x * 1000), y=int(y * 1000))
                )
            except (ValueError, IndexError):
                pass
        
        # Look for swipe indications
        swipe_match = re.search(r'swipe.*?from.*?(\d+\.?\d*).*?(\d+\.?\d*).*?to.*?(\d+\.?\d*).*?(\d+\.?\d*)', text)
        if swipe_match:
            try:
                start_x = float(swipe_match.group(1))
                start_y = float(swipe_match.group(2))
                end_x = float(swipe_match.group(3))
                end_y = float(swipe_match.group(4))
                return AndroidAction(
                    action=AndroidActionType.SWIPE,
                    swipe=SwipeCoordinates(
                        start=Coordinate(x=int(start_x * 1000), y=int(start_y * 1000)),
                        end=Coordinate(x=int(end_x * 1000), y=int(end_y * 1000)),
                        duration=100
                    )
                )
            except (ValueError, IndexError):
                pass
        
        # Look for swipe up/down
        if "swipe up" in text:
            return AndroidAction(action_type=AndroidActionType.SWIPE_UP, id=str(uuid.uuid4()))
        
        if "swipe down" in text:
            return AndroidAction(action_type=AndroidActionType.SWIPE_DOWN, id=str(uuid.uuid4()))
        
        # Look for typing
        type_match = re.search(r'type.*[\'"](.+?)[\'"]', text)
        if type_match:
            return AndroidAction(
                action=AndroidActionType.TYPE,
                text=type_match.group(1)
            )
        
        # Look for launch app
        launch_match = re.search(r'launch.*?[\'"](.+?)[\'"]', text)
        if launch_match:
            return AndroidAction(
                action_type=AndroidActionType.LAUNCH_APP,
                text=launch_match.group(1),
                id=str(uuid.uuid4())
            )
        
        # Look for press actions
        if "back" in text:
            return AndroidAction(action=AndroidActionType.PRESS, key=4)
        
        if "home" in text:
            return AndroidAction(action=AndroidActionType.PRESS, key=3)
        
        # Default to failure if we can't determine an action
        return AndroidAction(action=AndroidActionType.FAILURE)
    
    def plan_action(
        self,
        goal: str,
        additional_context: Optional[Union[str, Dict[str, Any]]] = None,
        additional_instructions: Optional[List[str]] = None,
        current_state: Optional[AndroidState] = None,
        session_history: Optional[List[AndroidStep]] = None
    ) -> AndroidAction:
        """Plan next action using OpenAI's API."""
        # Format system prompt with improved instructions
        system_prompt = self.format_system_prompt(goal, additional_context or "", additional_instructions or [])
        
        # Add history analysis to prevent repetitive actions
        if session_history and len(session_history) > 0:
            # Check for repeated actions
            recent_actions = [step.action.action_type for step in session_history[-3:]]
            if len(recent_actions) >= 3 and all(a == recent_actions[0] for a in recent_actions):
                system_prompt += "\nWARNING: The last few actions were all the same type. Try a different approach."
            
            # Check for repeated states
            recent_states = [step.state.current_app for step in session_history[-3:]]
            if len(recent_states) >= 3 and all(s == recent_states[0] for s in recent_states):
                system_prompt += "\nWARNING: The device state hasn't changed in the last few actions. Try a different approach."
            
            # Add action statistics
            action_counts = {}
            for step in session_history:
                action_type = step.action.action_type
                action_counts[action_type] = action_counts.get(action_type, 0) + 1
            
            system_prompt += "\nAction statistics:"
            for action_type, count in action_counts.items():
                if count > 0:
                    system_prompt += f"\n- {action_type}: {count} times"
            
            # Add guidance based on history
            system_prompt += "\n\nBased on the history, try to:"
            system_prompt += "\n1. Avoid repeating the same action type too many times"
            system_prompt += "\n2. Try different approaches if the current one isn't working"
            system_prompt += "\n3. Consider the outcomes of previous actions when planning the next step"
        
        # Format message content
        message_content = self.format_message_content(
            current_state or AndroidState(screenshot="", width=0, height=0, current_app=""), 
            include_history=bool(session_history),
            history=session_history
        )
        
        if self.options.debug:
            print(f"System prompt: {system_prompt}")
            print(f"Message content: {message_content}")
        
        # Make API call
        try:
            response = self.client.chat.completions.create(
                model=self.options.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message_content}
                ],
                temperature=self.options.temperature,
                max_tokens=self.options.max_tokens
            )
            
            # Get response text
            response_text = response.choices[0].message.content
            
            if self.options.debug:
                print(f"Response: {response_text}")
            
            # Parse action
            action = self.parse_action_response(response_text)
            
            if self.options.debug:
                print(f"Parsed action: {action}")
            
            return action
            
        except Exception as e:
            print(f"Error during OpenAI API call: {e}")
            return AndroidAction(action_type=AndroidActionType.FAILURE) 