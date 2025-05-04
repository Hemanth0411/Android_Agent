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
from .android_action import AndroidAction, AndroidActionType, Coordinate, SwipeCoordinates
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
  "action": "[TAP, SWIPE, SWIPE_UP, SWIPE_DOWN, TYPE, BACK, HOME, LAUNCH_APP, SUCCESS, FAILURE]",
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
                action_desc = f"{i+1}. {action.action}"
                
                if action.action == AndroidActionType.TAP and action.coordinate:
                    action_desc += f" at ({action.coordinate.x:.2f}, {action.coordinate.y:.2f})"
                elif action.action == AndroidActionType.SWIPE and action.swipe:
                    action_desc += f" from ({action.swipe.start.x:.2f}, {action.swipe.start.y:.2f}) to ({action.swipe.end.x:.2f}, {action.swipe.end.y:.2f})"
                elif action.action in (AndroidActionType.TYPE, AndroidActionType.LAUNCH_APP) and action.text:
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
            json_match = re.search(r'```(?:json|action)\n(.*?)\n```', response_text, re.DOTALL)
            if not json_match:
                print("⚠️ No JSON found in response, trying to infer action from text")
                # Print first 200 chars of the response for debugging
                print(f"📝 Response excerpt: {response_text[:200]}...")
                return self._infer_action_from_text(response_text)
            
            json_text = json_match.group(1)
            print(f"✅ Found JSON: {json_text}")
            
            try:
                action_json = json.loads(json_text)
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse error: {e}")
                print(f"📝 JSON text: {json_text}")
                return self._infer_action_from_text(response_text)
            
            # Create mapping from various action names to correct enum values
            action_map = {
                "tap": AndroidActionType.TAP,
                "click": AndroidActionType.TAP,
                "type": AndroidActionType.TYPE,
                "input": AndroidActionType.TYPE,
                "press": AndroidActionType.PRESS,
                "swipe": AndroidActionType.SWIPE,
                "swipe_up": AndroidActionType.SWIPE_UP,
                "swipeup": AndroidActionType.SWIPE_UP,
                "swipe_down": AndroidActionType.SWIPE_DOWN,
                "swipedown": AndroidActionType.SWIPE_DOWN,
                "screenshot": AndroidActionType.SCREENSHOT,
                "launch_app": AndroidActionType.LAUNCH_APP,
                "launchapp": AndroidActionType.LAUNCH_APP,
                "success": AndroidActionType.SUCCESS,
                "failure": AndroidActionType.FAILURE,
                "back": AndroidActionType.PRESS,  # Map back to PRESS with key=4
                "home": AndroidActionType.PRESS,  # Map home to PRESS with key=3
            }
            
            # Check if action key exists
            action_key = None
            for key in ["action", "action_type", "type"]:
                if key in action_json:
                    action_key = key
                    break
                    
            if not action_key:
                print(f"❌ Missing action field in JSON: {action_json}")
                return self._infer_action_from_text(response_text)
            
            # Get action type and normalize to lowercase
            action_type = action_json[action_key].lower()
            
            # Map the action type to the correct enum value
            if action_type not in action_map:
                print(f"⚠️ Unknown action type: {action_type}, trying to find closest match")
                # Try to find a partial match
                for key in action_map:
                    if key in action_type:
                        action_type = key
                        print(f"✅ Matched partial action: {key}")
                        break
                else:
                    print(f"❌ No match found for action type: {action_type}")
                    return self._infer_action_from_text(response_text)
            
            mapped_action_type = action_map[action_type]
            
            # Handle different action types
            if mapped_action_type == AndroidActionType.TAP:
                if "x" not in action_json or "y" not in action_json:
                    # Try alternative coordinate formats
                    if "coordinate" in action_json and isinstance(action_json["coordinate"], dict):
                        x = action_json["coordinate"].get("x")
                        y = action_json["coordinate"].get("y")
                    elif "coordinates" in action_json and isinstance(action_json["coordinates"], list):
                        if len(action_json["coordinates"]) >= 2:
                            x, y = action_json["coordinates"][0], action_json["coordinates"][1]
                        else:
                            print(f"❌ Invalid coordinates format: {action_json}")
                            return self._infer_action_from_text(response_text)
                    else:
                        print(f"❌ Missing coordinates for tap: {action_json}")
                        return self._infer_action_from_text(response_text)
                else:
                    x, y = action_json["x"], action_json["y"]
                
                # Convert coordinates to proper format (normalize if needed)
                try:
                    x_val = float(x)
                    y_val = float(y)
                    
                    # If values are between 0-1, they're normalized
                    if 0 <= x_val <= 1 and 0 <= y_val <= 1:
                        x_val = int(x_val * 1000)
                        y_val = int(y_val * 1000)
                    else:
                        # Values might already be in pixel coordinates
                        x_val = int(x_val)
                        y_val = int(y_val)
                        
                    return AndroidAction(
                        action=AndroidActionType.TAP,
                        coordinate=Coordinate(x=x_val, y=y_val)
                    )
                except (TypeError, ValueError) as e:
                    print(f"❌ Error processing tap coordinates: {e}")
                    return self._infer_action_from_text(response_text)
                    
            elif mapped_action_type == AndroidActionType.TYPE:
                # Look for text in various fields
                text = None
                for field in ["text", "input", "value", "content"]:
                    if field in action_json:
                        text = action_json[field]
                        break
                        
                if not text:
                    print(f"❌ Missing text for typing: {action_json}")
                    return self._infer_action_from_text(response_text)
                
                return AndroidAction(
                    action=AndroidActionType.TYPE,
                    text=text
                )
                
            elif mapped_action_type == AndroidActionType.PRESS:
                # Handle different key formats and special cases
                if action_type == "back":
                    key = 4  # KEYCODE_BACK
                elif action_type == "home":
                    key = 3  # KEYCODE_HOME
                else:
                    # Try to extract key from the action
                    key = action_json.get("key")
                    if key is None:
                        if "back" in str(action_json).lower():
                            key = 4
                        elif "home" in str(action_json).lower():
                            key = 3
                        else:
                            print(f"❌ Missing or invalid key for press: {action_json}")
                            return self._infer_action_from_text(response_text)
                
                # Convert key to integer if it's a string
                if isinstance(key, str):
                    try:
                        key = int(key)
                    except ValueError:
                        # Map string keys to their values
                        key_map = {"back": 4, "home": 3}
                        key = key_map.get(key.lower(), 0)
                        
                return AndroidAction(
                    action=AndroidActionType.PRESS,
                    key=key
                )
                
            elif mapped_action_type == AndroidActionType.SWIPE:
                # Handle various swipe coordinate formats
                start_x, start_y, end_x, end_y = None, None, None, None
                
                # Format 1: Explicit coordinates
                if all(k in action_json for k in ["start_x", "start_y", "end_x", "end_y"]):
                    start_x = action_json["start_x"]
                    start_y = action_json["start_y"]
                    end_x = action_json["end_x"]
                    end_y = action_json["end_y"]
                # Format 2: x, y, end_x, end_y
                elif all(k in action_json for k in ["x", "y", "end_x", "end_y"]):
                    start_x = action_json["x"]
                    start_y = action_json["y"]
                    end_x = action_json["end_x"]
                    end_y = action_json["end_y"]
                # Format 3: from and to objects
                elif "from" in action_json and "to" in action_json:
                    start_x = action_json["from"].get("x")
                    start_y = action_json["from"].get("y")
                    end_x = action_json["to"].get("x")
                    end_y = action_json["to"].get("y")
                # Format 4: start and end objects
                elif "start" in action_json and "end" in action_json:
                    start_x = action_json["start"].get("x")
                    start_y = action_json["start"].get("y")
                    end_x = action_json["end"].get("x")
                    end_y = action_json["end"].get("y")
                else:
                    print(f"❌ Missing coordinates for swipe: {action_json}")
                    return self._infer_action_from_text(response_text)
                
                # Validate and normalize coordinates
                try:
                    start_x = float(start_x)
                    start_y = float(start_y)
                    end_x = float(end_x)
                    end_y = float(end_y)
                    
                    # If values are between 0-1, they're normalized
                    if all(0 <= v <= 1 for v in [start_x, start_y, end_x, end_y]):
                        start_x = int(start_x * 1000)
                        start_y = int(start_y * 1000)
                        end_x = int(end_x * 1000)
                        end_y = int(end_y * 1000)
                    else:
                        # Values might already be in pixel coordinates
                        start_x = int(start_x)
                        start_y = int(start_y)
                        end_x = int(end_x)
                        end_y = int(end_y)
                        
                    duration = action_json.get("duration", 100)
                    
                    return AndroidAction(
                        action=AndroidActionType.SWIPE,
                        swipe=SwipeCoordinates(
                            start=Coordinate(x=start_x, y=start_y),
                            end=Coordinate(x=end_x, y=end_y),
                            duration=duration
                        )
                    )
                except (TypeError, ValueError) as e:
                    print(f"❌ Error processing swipe coordinates: {e}")
                    return self._infer_action_from_text(response_text)
                    
            elif mapped_action_type in [AndroidActionType.SWIPE_UP, AndroidActionType.SWIPE_DOWN]:
                return AndroidAction(action=mapped_action_type)
                
            elif mapped_action_type == AndroidActionType.LAUNCH_APP:
                # Look for app name in various fields
                app_name = None
                for field in ["text", "app", "package", "name"]:
                    if field in action_json:
                        app_name = action_json[field]
                        break
                        
                if not app_name:
                    print(f"❌ Missing app name for launch: {action_json}")
                    return self._infer_action_from_text(response_text)
                
                return AndroidAction(
                    action=AndroidActionType.LAUNCH_APP,
                    text=app_name
                )
                
            elif mapped_action_type in [AndroidActionType.SUCCESS, AndroidActionType.FAILURE]:
                return AndroidAction(action=mapped_action_type)
                
            else:
                print(f"⚠️ Unhandled action type: {mapped_action_type}")
                return self._infer_action_from_text(response_text)
                
        except Exception as e:
            print(f"❌ Error parsing action response: {e}")
            # Print traceback for debugging
            import traceback
            traceback.print_exc()
            return self._infer_action_from_text(response_text)
    
    def _infer_action_from_text(self, text: str) -> AndroidAction:
        """Attempt to infer action from text when JSON parsing fails.
        
        Args:
            text: Response text to parse
            
        Returns:
            Inferred AndroidAction
        """
        print("🔍 Inferring action from text")
        text = text.lower()
        
        # Common actions based on simple text
        action_map = {
            "go home": (AndroidActionType.PRESS, 3),
            "press home": (AndroidActionType.PRESS, 3),
            "home screen": (AndroidActionType.PRESS, 3),
            "return to home": (AndroidActionType.PRESS, 3),
            "go back": (AndroidActionType.PRESS, 4),
            "press back": (AndroidActionType.PRESS, 4), 
            "return to previous": (AndroidActionType.PRESS, 4),
            "task completed": (AndroidActionType.SUCCESS, None),
            "goal achieved": (AndroidActionType.SUCCESS, None),
            "mission accomplished": (AndroidActionType.SUCCESS, None),
            "completed successfully": (AndroidActionType.SUCCESS, None),
            "cannot complete": (AndroidActionType.FAILURE, None),
            "unable to proceed": (AndroidActionType.FAILURE, None),
            "failed to achieve": (AndroidActionType.FAILURE, None),
            "scroll up": (AndroidActionType.SWIPE_UP, None),
            "scroll down": (AndroidActionType.SWIPE_DOWN, None),
            "swipe up": (AndroidActionType.SWIPE_UP, None),
            "swipe down": (AndroidActionType.SWIPE_DOWN, None),
        }
        
        # Check for exact phrases first
        for phrase, (action_type, value) in action_map.items():
            if phrase in text:
                print(f"✅ Matched phrase: '{phrase}' -> {action_type}")
                if action_type == AndroidActionType.PRESS:
                    return AndroidAction(action=action_type, key=value)
                else:
                    return AndroidAction(action=action_type)
        
        # Look for success or failure indications
        if any(word in text for word in ["success", "goal achieved", "task complete", "done", "finished", "completed"]):
            print("✅ Success detected in text")
            return AndroidAction(action=AndroidActionType.SUCCESS)
        
        if any(word in text for word in ["fail", "cannot", "unable", "couldn't", "error", "issue"]):
            print("❌ Failure detected in text")
            return AndroidAction(action=AndroidActionType.FAILURE)
        
        # Check for home command first (high priority)
        if re.search(r'\b(home|main screen|launcher)\b', text):
            print("🏠 Home command detected")
            return AndroidAction(action=AndroidActionType.PRESS, key=3)  # 3 is home
            
        # Check for back command first (high priority)
        if re.search(r'\b(back|previous|return)\b', text):
            print("⬅️ Back command detected")
            return AndroidAction(action=AndroidActionType.PRESS, key=4)  # 4 is back
        
        # Look for type/input actions (high priority, check before tap)
        type_patterns = [
            r'type\s+["\'](.+?)["\']',
            r'input\s+["\'](.+?)["\']',
            r'enter\s+["\'](.+?)["\']',
            r'write\s+["\'](.+?)["\']',
            r'text\s+["\'](.+?)["\']',
            r'keyboard\s+["\'](.+?)["\']',
        ]
        
        for pattern in type_patterns:
            type_match = re.search(pattern, text)
            if type_match:
                text_content = type_match.group(1)
                print(f"⌨️ Type detected: '{text_content}'")
                return AndroidAction(
                    action=AndroidActionType.TYPE,
                    text=text_content
                )
        
        # Look for tap indications with various formats
        tap_patterns = [
            # Standard tap with coordinates
            r'(?:tap|click|touch|press).*?(\d+\.?\d*).*?(\d+\.?\d*)',
            # Tap with normalized coordinates in various formats
            r'(?:tap|click|touch|press).*?coordinates?\s*\(?\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*\)?',
            r'(?:tap|click|touch|press).*?at position\s*\(?\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*\)?',
            r'(?:tap|click|touch|press).*?location\s*\(?\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*\)?',
            # Tap with x= y= format
            r'(?:tap|click|touch|press).*?x\s*=\s*(\d+\.?\d*).*?y\s*=\s*(\d+\.?\d*)',
        ]
        
        for pattern in tap_patterns:
            tap_match = re.search(pattern, text)
            if tap_match:
                try:
                    x = float(tap_match.group(1))
                    y = float(tap_match.group(2))
                    print(f"👆 Tap detected at coordinates ({x}, {y})")
                    
                    # Convert coordinates if necessary
                    if 0 <= x <= 1 and 0 <= y <= 1:  # Normalized
                        x = int(x * 1000)
                        y = int(y * 1000)
                    else:  # Raw pixel values or other format
                        x = int(x)
                        y = int(y)
                        
                    return AndroidAction(
                        action=AndroidActionType.TAP,
                        coordinate=Coordinate(x=x, y=y)
                    )
                except (ValueError, IndexError) as e:
                    print(f"❌ Error parsing tap coordinates: {e}")
                    continue
        
        # Check for tap/click action mentions without coordinates
        if any(word in text for word in ["tap", "click", "touch", "press"]):
            # If we found tap/click action but no coordinates, search for numbers in proximity
            num_pattern = r'(\d+\.?\d*)[^\d]+(\d+\.?\d*)'
            num_match = re.search(num_pattern, text)
            if num_match:
                try:
                    x = float(num_match.group(1))
                    y = float(num_match.group(2))
                    print(f"👆 Tap coordinates extracted: ({x}, {y})")
                    
                    # Convert coordinates if necessary
                    if 0 <= x <= 1 and 0 <= y <= 1:  # Normalized
                        x = int(x * 1000)
                        y = int(y * 1000)
                    else:  # Raw pixel values
                        x = int(x)
                        y = int(y)
                        
                    return AndroidAction(
                        action=AndroidActionType.TAP,
                        coordinate=Coordinate(x=x, y=y)
                    )
                except (ValueError, IndexError) as e:
                    print(f"❌ Error extracting tap coordinates: {e}")
        
        # Look for swipe with detailed patterns
        swipe_patterns = [
            r'swipe.*?from.*?\(?(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\)?.*?to.*?\(?(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\)?',
            r'swipe.*?start.*?\(?(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\)?.*?end.*?\(?(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\)?',
            r'drag.*?from.*?\(?(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\)?.*?to.*?\(?(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\)?',
        ]
        
        for pattern in swipe_patterns:
            swipe_match = re.search(pattern, text)
            if swipe_match:
                try:
                    start_x = float(swipe_match.group(1))
                    start_y = float(swipe_match.group(2))
                    end_x = float(swipe_match.group(3))
                    end_y = float(swipe_match.group(4))
                    print(f"👆 Swipe detected from ({start_x}, {start_y}) to ({end_x}, {end_y})")
                    
                    # Convert coordinates if necessary
                    if 0 <= start_x <= 1 and 0 <= start_y <= 1 and 0 <= end_x <= 1 and 0 <= end_y <= 1:
                        start_x = int(start_x * 1000)
                        start_y = int(start_y * 1000)
                        end_x = int(end_x * 1000)
                        end_y = int(end_y * 1000)
                    else:
                        start_x = int(start_x)
                        start_y = int(start_y)
                        end_x = int(end_x)
                        end_y = int(end_y)
                        
                    return AndroidAction(
                        action=AndroidActionType.SWIPE,
                        swipe=SwipeCoordinates(
                            start=Coordinate(x=start_x, y=start_y),
                            end=Coordinate(x=end_x, y=end_y),
                            duration=100
                        )
                    )
                except (ValueError, IndexError) as e:
                    print(f"❌ Error parsing swipe coordinates: {e}")
                    continue
        
        # Look for swipe up/down directions
        if any(phrase in text for phrase in ["swipe up", "scroll up", "flick up"]):
            print("👆 Swipe up detected")
            return AndroidAction(action=AndroidActionType.SWIPE_UP)
        
        if any(phrase in text for phrase in ["swipe down", "scroll down", "flick down"]):
            print("👇 Swipe down detected")
            return AndroidAction(action=AndroidActionType.SWIPE_DOWN)
        
        # Look for launch app
        launch_patterns = [
            r'launch.*?[\'"](.+?)[\'"]',
            r'open app.*?[\'"](.+?)[\'"]',
            r'start.*?app.*?[\'"](.+?)[\'"]',
            r'open.*?application.*?[\'"](.+?)[\'"]',
        ]
        
        for pattern in launch_patterns:
            launch_match = re.search(pattern, text)
            if launch_match:
                app_name = launch_match.group(1)
                print(f"🚀 Launch app detected: '{app_name}'")
                return AndroidAction(
                    action=AndroidActionType.LAUNCH_APP,
                    text=app_name
                )
        
        # If we found "type" keyword but no matching pattern earlier, look for any quoted text
        if any(word in text for word in ["type", "input", "enter", "write", "text"]):
            # Try to find any quoted text
            quoted_match = re.search(r'[\'"](.+?)[\'"]', text)
            if quoted_match:
                text_content = quoted_match.group(1)
                print(f"⌨️ Type content extracted from quotes: '{text_content}'")
                return AndroidAction(
                    action=AndroidActionType.TYPE,
                    text=text_content
                )
            else:
                # If no quoted text found, try to find text after one of these keywords
                for keyword in ["type", "input", "enter", "write", "text"]:
                    if keyword in text:
                        parts = text.split(keyword, 1)[1].strip()
                        # Take just the first line or sentence
                        parts = parts.split('\n')[0].split('.')[0].strip()
                        if parts and len(parts) < 100:  # Limit to reasonable text length
                            print(f"⌨️ Type content extracted after keyword: '{parts}'")
                            return AndroidAction(
                                action=AndroidActionType.TYPE,
                                text=parts
                            )
                            
        # Default to pressing home if we can't determine an action
        print("⚠️ Couldn't determine action from text, defaulting to home")
        return AndroidAction(action=AndroidActionType.PRESS, key=3)
    
    def plan_action(
        self,
        goal: str,
        additional_context: Optional[Union[str, Dict[str, Any]]] = None,
        additional_instructions: Optional[List[str]] = None,
        current_state: Optional[AndroidState] = None,
        session_history: Optional[List[AndroidStep]] = None
    ) -> AndroidAction:
        """Plan next action based on current state and goal.
        
        Args:
            goal: The goal to achieve
            additional_context: Extra context information
            additional_instructions: Extra instructions
            current_state: Current device state
            session_history: History of previous actions and states
            
        Returns:
            The next action to perform
        """
        if not current_state:
            print("❌ No current state provided")
            return AndroidAction(action=AndroidActionType.FAILURE)
        
        try:
            # Prepare conversation context
            system_prompt = self.format_system_prompt(
                goal,
                additional_context or "",
                additional_instructions or []
            )
            print(f"🔵 System prompt length: {len(system_prompt)} characters")
            
            # Prepare message content including screenshot
            content = self.format_message_content(
                current_state,
                include_history=True,
                history=session_history
            )
            print(f"🔵 Screenshot base64 size: {len(current_state.screenshot)/1024:.1f} KB")
            
            # Prepare messages for API call
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ]
            
            # Make API call
            print(f"🤖 Calling OpenAI API for action plan...")
            response = self.client.chat.completions.create(
                model=self.options.model,
                messages=messages,
                temperature=self.options.temperature,
                max_tokens=self.options.max_tokens
            )
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Store the observation section for UI detection
            observation = self._extract_section(response_text, "observation")
            if observation:
                self.last_observation = observation
                print(f"👁️ OBSERVATION: {observation}")
            else:
                self.last_observation = ""
            
            # Extract reasoning for debugging
            reasoning = self._extract_section(response_text, "reasoning")
            if reasoning:
                print(f"🧠 REASONING: {reasoning}")
            
            # Parse response to get action
            action = self.parse_action_response(response_text)
            
            # Log full response for debugging
            if self.options.debug:
                print(f"📝 Full response: {response_text}")
            else:
                print(f"🔄 Full response: {response_text}")
            
            # Log action
            print(f"🎯 Selected action: {action.action}")
            
            # Special case for Chrome UI detection
            if "chrome" in self.last_observation.lower() and ("com.android.chrome" not in current_state.current_app):
                print("⚠️ Chrome UI detected but not in app name. This may indicate incorrect app detection.")
                
            return action
            
        except Exception as e:
            print(f"❌ Error in plan_action: {e}")
            import traceback
            traceback.print_exc()
            return AndroidAction(action=AndroidActionType.FAILURE)
            
    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """Extract a specific section from the response.
        
        Args:
            text: The full response text
            section_name: The name of the section to extract
            
        Returns:
            The extracted section text or None if not found
        """
        pattern = rf"```{section_name}\n(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None 