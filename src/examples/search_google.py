"""Example script to demonstrate searching Google on Android.

This script shows how to:
1. Launch Chrome browser with first-run handling
2. Navigate to Google.com
3. Perform a search with enhanced keyboard handling
4. Verify search results
"""

import argparse
import os
import sys
import time
import subprocess
from typing import List, Optional

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from android_agent.android_agent import AndroidAgent, AndroidAgentOptions, AndroidGoalState
from android_agent.android_action import AndroidAction, AndroidActionType
from android_agent.openai_planner import OpenAIPlanner, OpenAIPlannerOptions
from android_agent.android_controller import (
    is_keyboard_visible, 
    wait_for_keyboard, 
    dismiss_keyboard,
    get_current_app,
    press_home,
    press_back
)

def get_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """Get OpenAI API key from args or environment."""
    return api_key or os.environ.get("OPENAI_API_KEY")

def launch_chrome(adb_path: str) -> bool:
    """Launch Chrome with first-run handling.
    
    Args:
        adb_path: Path to ADB executable
        
    Returns:
        bool: True if Chrome launched successfully
    """
    print("\n🌐 Launching Chrome with first-run handling...")
    
    # First try direct launch with flags to skip first-run
    try:
        cmd = f"{adb_path} shell am start -a android.intent.action.VIEW -d \"about:blank\" -n com.android.chrome/com.google.android.apps.chrome.Main --es \"com.android.chrome.firstrun.skip\" \"true\""
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and "Error" not in result.stdout:
            print("✅ Chrome launched with skip-first-run flag")
            time.sleep(2)  # Wait for Chrome to load
            return True
    except Exception as e:
        print(f"⚠️ Direct launch failed: {e}")
    
    # If direct launch fails, try standard launch
    try:
        cmd = f"{adb_path} shell am start -a android.intent.action.VIEW -d \"about:blank\" -n com.android.chrome/com.google.android.apps.chrome.Main"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and "Error" not in result.stdout:
            print("✅ Chrome launched with standard command")
            time.sleep(2)
            
            # Check if we're in first-run screen
            current_app = get_current_app(adb_path)
            if "firstrun" in current_app.lower():
                print("⚠️ First-run screen detected - attempting to bypass")
                # Try tapping "Use without an account" at different positions
                for y in [0.75, 0.8, 0.85]:
                    tap_cmd = f"{adb_path} shell input tap 540 {int(2400 * y)}"
                    subprocess.run(tap_cmd, shell=True)
                    time.sleep(1)
                    
                    # Check if we're out of first-run
                    current_app = get_current_app(adb_path)
                    if "firstrun" not in current_app.lower():
                        print("✅ Successfully bypassed first-run screen")
                        return True
                
                print("⚠️ Could not bypass first-run screen")
                return False
            
            return True
    except Exception as e:
        print(f"⚠️ Standard launch failed: {e}")
    
    return False

def main():
    """Main function to run the Google search automation."""
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
            "If Chrome shows first-run screen, look for and tap 'Use without an account'",
            "If first-run screen persists, try tapping different parts of the screen",
            "After bypassing first-run, wait for Chrome to fully load before proceeding"
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
        3. If Chrome shows first-run screen:
           - Look for and tap 'Use without an account'
           - If that doesn't work, try tapping different parts of the screen
           - Wait for Chrome to fully load after bypassing first-run
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
        
        # Try to launch Chrome first
        if not launch_chrome(args.adb_path):
            print("⚠️ Could not launch Chrome - proceeding with agent anyway")
        
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
            press_home(args.adb_path)
            # Check if keyboard is visible and dismiss it
            if is_keyboard_visible(args.adb_path):
                print("Dismissing keyboard...")
                dismiss_keyboard(args.adb_path)
        except Exception as e:
            if args.debug:
                print(f"Cleanup error: {e}")


if __name__ == "__main__":
    sys.exit(main()) 