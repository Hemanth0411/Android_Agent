"""Example script to test keyboard input functionality.

This script demonstrates the improved keyboard handling features:
1. Opening Chrome browser
2. Tapping the address bar to focus it
3. Explicitly waiting for the keyboard to appear
4. Typing a search term
5. Pressing the search button
6. Verifying results
"""

import argparse
import os
import sys
import time
from typing import List, Optional

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from android_agent.android_agent import AndroidAgent, AndroidAgentOptions, AndroidGoalState
from android_agent.openai_planner import OpenAIPlanner, OpenAIPlannerOptions
from android_agent.android_controller import is_keyboard_visible, wait_for_keyboard, dismiss_keyboard
from android_agent.android_action import AndroidAction, AndroidActionType


def get_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """Get OpenAI API key from args or environment.
    
    Args:
        api_key: API key from command line
        
    Returns:
        API key if found, None otherwise
    """
    return api_key or os.environ.get("OPENAI_API_KEY")


def main():
    """Main function to test keyboard input functionality."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test keyboard input functionality")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--api_key", help="OpenAI API key (can also use OPENAI_API_KEY env var)")
    parser.add_argument("--search_term", default="keyboard input test", 
                        help="Term to search for")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--pause", action="store_true", help="Pause after each action")
    args = parser.parse_args()

    # Get API key
    api_key = get_api_key(args.api_key)
    if not api_key:
        print("Error: OpenAI API key required (via --api_key or OPENAI_API_KEY env var)")
        return 1

    # Configure OpenAI planner
    planner_options = OpenAIPlannerOptions(
        api_key=api_key,
        model="gpt-4o",  # Use latest model for best results
        temperature=0.2,
        debug=args.debug
    )
    planner = OpenAIPlanner(options=planner_options)

    # Create screenshots directory
    screenshot_dir = "screenshots/input_test"
    os.makedirs(screenshot_dir, exist_ok=True)

    # Configure agent options with specific instructions for keyboard handling
    agent_options = AndroidAgentOptions(
        additional_context="Testing keyboard input in Chrome with improved keyboard detection",
        additional_instructions=[
            "Focus specifically on making keyboard input work correctly",
            "Tap precisely on the address bar at the top of Chrome",
            "After tapping, WAIT for the keyboard to appear",
            "If the keyboard doesn't appear, try tapping the address bar again",
            "Once keyboard appears, type the search term carefully",
            "After typing, look for and press the search/enter button on the keyboard",
            "If stuck in a loop of repeatedly tapping, try a different approach",
            "If tap doesn't work, try pressing back and starting over",
            "Verify that typed input is visible in the address bar",
            "After search completes, verify search results are shown"
        ],
        max_steps=20,
        pause_after_each_action=args.pause,
        screenshot_dir=screenshot_dir
    )

    # Define a very explicit goal focusing on keyboard input
    goal = f"""Test keyboard input by following these EXACT steps:
    1. Press HOME to ensure you start from a clean state
    2. Open Chrome browser (look for the Chrome icon in the app drawer)
    3. When Chrome is open, locate the address bar at the top
    4. TAP PRECISELY on the address bar to focus it and bring up the keyboard
    5. WAIT for the keyboard to appear 
    6. TYPE "{args.search_term}" into the address bar
    7. Press the search/enter button on the keyboard
    8. Verify that search results for "{args.search_term}" are displayed
    
    The most important steps are 4, 5, and 6. You MUST make sure the keyboard appears
    before attempting to type. If no keyboard appears after tapping, try tapping again."""

    # Initialize Android agent with the specific typing goal
    agent = AndroidAgent(
        adb_path=args.adb_path,
        action_planner=planner,
        goal=goal,
        options=agent_options
    )

    try:
        # Before starting, check keyboard state and dismiss if visible
        print("\n--- Pre-test keyboard check ---")
        keyboard_visible = False
        try:
            keyboard_visible = is_keyboard_visible(args.adb_path)
            print(f"Keyboard visible before test: {keyboard_visible}")
            if keyboard_visible:
                print("Dismissing keyboard before starting...")
                dismiss_keyboard(args.adb_path)
        except Exception as e:
            print(f"Error checking keyboard state: {e}")

        # Start the automation
        print("\n--- Starting keyboard input test ---")
        print(f"Goal: Test keyboard input with search term '{args.search_term}'")
        print(f"Model: {planner_options.model}")
        print(f"Max steps: {agent_options.max_steps}")
        if args.debug:
            print("Debug mode enabled")
        
        agent.start()
        
        # Check keyboard state after completion
        print("\n--- Post-test keyboard check ---")
        try:
            keyboard_visible = is_keyboard_visible(args.adb_path)
            print(f"Keyboard visible after test: {keyboard_visible}")
            if keyboard_visible:
                print("Dismissing keyboard...")
                dismiss_keyboard(args.adb_path)
        except Exception as e:
            print(f"Error checking keyboard state: {e}")
        
        # Check final status
        if agent.status == AndroidGoalState.SUCCESS:
            print("\n✅ Successfully completed keyboard input test!")
            return 0
        elif agent.status == AndroidGoalState.FAILED:
            print(f"\n❌ Failed to complete keyboard input test. Final status: {agent.status}")
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