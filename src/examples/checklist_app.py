"""Example script to demonstrate comprehensive testing of a checklist app.

This script shows how to:
1. Launch the checklist app
2. Explore and identify all available features
3. Create a new task list
4. Add multiple tasks with different priorities
5. Modify existing tasks
6. Delete tasks
7. Test other features like sorting, filtering, and settings

Uses improved keyboard handling for more reliable text input.
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
from android_agent.android_controller import is_keyboard_visible, wait_for_keyboard, dismiss_keyboard


def get_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """Get OpenAI API key from args or environment.
    
    Args:
        api_key: API key from command line
        
    Returns:
        API key if found, None otherwise
    """
    return api_key or os.environ.get("OPENAI_API_KEY")


def main():
    """Main function to run the checklist app automation."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Comprehensive checklist app testing")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--api_key", help="OpenAI API key (can also use OPENAI_API_KEY env var)")
    parser.add_argument("--checklist_app", default="com.mdiwebma.tasks", 
                        help="Package name of the checklist app")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--pause", action="store_true", help="Pause after each action")
    parser.add_argument("--keyboard_check", action="store_true", 
                      help="Verify keyboard appearance before starting")
    args = parser.parse_args()

    # Get API key
    api_key = get_api_key(args.api_key)
    if not api_key:
        print("Error: OpenAI API key required (via --api_key or OPENAI_API_KEY env var)")
        return 1

    # Create screenshots directory
    screenshot_dir = "screenshots/checklist_app"
    os.makedirs(screenshot_dir, exist_ok=True)

    # Configure OpenAI planner
    planner_options = OpenAIPlannerOptions(
        api_key=api_key,
        model="gpt-4o",
        temperature=0.2,
        debug=args.debug
    )
    planner = OpenAIPlanner(options=planner_options)

    # Configure agent options with detailed instructions
    agent_options = AndroidAgentOptions(
        additional_context=f"Comprehensive testing of checklist app '{args.checklist_app}' with improved keyboard handling",
        additional_instructions=[
            "Be precise with tap coordinates",
            "Wait for UI elements to load before interacting",
            "If an action fails, try a different approach",
            "Explore all visible UI elements and features",
            "Take note of any settings or configuration options",
            "Test both basic and advanced features",
            "Verify that changes are saved and persisted",
            "When typing text, wait for the keyboard to appear",
            "If the keyboard doesn't appear, try tapping the input field again",
            "After typing, look for and tap the 'Done' or 'Enter' key on the keyboard",
            "If an action doesn't work after 2 attempts, try a different approach",
            "Look for visual feedback after each action to confirm it worked",
            "If stuck on a screen, try pressing the back button to reset"
        ],
        max_steps=100,
        pause_after_each_action=args.pause,
        screenshot_dir=screenshot_dir
    )

    # Initialize Android agent with comprehensive goal
    agent = AndroidAgent(
        adb_path=args.adb_path,
        action_planner=planner,
        goal=f"""Comprehensively test the checklist app '{args.checklist_app}' by:
        1. Launching the app and exploring its interface
        2. Creating a new task list named 'Test Tasks':
           - Look for and tap the 'New Task' or '+' button
           - Wait for the keyboard to appear
           - Type 'Test Tasks' as the list name
           - Tap the 'Done' or 'Enter' key on the keyboard
           - Look for a 'Save' or 'Create' button and tap it
        3. Adding multiple tasks with different priorities:
           - Tap the 'New Task' or '+' button
           - Type 'High Priority Task'
           - Look for priority settings and set to high
           - Tap 'Save' or 'Done'
           - Repeat for medium and low priority tasks
        4. Testing task modification:
           - Find and tap the 'High Priority Task'
           - Look for edit options
           - Change name to 'Updated High Priority Task'
           - Change priority to medium
           - Save changes
        5. Testing task deletion:
           - Find the 'Low Priority Task'
           - Look for delete or remove options
           - Confirm deletion
        6. Exploring additional features:
           - Look for sorting options in the menu
           - Try different sort orders
           - Look for filtering options
           - Try different filters
           - Explore settings menu
           - Test any other visible features""",
        options=agent_options
    )

    try:
        # Before starting, check keyboard state if requested
        if args.keyboard_check:
            print("\n--- Pre-test keyboard check ---")
            try:
                keyboard_visible = is_keyboard_visible(args.adb_path)
                print(f"Keyboard visible before test: {keyboard_visible}")
                if keyboard_visible:
                    print("Dismissing keyboard before starting...")
                    dismiss_keyboard(args.adb_path)
            except Exception as e:
                print(f"Error checking keyboard state: {e}")

        # Start the automation
        print("\n========== Starting Checklist App Test ==========")
        print(f"App: {args.checklist_app}")
        print(f"Model: {planner_options.model}")
        print(f"Max steps: {agent_options.max_steps}")
        print(f"Screenshots: {screenshot_dir}")
        if args.debug:
            print("Debug mode enabled")
        print("\nPress Ctrl+C to abort\n")
        
        agent.start()
        
        # Check final status
        if agent.status == AndroidGoalState.SUCCESS:
            print("\n✅ Successfully completed checklist app testing!")
            return 0
        elif agent.status == AndroidGoalState.FAILED:
            print(f"\n❌ Failed to complete checklist app testing. Final status: {agent.status}")
            return 1
        else:
            print(f"\n⚠️ Testing not completed (reached maximum steps)")
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