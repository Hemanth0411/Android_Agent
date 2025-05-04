"""Example script to demonstrate searching Google on Android.

This script shows how to:
1. Launch Chrome browser
2. Navigate to Google.com
3. Perform a search with enhanced keyboard handling
4. Verify search results
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
    """Main function to run the Google search automation."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Automate Google search on Android")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--api_key", help="OpenAI API key (can also use OPENAI_API_KEY env var)")
    parser.add_argument("--search_term", default="Android automation agent", 
                        help="Term to search for on Google")
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
    screenshot_dir = "screenshots/google_search"
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
        additional_context="Searching Google on Android with improved keyboard handling",
        additional_instructions=[
            "Be precise with tap coordinates",
            "Wait for UI elements to load before interacting",
            "If an action fails, try a different approach",
            "When typing text, wait for the keyboard to appear",
            "After typing, look for and tap the 'Search' or 'Go' button",
            "If the Chrome app doesn't open correctly, try closing it and reopening",
            "Look for the Chrome icon specifically, not other Google apps",
            "If you end up in Google Lens or other Google apps, press back and try again",
            "Verify you're in Chrome by looking for the address bar",
            "If stuck, try pressing home and starting over",
            "After tapping the search bar, wait for keyboard to appear before typing",
            "If the keyboard doesn't appear after tapping, try tapping a different part of the search bar",
            "After typing, look for and tap the 'Search' or 'Go' button on the keyboard",
        ],
        max_steps=30,
        pause_after_each_action=args.pause,
        screenshot_dir=screenshot_dir
    )

    # Initialize Android agent with specific goal
    agent = AndroidAgent(
        adb_path=args.adb_path,
        action_planner=planner,
        goal=f"""Search for '{args.search_term}' on Google by:
        1. Going to the home screen
        2. Finding and opening the Chrome browser app (look for the Chrome icon specifically)
        3. If Chrome doesn't open correctly:
           - Press back to exit any other Google apps
           - Try opening Chrome again
           - If still not working, press home and try again
        4. Once in Chrome:
           - Look for the address bar
           - Tap it to focus
           - Wait for keyboard to appear
           - If keyboard appears, type 'google.com'
           - If keyboard doesn't appear, try tapping a different part of the address bar
           - After typing, look for and tap the 'Go' or 'Enter' button on the keyboard
        5. On Google's homepage:
           - Find the search box
           - Tap it to focus
           - Wait for keyboard to appear
           - If keyboard appears, type '{args.search_term}'
           - If keyboard doesn't appear, try tapping a different part of the search box
           - After typing, look for and tap the 'Search' or 'Google Search' button on the keyboard
        6. Verify search results are displayed""",
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
        print("\n========== Starting Google Search Test ==========")
        print(f"Goal: Search for '{args.search_term}' on Google")
        print(f"Model: {planner_options.model}")
        print(f"Max steps: {agent_options.max_steps}")
        print(f"Screenshots: {screenshot_dir}")
        if args.debug:
            print("Debug mode enabled")
        print("\nPress Ctrl+C to abort\n")
        
        agent.start()
        
        # Check final status
        if agent.status == AndroidGoalState.SUCCESS:
            print("\n✅ Successfully completed Google search!")
            return 0
        elif agent.status == AndroidGoalState.FAILED:
            print(f"\n❌ Failed to complete Google search. Final status: {agent.status}")
            return 1
        else:
            print(f"\n⚠️ Search not completed (reached maximum steps)")
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