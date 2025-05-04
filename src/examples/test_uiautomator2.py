#!/usr/bin/env python3
"""Example script to demonstrate UIAutomator2 text input fallback.

This script shows how to:
1. Open an app with text input fields
2. Use UIAutomator2 to directly send text to input fields
3. Compare standard keyboard input with UIAutomator2 direct input
4. Handle cases where the keyboard doesn't appear
"""

import argparse
import os
import sys
import time
from typing import List, Optional

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from android_agent.android_agent import AndroidAgent, AndroidAgentOptions, AndroidGoalState
from android_agent.android_action import AndroidAction, AndroidActionType
from android_agent.openai_planner import OpenAIPlanner, OpenAIPlannerOptions
from android_agent.android_controller import (
    is_keyboard_visible, 
    dismiss_keyboard, 
    type_text, 
    type_text_with_uiautomator2, 
    smart_type_text
)


def get_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """Get OpenAI API key from args or environment.
    
    Args:
        api_key: API key from command line
        
    Returns:
        API key if found, None otherwise
    """
    return api_key or os.environ.get("OPENAI_API_KEY")


def check_uiautomator2() -> bool:
    """Check if UIAutomator2 is installed.
    
    Returns:
        bool: Whether UIAutomator2 is available
    """
    try:
        import importlib.util
        return importlib.util.find_spec("uiautomator2") is not None
    except Exception:
        return False


def test_direct_input(adb_path: str, app_package: str, x: float, y: float, text: str) -> bool:
    """Test direct UIAutomator2 input to a specific field.
    
    Args:
        adb_path: Path to ADB executable
        app_package: Package name of app to test with
        x: X coordinate to tap (normalized 0-1)
        y: Y coordinate to tap (normalized 0-1)
        text: Text to input
        
    Returns:
        bool: Whether the test succeeded
    """
    try:
        print("\n=== Testing Direct UIAutomator2 Input ===")
        
        # Launch app
        from android_agent.android_controller import launch_app, press_home
        press_home(adb_path)
        time.sleep(1)
        launch_app(adb_path, app_package)
        time.sleep(2)
        
        # Try to input text using UIAutomator2
        print(f"📝 Attempting to input text to field at ({x}, {y})")
        result = type_text_with_uiautomator2(adb_path, text, x, y)
        
        if result:
            print(f"✅ Successfully input text using UIAutomator2: '{text}'")
        else:
            print(f"❌ Failed to input text using UIAutomator2")
            
        return result
    except Exception as e:
        print(f"❌ Error in direct input test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function to test UIAutomator2 text input."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test UIAutomator2 text input")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--api_key", help="OpenAI API key (can also use OPENAI_API_KEY env var)")
    parser.add_argument("--app", default="com.android.settings", 
                        help="Package name of app to test with")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Check if UIAutomator2 is installed
    if not check_uiautomator2():
        print("\n❌ UIAutomator2 is not installed. Please install it with:")
        print("pip install uiautomator2")
        print("\nThen run 'python -m uiautomator2 init' to initialize")
        return 1

    # Get API key
    api_key = get_api_key(args.api_key)
    if not api_key:
        print("Error: OpenAI API key required (via --api_key or OPENAI_API_KEY env var)")
        return 1

    # Create screenshots directory
    screenshot_dir = "screenshots/uiautomator2_test"
    os.makedirs(screenshot_dir, exist_ok=True)

    # Check keyboard state
    try:
        keyboard_visible = is_keyboard_visible(args.adb_path)
        print(f"Keyboard visible before test: {keyboard_visible}")
        if keyboard_visible:
            print("Dismissing keyboard before starting...")
            dismiss_keyboard(args.adb_path)
    except Exception as e:
        print(f"Error checking keyboard state: {e}")

    # First test: Direct UIAutomator2 input
    if args.app == "com.android.settings":
        # Use search bar in settings (typically at top)
        test_direct_input(args.adb_path, args.app, 0.5, 0.1, "test input")
    else:
        # Generic coordinates for testing
        test_direct_input(args.adb_path, args.app, 0.5, 0.5, "test input")

    # Second test: Agent-based testing using UIAutomator2 fallback
    # Configure OpenAI planner
    planner_options = OpenAIPlannerOptions(
        api_key=api_key,
        model="gpt-4o",
        temperature=0.2,
        debug=args.debug
    )
    planner = OpenAIPlanner(options=planner_options)

    # Configure agent options
    agent_options = AndroidAgentOptions(
        additional_context="Testing UIAutomator2 text input fallback",
        additional_instructions=[
            "This test specifically demonstrates UIAutomator2 text input fallback.",
            "If you encounter text input fields, try to type in them.",
            "We're testing if UIAutomator2 can send text directly when keyboard doesn't appear."
        ],
        max_steps=15,
        pause_after_each_action=False,
        screenshot_dir=screenshot_dir
    )

    # Initialize Android agent with specific goal
    agent = AndroidAgent(
        adb_path=args.adb_path,
        action_planner=planner,
        goal=f"""Test UIAutomator2 text input fallback with these steps:
        1. Press HOME to ensure we start from a clean state
        2. Open the {args.app} app
        3. Look for any text input field or search bar
        4. Tap on the input field
        5. Type "UIAutomator2 test input" in the field
        6. If keyboard doesn't appear, the agent should still be able to input text
           using the UIAutomator2 fallback mechanism
        7. Verify the input succeeded by checking if the text appears in the field""",
        options=agent_options
    )

    try:
        # Start the automation
        print("\n=== Starting UIAutomator2 Agent Test ===")
        print(f"Goal: Test UIAutomator2 text input in {args.app}")
        print(f"Model: {planner_options.model}")
        print(f"Max steps: {agent_options.max_steps}")
        
        agent.start()
        
        # Check final status
        if agent.status == AndroidGoalState.SUCCESS:
            print("\n✅ Successfully completed UIAutomator2 text input test!")
            return 0
        elif agent.status == AndroidGoalState.FAILED:
            print(f"\n❌ Failed to complete UIAutomator2 test. Final status: {agent.status}")
            return 1
        else:
            print(f"\n⚠️ Test not completed (reached maximum steps)")
            return 1
            
    except KeyboardInterrupt:
        print("\nOperation aborted by user")
        return 130
        
    except Exception as e:
        print(f"\nError during automation: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1
    
    finally:
        # Cleanup
        try:
            print("\nPerforming cleanup...")
            # Try to go back to home screen
            agent._take_action(AndroidAction(action=AndroidActionType.PRESS, key=3))
            # Check if keyboard is visible and dismiss it
            if is_keyboard_visible(args.adb_path):
                print("Dismissing keyboard...")
                dismiss_keyboard(args.adb_path)
        except Exception as e:
            if args.debug:
                print(f"Cleanup error: {e}")


if __name__ == "__main__":
    sys.exit(main()) 